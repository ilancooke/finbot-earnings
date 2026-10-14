# finbot-earnings event contracts

## FilingReady 1.0 — consumer expectations agreed 2026-10-14

`finbot-filings` owns this shared notification contract and its implementation.
The [producer-owned contract and design](../../finbot-filings/docs/FILING_READY.md)
in the sibling workspace checkout is authoritative. This document records the
matching input expected by `finbot-earnings`; keep its fields and hashing rules
aligned with that source.

The producer transition is not implemented: current code publishes per-document
`ArtifactReady`. The target earnings subscription consumes only `filing.ready`
on the existing filings SNS topic. Earnings owns the SQS subscription and the
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

### Earnings work identity

```text
filing_id + snapshot_id + extraction_config_version + run_mode
```

The canonical EarningsEvent identity remains company and reporting period, as
specified in [V0_DECISIONS.md](V0_DECISIONS.md).

## Other contracts

The LLM response is specified in [V0_DECISIONS.md](V0_DECISIONS.md). The final
validated EarningsEvent publication envelope will be finalized separately.
