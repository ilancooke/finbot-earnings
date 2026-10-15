# Local filing evaluation

The evaluation runner reuses `NovaLiteModel`, `FilingPipeline` and the evidence
validator. Documents and labels are local files; processing records use a new
local SQLite database in evaluation mode. It never consumes a queue, downloads
from S3, updates DynamoDB, creates canonical events or publishes notifications.
No earnings deployment is needed. Only Bedrock inference runs remotely.

## Commands

Run from the repository root after installing `.[dev]` (or `.[aws]` for runtime
use without the development tools). `earnings-eval` is a console alias for
`python -m finbot_earnings.evaluation`. Neither loads `.env` or the legacy POC CLI.

```bash
# Validate every case, label, local file size and SHA-256; no AWS access.
.venv/bin/python -m finbot_earnings.evaluation check \
  --corpus evaluations/starter/corpus.json

# Smoke-test the full runner using saved synthetic responses; no AWS access.
.venv/bin/python -m finbot_earnings.evaluation run \
  --corpus evaluations/starter/corpus.json --offline \
  --output-dir /tmp/earnings-eval-smoke

# Paid Nova Lite inference, one request per supported complete filing snapshot.
.venv/bin/python -m finbot_earnings.evaluation run \
  --corpus /path/to/reviewed-corpus/corpus.json --profile default \
  --output-dir /path/to/new-evaluation-run
```

Output directories must be new. Re-running into a different directory is a new
experiment and can incur charges again. Runs are sequential, with no automatic
application or SDK inference retries and no repair calls. Technical failures are
recorded and subsequent cases continue. The exit code is 1 for technical failures,
2 for invalid CLI/corpus inputs and 0 for a completed run; quality scores alone do
not set a failure threshold. All corpus inputs are checked before inference starts.

The default `--config infra/cdk/config.prod.json` supplies region and extraction
configuration. An alternate file needs `region` and the complete `extraction`
object; other infrastructure fields are ignored. The current adapter requires
`amazon.nova-lite-v1:0` and prompt `eps-nova-tool-v1`. Normal AWS credentials must
permit `bedrock:InvokeModel` on that model in the configured region. `--profile`
is optional; the default AWS credential chain also works. A single client is
created lazily and reused. Existing input/output limits and review policy apply.

To estimate cost, supply both `--input-usd-per-million` and
`--output-usd-per-million` using current prices for that model, region and inference
mode from [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/). Rates are saved
in the run metadata. No prices are silently assumed. Estimates use reported input
and output tokens, exclude taxes/discounts and are not a billing record. Without
rates, cost is `null`/unknown. Failed or malformed provider responses can lack
usage: total estimated cost then remains unknown, alongside a known subtotal and
the count of calls with unknown usage. Fixture tokens and cost estimates are
synthetic equivalents, not real charges.

## Corpus format and real labels

[`evaluations/starter`](../evaluations/starter) contains eight **synthetic** cases,
not reviewed real filings. Its fixture responses are deliberately known answers;
perfect offline scores only verify the harness. Cases cover multi-file HTML,
negative EPS/plain text with historical comparisons, PDF-only and mixed inputs,
non-earnings notices, guidance, conflicting values and financial tables.

Keep a real corpus outside source control, for example under
`$FINBOT_DATA_ROOT/earnings/evaluations/corpora/`. Treat downloaded files as fixed;
there is no separate freezing operation. Copy their bytes unchanged. Use an existing
FilingReady payload when available. For older filings, construct equivalent evaluator
metadata from the filing record, complete selected artifact records and company
record, and record that origin separately. No SNS publication is needed. Local paths
replace transport access; original `s3_uri` values remain provenance and are never
fetched by the runner. Do not label an incomplete collection as a full filing input.

For the product baseline, use only finbot-filings artifacts in
`finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua`, grouped by ticker/filing.
Older local collections used different filters and are excluded from the active
golden dataset. Local evaluation copies must come from that product output; the
saved records retain real S3 references. See [GOLDEN_DATASET.md](GOLDEN_DATASET.md).

Use `label_source: "agent_draft"` for assistant-drafted real labels pending review;
reports preserve this status. Change it to `human_reviewed` only after checking the
labels against the source documents. The existing file-size/hash checks are automatic
corpus-format checks, not an additional operator freezing step.

The root `corpus.json` has:

```json
{
  "schema_version": "1.0",
  "corpus_id": "reviewed-filings-v1",
  "label_source": "human_reviewed",
  "label_notes": "Who reviewed the labels, when, and the review procedure",
  "cases": ["case-a/case.json", "case-b/case.json"]
}
```

Each case JSON has these fields (see a complete starter case for an example):

| Field | Meaning |
| --- | --- |
| `case_id` | Unique filename-safe token, up to 80 characters |
| `tags` | Array of coverage labels, such as `pdf` or `historical_comparison` |
| `filing` | Complete valid FilingReady 1.0 JSON, including original snapshot hash |
| `documents` | Exactly one entry per manifest artifact ID, each with `path` and `sha256` |
| `expected` | Reviewed classification and facts in the minimal EPS extraction schema |
| `fixture_response` | Optional relative JSON filename for `--offline` playback; contains `response` and `usage` |

All paths are relative to the **corpus root**, including paths inside case JSON.
Absolute paths and symlinks escaping that root are rejected. File sizes must match
the upstream manifest; content hashes must match the corpus entries. A file's
SHA-256 can be obtained with `shasum -a 256 /path/to/document`. JSON inputs reject
duplicate keys and nonfinite numbers. Changes to source bytes require a new corpus
version and matching hashes; changed labels also produce a different corpus hash.
Repeated case IDs or filing snapshots are rejected.

Review labels independently of model output. Expected facts use the same fields
documented in [V0_DECISIONS.md](V0_DECISIONS.md): metric, signed decimal value,
currency, period, source artifact ID and supporting evidence. Include current
reported results, preserving sign and precision; omit historical comparisons and
guidance. Negative and uncertain cases have empty fact arrays. One expected fact
per metric/reporting period is allowed. Expected facts must cite manifest sources.
Labels are never included in Bedrock requests. Avoid tuning prompts on the entire
corpus; reserve reviewed cases for a later holdout comparison.

## Outputs and score interpretation

Each run writes:

- `run.json`: run identity/time, provider, region, full extraction configuration,
  corpus hash, scoring version, prompt/schema/validator hashes and optional prices.
- `corpus-snapshot.json`: frozen parsed input manifests, document paths/hashes and
  labels; offline runs also retain the fixture responses they used.
- `processing.sqlite3`: durable evaluation processing records, without canonical
  events or an outbox. Raw document bodies remain in the original frozen corpus.
- `cases/<case_id>.json`: saved model response/usage, timing, validation findings,
  accepted facts, outcome and per-case scores.
- `report.json` and `report.md`: aggregate and case-level results, updated after
  each case so completed work remains inspectable after interruption. Check
  `complete` before comparing a report to a full baseline.

Classification accuracy and exact extraction accuracy use **all processed cases**,
including failed, invalid and pre-inference review cases. Exact extraction requires
a valid response, correct classification and no missing/extra facts. Technical
failures are not discarded to make the model look better.

Fact precision/recall/F1 use exact metric, currency, period kind/end date and decimal
string (preserving precision, ignoring an optional leading `+`). A wrong value or
period counts as both one extra and one missing fact; duplicate predictions count
as extras. Quote wording, period labels and source IDs are not part of this
economic-value score: the production validator independently checks grounding.
Undefined ratios, such as recall when no expected facts exist, are `null`/`n/a`.

The **extraction** scores compare the saved response to gold facts before evidence
validation. The **accepted** scores compare accepted facts against the same gold
facts. Review outcomes, findings and acceptance rate show the difference between
extracting a value correctly and accepting it under the current policy. In
particular, PDF-sourced and table-only facts remain review-only even when correctly
extracted. This is an intentional visible validation gap, not an extraction error.

Latency is local wall-clock time around the model adapter, including SDK/network
overhead. Reports include median and nearest-rank p95 model latency, case durations
and token totals with usage-completeness counts. No raw SDK error messages,
credentials or document bodies are printed. These JSON/SQLite files are local
experiment records, not published research datasets or catalog outputs.
