# Milestone 1 contract specifications

These files specify the approved launch contract. The isolated Milestone 2 extractor
loads its own byte-exact packaged fiscal schema; the legacy consumer does not import
these documents. [CONTRACTS.md](../CONTRACTS.md) explains the business rules and
compatibility boundary. Synthetic examples are not deployable input/configuration
or new extraction-quality evidence.

- `earnings_eps_fiscal_v2.schema.json`: byte-exact copy of the tested evals schema.
- `earnings_extracted_v1.schema.json`: new output envelope specification, embedding
  the same observation schema; application checks additionally enforce identity,
  provenance, one period and uniqueness.
- `examples.json`: 16 response cases, six identity vectors, one complete accepted
  event and three input-policy examples. Repeated-letter hashes are intentional
  synthetic digest inputs; their configurations/source files are not real objects.

The checker below validates schemas, examples, copied-schema hash and canonical
identity/provenance. It checks the specification, not production implementation
parity or provider behavior. Run from the earnings repository using its `.venv`:

```python
from copy import deepcopy
from hashlib import sha256
import json
import re
from urllib.parse import unquote
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

root = Path('docs/contracts')
load = lambda name: json.loads((root / name).read_text())
eps = load('earnings_eps_fiscal_v2.schema.json')
event_schema = load('earnings_extracted_v1.schema.json')
data = load('examples.json')
for schema in (eps, event_schema):
    Draft202012Validator.check_schema(schema)
assert sha256((root / 'earnings_eps_fiscal_v2.schema.json').read_bytes()).hexdigest() == '658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94'
validator = Draft202012Validator(eps)
for case in data['response_cases']:
    response = case['response']
    exact_integers = all(type(row['fiscal_year']) is int and
                         (row['fiscal_quarter'] is None or type(row['fiscal_quarter']) is int)
                         for rows in response.values() for row in rows)
    if not validator.is_valid(response) or not exact_integers:
        actual = ('processing_failed', 'invalid_model_response')
    else:
        periods, duplicate = set(), False
        for rows in response.values():
            keys = set()
            for row in rows:
                period = (row['period_type'], row['fiscal_year'], row['fiscal_quarter'])
                key = (row['currency'], *period)
                duplicate |= key in keys
                keys.add(key)
                periods.add(period)
        actual = (('review_required', 'duplicate_observation') if duplicate else
                  ('review_required', 'multiple_fiscal_periods') if len(periods) > 1 else
                  ('accepted', None) if periods else ('no_eps_extracted', None))
    assert actual == (case['expected_outcome'], case['expected_reason']), case['name']
for vector in data['identity_vectors'].values():
    encoded = json.dumps(vector['identity'], sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False)
    digest = sha256(encoded.encode('utf-8')).hexdigest()
    assert encoded == vector['canonical_json'] and digest == vector['digest']
    assert vector['work_id'] == 'earnings-work:v2:' + digest
    assert vector['event_id'] == 'earnings.extracted:1.0:' + digest
    assert vector['processing_record_ref'] == 'earnings-processing:v2:' + digest
vectors = data['identity_vectors']
assert vectors['initial'] == vectors['duplicate_delivery']
assert len({v['digest'] for v in vectors.values()}) == 5
sample = data['accepted_event']
Draft202012Validator(event_schema, format_checker=FormatChecker()).validate(sample)
initial = vectors['initial']
assert sample['event_id'] == initial['event_id']
assert sample['processing']['work_id'] == initial['work_id']
assert sample['source']['manifest_ref'] == initial['processing_record_ref'] + '/input'
for field in ('filing_id', 'snapshot_id'):
    assert sample['source'][field] == initial['identity'][field]
for field in ('extraction_config_version', 'extraction_config_sha256', 'run_id'):
    assert sample['processing'][field] == initial['identity'][field]
assert sample['processing']['processing_record_ref'] == initial['processing_record_ref']
assert sample['extraction_started_at'] <= sample['extraction_completed_at'] <= sample['created_at']
assert sample['extraction'] == data['response_cases'][0]['response']
empty_event = deepcopy(sample)
empty_event['extraction'] = {'reported_diluted_eps': [], 'adjusted_diluted_eps': []}
assert not Draft202012Validator(event_schema).is_valid(empty_event)
for case in data['input_cases']:
    assert case['inference_calls'] == case['events'] == 0
paths = [Path('README.md'), Path('ROADMAP.md'), *Path('docs').glob('*.md'), root / 'README.md']
links = 0
for path in paths:
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', path.read_text()):
        if '://' in target or target.startswith('mailto:'):
            continue
        name, _, fragment = unquote(target).partition('#')
        dest = (path.parent / name).resolve() if name else path.resolve()
        assert dest.exists(), (path, target)
        if fragment and dest.suffix == '.md':
            headings = re.findall(r'^#{1,6} (.+)$', dest.read_text(), re.M)
            slugs = {re.sub(r'[^\w\s-]', '', h.lower()).replace(' ', '-') for h in headings}
            assert fragment in slugs, (path, target, slugs)
        links += 1
print('Specification checks passed: 2 schemas, 16 responses, 6 identity vectors, 1 event, 3 input examples.')
print(f'Documentation checks passed: {len(paths)} Markdown files, {links} local links/fragments.')
```

Shell command to execute this exact block:

```bash
.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'
```
