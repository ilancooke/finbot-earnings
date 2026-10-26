# Independent reference fingerprint export

Run from `finbot-filing-evals` at commit
`d105712812a3daaf0d958c0b9b180f41ca4703ce`, using that package's `.venv`.
This is a one-time read-only audit recipe, not an earnings dependency or evaluator.
The saved run is checked by the evals loader. Source modules are matched against
its implementation hashes before the actual direct adapter is called with the
pinned SDK over mocked HTTP. Source artifacts stay read-only; SDK output is written
only under a temporary directory. No real credential or provider call is used.

Save the following block to `/tmp/finbot-m5-export-reference.py`, then run:

```bash
.venv/bin/python /tmp/finbot-m5-export-reference.py \
  ../../data/filing-evals/runs/20261023T145725Z-9ff8c84b \
  /tmp/finbot-m5-reference.json
```

Compare `/tmp/finbot-m5-reference.json` with earnings'
[`v6-reference.json`](v6-reference.json). The SHA-256 is
`1a3b0c28c18c1db411259fd1ed0357d30e4273870b4cbc3cd656cb30eac0b289`.
The export is deterministic and preserves both the actual reference request digest
and a second digest changing only the equivalent `filed_at` timestamp spelling.
Do not regenerate this evidence to conceal a material configuration change;
evaluate changes in evals and document compatibility before updating the baseline.

```python
"""Run with finbot-filing-evals' own Python, from that repository; no inference."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
import openai
from finbot_filing_evals.evaluation import direct
from finbot_filing_evals.evaluation.files import load_run


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return sha256(raw).hexdigest()


def forbidden(*args, **kwargs):
    raise RuntimeError("Network forbidden during reference export")


socket.socket.connect = socket.create_connection = forbidden
root, output = map(Path, sys.argv[1:])
manifest, results = load_run(root)
config = json.loads((root / "extractor.json").read_text())
source = Path(direct.__file__).parents[1]
for name in ("direct.py", "bedrock.py", "contracts.py", "files.py"):
    assert sha256((source / "evaluation" / name).read_bytes()).hexdigest() == manifest["implementation"][name]
assert sha256((source / "review/viewer.py").read_bytes()).hexdigest() == manifest["implementation"]["viewer.py"]
rows = []
with TemporaryDirectory(prefix="finbot-m5-reference-") as tmp:
    for request_path in sorted((root / "inputs").glob("*/request.json")):
        case = request_path.parent.name
        seen = []
        body = (root / "responses" / (case + ".provider.json")).read_bytes()

        def handler(request):
            assert str(request.url) == "https://api.openai.com/v1/responses"
            assert request.extensions["timeout"] == dict(connect=120, read=120, write=120, pool=120)
            seen.append(json.loads(request.content))
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            with openai.OpenAI(api_key="synthetic-offline-key", base_url=direct.ENDPOINTS["openai"],
                               timeout=120, max_retries=1, http_client=http) as client:
                with patch.object(direct, "make_client", return_value=client):
                    extractor = direct.DirectExtractor(config)
                    envelope, _, error = extractor.invoke(request_path, request_path.parent,
                                                          Path(tmp) / (case + ".json"))
        assert error is None and len(seen) == 1
        native = json.loads(body)
        labels = json.loads(direct.extraction_text(native, "openai"))
        usage = direct.normalized_usage(native, "openai")
        assert json.loads(envelope)["labels"] == labels
        expected = deepcopy(seen[0])
        context = json.loads(expected["input"][0]["content"][0]["text"].removeprefix("Filing context: "))
        original = context["filed_at"]
        context["filed_at"] = datetime.fromisoformat(original.replace("Z", "+00:00")).astimezone(
            timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        expected["input"][0]["content"][0]["text"] = "Filing context: " + json.dumps(context, ensure_ascii=False)
        rows.append(dict(case_id=case, reference_request_sha256=digest(seen[0]),
                         canonical_timestamp_request_sha256=digest(expected),
                         filed_at_before=original, filed_at_after=context["filed_at"],
                         extraction_sha256=digest(labels), usage_sha256=digest(usage)))
result = dict(schema_version=1, run_id=manifest["run_id"],
              integrity_sha256=sha256((root / "integrity.json").read_bytes()).hexdigest(),
              reference_implementation=manifest["implementation"],
              dependencies={p: metadata.version(p) for p in
                            ("openai", "httpx", "html5lib", "Pillow", "jsonschema", "webencodings", "six")},
              baseline_summary=results["summary"], cases=rows)
output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
print(f"Exported {len(rows)} reference request/output fingerprints; no network")
```
