# finbot-earnings event contracts

Updated 2026-10-25 through Milestone 3. Input 1.0 remains unchanged. The
[fiscal extractor](EXTRACTOR.md), `FiscalConsumer` and version-2 stores implement
the response, acceptance, identity and `earnings.extracted` contract below.
[OFFLINE_PROCESSING.md](OFFLINE_PROCESSING.md) records physical storage and CLI.
The documentation event schema checks runtime fixtures in tests; runtime acceptance
uses the packaged fiscal schema. Legacy paths/records remain separately until cleanup.

## FilingReady 1.0 — consumer expectations agreed 2026-10-14

`finbot-filings` owns this shared notification contract and its implementation.
The [producer-owned contract and design](../../finbot-filings/docs/FILING_READY.md)
in the sibling workspace checkout is authoritative. This document records the
matching input expected by `finbot-earnings`; keep its fields and hashing rules
aligned with that source.

The producer source implements filing-level `FilingReady`; actual deployed state
has not been inspected in this milestone. The target earnings subscription consumes only `filing.ready`
on the producer’s `finbot-prod-filing-ready` SNS topic (`FilingTopicArn` CDK
output). Subscriptions to the old artifact-ready topic do not receive these events. Earnings owns the SQS subscription and the
processing of the complete selected filing snapshot in one LLM request.

The notification contains references, not document bytes.

### Envelope

All fields below are required.

| Field | Type | Contract |
| --- | --- | --- |
| `event_type` | String | Exactly `filing.ready` |
| `schema_version` | String | Exactly `1.0` |
| `filing_id` | String | Dashed SEC accession |
| `snapshot_id` | String | Deterministic manifest SHA-256, specified below |
| `cik` | String | Ten-digit, zero-padded canonical company identity |
| `ticker` | String | Canonical upstream ticker |
| `company_name` | String | Reviewed upstream company name, frozen with the snapshot |
| `form_type` | String | Original SEC form, retaining amendment suffix when present |
| `filed_at` | UTC timestamp string | Canonical SEC acceptance time |
| `ready_at` | UTC timestamp string | First durable completion of this stored snapshot |
| `primary_artifact_id` | String | Primary report's identity, present exactly once in `artifacts` |
| `artifacts` | Array of objects | Nonempty complete selected manifest, sorted by `artifact_id` |

Use normalized UTC timestamps in `YYYY-MM-DDTHH:MM:SS.ffffffZ` form so equivalent
timestamps have one representation for snapshot hashing.

### Artifact entries

| Field | Type | Contract |
| --- | --- | --- |
| `artifact_id` | String | Required; existing `<accession>/<filename>` identity |
| `filename` | String | Required; safe original basename with case preserved |
| `s3_uri` | String | Required; canonical upstream stored-object reference |
| `size_bytes` | Integer | Required; nonnegative stored byte count |
| `document_type` | String | Optional; omit when unknown |
| `content_type` | String | Optional; omit when unknown |

There is no redundant artifact count. Unknown optional values are omitted, not
null. Every artifact must belong to the envelope's filing and company; artifact
identity must agree with accession and filename. Preserve canonical S3 URI
encoding from upstream.

Supporting JPEG/PNG/GIF files can appear in this same manifest. Original HTML
image references retain parent association and page order; rasters are handled
separately from standalone document counts. No new event fields or hash rules are
introduced. Update image-unaware consumers before upstream image acquisition or
recovery publishes new snapshots. Existing event snapshots remain immutable.

### Readiness guarantees expected by the consumer

The notification lists a nonempty complete selection with unique artifact IDs
and exactly one referenced primary. Every listed document is already stored.
Completeness covers the selected snapshot, not every file in the SEC archive.
The consumer uses this list directly rather than inferring completion from an
S3 prefix, individual document events or a waiting period.

Snapshot contents and `ready_at` remain fixed across notification retries. Added
attachments create a new snapshot; previously published inputs remain immutable.
Delivery is at least once. The consumer must tolerate duplicate notifications.
Producer-specific persistence and publication recovery are documented in
`finbot-filings/docs/FILING_READY.md`, not in the earnings architecture.

### Deterministic snapshot identity

Compute `snapshot_id` as the lowercase 64-character hexadecimal SHA-256 digest of
canonical UTF-8 JSON containing exactly these envelope fields:

```text
filing_id, cik, ticker, company_name, form_type, filed_at,
primary_artifact_id, artifacts
```

Include every artifact field present in the manifest. Sort artifact entries by
their case-sensitive `artifact_id`; sort all JSON object keys, use no insignificant
whitespace, emit Unicode as UTF-8 and preserve original string case. Normalize
timestamps before hashing. Exclude `ready_at`, `snapshot_id`, the SNS/SQS wrapper
and other transport metadata.

Equivalent input produces the same identity regardless of notification retries
or original array ordering. Added documents or changed hashed input fields produce
a different identity. This hashes the manifest, not document bytes, relying on
the producer's immutable-object contract.

## Extraction response — earnings_eps.fiscal.v2

The exact tested local JSON Schema is copied byte-for-byte to
[earnings_eps_fiscal_v2.schema.json](contracts/earnings_eps_fiscal_v2.schema.json).
The isolated extractor loads a byte-exact packaged copy. Both required
arrays are `reported_diluted_eps` and `adjusted_diluted_eps`; no additional keys.
Each observation has exactly:

| Field | Required type/rule |
| --- | --- |
| `value` | String matching `^-?[0-9]+\.[0-9]+$`; preserve sign, digits and trailing zeroes; no exponent, commas or plus sign |
| `currency` | Three uppercase letters (`^[A-Z]{3}$`); disclose currency, never convert |
| `period_type` | `quarterly` or `annual` |
| `fiscal_year` | Integer 1000–9999, issuer's fiscal designation |
| `fiscal_quarter` | Integer 1–4 for quarterly, JSON null for annual |

Null is allowed only for annual `fiscal_quarter`. Booleans are not fiscal integers.
No calendar dates, classification, quote, source ID, confidence or share-basis
field. Do not add them to the tested model response. Empty arrays are valid.
Local business checks require one period across both arrays and uniqueness per
metric/currency/period, beyond JSON Schema. See [acceptance policy](V0_DECISIONS.md#acceptance-policy).

Quarterly means one standalone fiscal quarter. Annual means an affirmatively
complete fiscal year, including a 52/53-week year. YTD/multiquarter aggregations
are excluded. Q4 wins when both Q4/full year are disclosed; annual-only reports
select annual. No period dates or quarter-by-subtraction inference. Source meaning
is enforced by prompt v6, not independent per-fact verification.

The provider transport schema `openai-fiscal-v2-union-v1` uses the evals
`direct.output_schema` compilation: remove `$schema`, replace observation `allOf`
conditionals with `anyOf` quarterly/annual variants, retain the local schema's
other fields/constraints, and locally validate against the unchanged full schema.
Do not silently weaken fiscal checks to satisfy provider schema restrictions.
Milestone 2 implements and tests this compilation and request settings.

## Configuration and processing record versions

Milestone 2 freezes `eps-openai-luna-v6-v1` in the isolated extractor's
`resources/configuration.json`; it is distinct from the legacy configuration
dataclass. [EXTRACTOR.md](EXTRACTOR.md) specifies its bounds, receipt API and pins.
An immutable configuration document includes these keys:

| Key | Required content |
| --- | --- |
| `version` | Configuration version string, `[A-Za-z0-9._-]{1,200}` |
| `provider`, `model`, `endpoint` | `openai`, `gpt-6-luna`, `https://api.openai.com/v1` |
| `prompt_version`, `prompt_sha256` | `eps-v6` and SHA-256 of exact UTF-8 prompt file bytes |
| `response_schema_version`, `response_schema_sha256` | `earnings_eps.fiscal.v2` and exact local schema file-byte digest |
| `transport_schema_version`, `transport_schema_sha256` | `openai-fiscal-v2-union-v1` and canonical compiled-schema digest |
| `preparation_version`, `preparation_sha256` | `filing-html-text-images-v1` and versioned preparation implementation/inventory digest |
| `adapter_version`, `sdk_versions` | Traceable adapter version and exact SDK/parser/image dependency versions |
| `acceptance_policy` | `fiscal-eps-acceptance-v1` |
| `request_settings` | Tested request settings, high image detail, 120-second timeout, zero SDK retries; application budgets attempts separately |
| `input_limits` | Frozen finite limits in configuration and EXTRACTOR; whole-snapshot review, including 64-image cap supporting HON |
| `persistence_limits` | 2-MiB native response, 64-KiB extracted text; 240-KiB event reservation; durable splitting/enforcement in Milestone 3 |

Use exact strings/integers/booleans/arrays/objects; no floating-point numbers,
nonfinite numbers or secret values in configuration. Operational destinations,
credential values/rotation, receive times, lease ownership and transport IDs are
not extraction configuration. Save operational retry/lease settings separately.
Hash the complete configuration using canonical JSON below. Reusing a version
with different content is a configuration error; behavior changes require a new
version/digest. Include model/prompt/schema/preparation/acceptance/limit changes.

Processing records use `record_schema_version: 2` in a new namespace. Their logical
content is: immutable identity and complete input manifest (`input`), full
`extraction_config` and digest, saved native/parsed `response` with usage and
extraction timing, outcome/reasons, immutable event reference/bytes and separate
publication attempts/acknowledgments/times. Keep invalid/refused/incomplete results
inspectable too. Physical keys, bounded chunk splitting and transactional status partitions are
implemented in Milestone 3; see OFFLINE_PROCESSING. Legacy stores remain separate.

## Work and immutable event identity

Canonical JSON means UTF-8, object keys sorted recursively, no insignificant
whitespace, Unicode emitted directly (no normalization/case changes), arrays kept
in their specified order, duplicate keys/nonfinite values rejected. Python
reference encoding: `json.dumps(value, sort_keys=True, ensure_ascii=False,
separators=(',', ':'), allow_nan=False).encode('utf-8')`. For digests, use lowercase
64-character hex SHA-256. Exact file-byte digests above are distinct from canonical
JSON content digests.

Hash exactly this identity object, with all fields required:

```json
{
  "namespace": "earnings.extracted/1.0",
  "filing_id": "0000000001-26-000001",
  "snapshot_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "extraction_config_version": "eps-openai-luna-v6-v1",
  "extraction_config_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "run_id": "initial"
}
```

`run_id` matches `[A-Za-z0-9._-]{1,100}`, defaults to `initial`, and is explicitly
chosen for a fresh operator run. There is no target evaluation run mode; evals
owns experiments. The synthetic digest inputs above do not identify real objects.
Their canonical identity SHA-256 is
`0d2d1880a4cf29b45d1922d0972f9fa79dc417732ce7aa2b00058643c12f8fff`.
[examples.json](contracts/examples.json) records exact canonical bytes and vectors.

```text
D = sha256(canonical identity object)
work_id = "earnings-work:v2:" + D
processing_record_ref = "earnings-processing:v2:" + D
event_id = "earnings.extracted:1.0:" + D
manifest_ref = processing_record_ref + "/input"
```

Processing/manifest references are logical identifiers resolved by the version-2
operator/storage adapter, not public URLs or new S3 paths. `manifest_ref` resolves
to the exact complete FilingReady input retained for this work. One accepted work
has one immutable event. Do not include EPS values or completion/publication times
in identity. No canonical company-period ID, HEAD or revision counter.

| Input/action | Result |
| --- | --- |
| Same snapshot/config/run delivered again | Same work/result/event ID; no fresh inference after saved completion |
| Publication retry/lost acknowledgment | Identical saved event bytes/ID; at-least-once delivery |
| Same filing, changed manifest/snapshot | New work/event if accepted, even with equal EPS |
| Amended filing or later report for same fiscal period | Independent work/event, retaining original form type and provenance |
| Explicit fresh run | New run ID/configuration, new result/event if accepted; preserve old result |
| Retry/rearm failed work | Same identity; resume response/publication checkpoints, no forced re-extraction |
| Different filing with different EPS | Independent accepted event; no cross-filing value-conflict gate |

An existing identity with different immutable input/configuration is rejected,
not overwritten. No automatic reprocessing on configuration rollout, historical
S3 scan or legacy republication. Recovery before response persistence may call the
provider again; exactly-once inference is not promised.

## earnings.extracted 1.0 event

[earnings_extracted_v1.schema.json](contracts/earnings_extracted_v1.schema.json)
is the documentation schema. All listed fields are required, no additional fields:

| Field | Meaning |
| --- | --- |
| `event_type`, `schema_version` | Exactly `earnings.extracted`, `1.0` |
| `event_id` | Derived immutable ID above; downstream deduplication key |
| `issuer` | `cik`, `ticker`, `company_name`, copied from authoritative input |
| `source` | `filing_id`, `snapshot_id`, `form_type`, `filed_at`, `ready_at`, `primary_artifact_id`, `manifest_ref`; one input snapshot |
| `extraction` | Complete accepted fiscal v2 object; both EPS arrays, at least one nonempty |
| `processing` | Fields detailed below |
| `extraction_started_at`, `extraction_completed_at` | Start/end of the saved successful extraction attempt; original timestamps survive recovery |
| `created_at` | Event creation/acceptance time, fixed before atomic persistence/publication |

`processing` requires `work_id`, `processing_record_ref`, `run_id`, `provider`,
`model`, `extraction_config_version`, `extraction_config_sha256`, `prompt_version`,
`response_schema_version`, `preparation_version`, `acceptance_policy`.
Values follow the version register and hash rules above. The reference resolves
full prompt/schema/preparation/transport versions/hashes, settings, raw response,
usage, input manifest, outcomes and timing. No secret values in provenance.

Source fields must equal saved input; all ID/reference suffixes and the config
hash must agree with the recomputed work digest. All observations share one fiscal
period; duplicate keys within a metric are disallowed. Those cross-field rules
are checked in application code, beyond the JSON Schema. UTC timestamps use
`YYYY-MM-DDTHH:MM:SS.ffffffZ` and valid calendar/time values. Extraction start ≤
completion ≤ creation. Save actual publication acknowledgments and subscriber
receipt metadata separately, never by rewriting the event. Subscriber inspection
time is not receipt time. Missing upstream discovery times are not invented.

Serialize and save the complete event before sending SNS. Commit outcome and
publication intent atomically. Publish the same saved bytes on retries and save
acknowledgment before acknowledging the input. An accepted processing result may
still have pending/failed publication; expose that delivery stage separately.
A published event means schema/business-rule acceptance, **not independent fact
verification**. There is no per-fact quote/source claim or share denomination.

The full synthetic event with real computed IDs is in
[examples.json](contracts/examples.json), under `accepted_event`. Its extraction:

```json
{
  "reported_diluted_eps": [
    {"value":"1.230","currency":"USD","period_type":"quarterly","fiscal_year":2026,"fiscal_quarter":3}
  ],
  "adjusted_diluted_eps": [
    {"value":"1.45","currency":"USD","period_type":"quarterly","fiscal_year":2026,"fiscal_quarter":3}
  ]
}
```

## Acceptance examples

All amounts are synthetic. [examples.json](contracts/examples.json) contains full,
reported-only, adjusted-only, empty, annual, Q4, YTD, total/component, currency,
conflict, invalid-output and identity examples for offline implementation fixtures.

| Disclosure/output | Required result |
| --- | --- |
| Q3 FY2026 reported `-0.30`, no adjusted metric established | Accepted reported array with `-0.30`, adjusted `[]`; preserve loss sign |
| Only adjusted Q3 FY2026 `1.45` established | Reported `[]`, adjusted nonempty; publish |
| Q4 FY2026 `1.20` and full-year `4.90` | Select Q4 only, not two events/periods |
| Full FY2027 `5.10` only | Annual FY2027, `fiscal_quarter: null`; do not substitute publication year |
| Q3 FY2031 `2.15` alongside partial-year YTD `6.40` | Emit only `2.15`; no annual relabeling or quarter-by-subtraction |
| Total reported `1.23`, continuing component `1.10`, primary adjusted `1.45` based on continuing operations | Reported `1.23`, adjusted `1.45`; no calculated total |
| TWD `10.00` per ordinary share and USD `0.625` per ADS | Preserve both currencies/values; share basis unspecified, no conversion/equivalence |
| Two same-currency/share-basis values emitted under one metric/period | Cannot represent both: `duplicate_observation` review; no silent winner/conversion |
| Identical repeated rows or conflicting `1.23`/`1.24` in same metric/currency/period | Whole-response `duplicate_observation` review, no row salvage |
| Reported Q3 and adjusted Q4, or quarterly plus annual output | Whole-response `multiple_fiscal_periods` review |
| `{"reported_diluted_eps":[],"adjusted_diluted_eps":[]}` | `no_eps_extracted`; acknowledge, no publication or inference retry; not definitive non-earnings |
| Numeric EPS, exponent string `1e2`, extra classification, null currency or boolean quarter | `processing_failed / invalid_model_response`; save invalid output; no automatic inference retry |
| Separate later filing reports different/equal EPS for same period | Independent event if accepted; no canonical conflict/revision |

Correct financial period/value selection in these disclosure examples is a prompt
requirement. Structural checks cannot detect a schema-valid value taken from a YTD
column but mislabeled quarterly. Do not claim source verification that was not done.

## Review and failure reasons

These are target reason codes, distinct from legacy findings. Each stored reason
has `code` and `stage`; optional fields are omitted when inapplicable, never null.
Include `artifact_id`/`filename` for member issues, `bound`/`actual`/`limit` for
bounds, and `path` for response rows. Aggregate violations identify the whole
snapshot plus contributing member IDs. Numeric limit values are populated from
the frozen configuration. Diagnostics contain no
credentials/provider error-body text. Preserve raw response separately.

| Code | Stage / outcome / recovery |
| --- | --- |
| `unsupported_selected_format` | Input / review / identify every offending selected member, including TXT/PDF; no inference |
| `invalid_selected_image` | Input / review / failed decoder, encoding/frame support; no omitted image |
| `snapshot_bound_exceeded` | Input / review / identify named count/byte/pixel/token/encoded-request bound and actual/limit; no inference |
| `unsupported_document_encoding` | Preparation / review / identify unprocessable HTML; no silent byte loss |
| `duplicate_observation` | Acceptance / review / row paths and duplicate identity, even for equal values |
| `multiple_fiscal_periods` | Acceptance / review / conflicting periods and row paths |
| `provider_refusal`, `incomplete_model_output` | Extraction / review / preserve response, no automatic inference retry/repair |
| `invalid_model_response` | Response / terminal processing failure / invalid JSON, duplicate JSON keys, schema or unexpected response shape; no automatic inference retry |
| `invalid_filing_ready` | Input / terminal processing failure / invalid notification/hash; preserve safe diagnostics, no inference |
| `source_object_missing`, `source_size_mismatch`, `source_read_failed` | Input / processing failure / bounded technical recovery then DLQ; never treat incomplete input as accepted |
| `provider_transient_failure` | Extraction / processing failure / bounded retry budget; attempts/unknown usage recorded |
| `provider_configuration_failure` | Extraction / terminal processing failure / access/billing/quota configuration; explicit fix/resume, no blind repeated calls |
| `persistence_failed`, `publication_failed` | Persistence or publication / processing failure / bounded checkpoint recovery; saved payload publication never calls inference |

An unsupported format wins whole-snapshot review even if another member has EPS.
Invalid JSON/schema is a failed extraction rather than a factual review. Completed
review/empty outcomes acknowledge normally. Transient/exhausted technical work
remains unacknowledged until recovery/SQS redrive; there is no unbounded automatic
retry or inference on completed empty/review outcomes. Explicit new-run reprocessing
retains the same complete manifest and new run/configuration, with charges and
publication effects visible. Operator command syntax is in OFFLINE_PROCESSING.

## Compatibility with implemented v0

The retained legacy runtime accepts `eps-v0` classification/facts with evidence/period-end dates
and emits `earnings.validated` / `1.0`: company-period `event_id`, integer `revision`,
`facts`, `source_snapshots`, `validated_at`, `validation_policy`. Independent
prose checks and canonical enrichment/conflict handling apply there only; see
[OFFLINE_PROCESSING.md](OFFLINE_PROCESSING.md). Legacy tests remain; the demo now exercises the fiscal consumer.

The new event family also starts at schema `1.0`; event type plus version selects
the contract. Never parse old payloads as the new family, relabel them as extracted,
migrate/rewrite old jobs or automatically republish history. New work/record
namespaces and configuration hashes prevent legacy completions suppressing new
runs. No older published-schema consumer compatibility is promised. Inspect actual
stored cloud state before Milestone 6 release decisions; source configuration is
not proof of deployed state.

## Reference identity

The read-only source checkout was `finbot-filing-evals` commit
`d105712812a3daaf0d958c0b9b180f41ca4703ce` on 2026-10-25:

| Source | File-byte SHA-256 |
| --- | --- |
| [v6 prompt](../../finbot-filing-evals/prompts/eps-v6.txt) | `54158e06ec22a876acb0272bc1674bdd5dbf0f5a489eb7d9c8c3e65fdaf40237` |
| [fiscal schema](../../finbot-filing-evals/src/finbot_filing_evals/evaluation/schemas/earnings_eps_fiscal_v2.schema.json) | `658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94` |
| [candidate config](../../finbot-filing-evals/configs/openai-luna-6-prompt-v6-sample-50.json) | `42b31225f4d05c21543ed30bfff5c1d7288039fedd67bd35f060d44e91f8bd02` |

[Experiment report](../../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md):
L5 run `20261023T145725Z-9ff8c84b`, 83/83 targets and 50/50 exact filings, development
sample rather than held-out accuracy. Reviewed bundle:
`$FINBOT_DATA_ROOT/filing-evals/golden/earnings-eps-50-v1`. These references establish
Milestone 1's specification inputs, not Milestone 5 production parity evidence.
