# Offline filing processing

Updated 2026-10-25 for Milestone 1. **Everything under “Current implementation”
below describes the unchanged Nova-era `eps-v0` core**, not the approved launch
contract. The demo/tests still emit `earnings.validated` company-period revisions.
The direct OpenAI extractor is Milestone 2; integration/demo/CLI is Milestone 3;
legacy evaluation removal is Milestone 4. No runtime code changed in Milestone 1.

## Approved transition target — not implemented

[CONTRACTS.md](CONTRACTS.md) and [V0_DECISIONS.md](V0_DECISIONS.md) specify fiscal v2
EPS arrays, one current fiscal period, `fiscal-eps-acceptance-v1` and immutable
`earnings.extracted` 1.0 events. Independent per-fact evidence checks, classification,
period-end dates and canonical merging are removed from the launch path. Do not
feed fiscal v2 objects through the legacy prose validator or invent evidence fields.

| Member/bound | Target behavior before inference |
| --- | --- |
| HTML plus original supported JPEG/PNG/GIF images | One request using tested text/image preparation |
| TXT, PDF, other unsupported member | Whole-snapshot review, `unsupported_selected_format` |
| Mixed HTML/PDF snapshot | Whole-snapshot review; no HTML-only extraction/event |
| Complete snapshot exceeds configured bound | Whole-snapshot review, `snapshot_bound_exceeded`; no truncation/drop/split |

Numeric launch bounds are pending Milestone 2 provider verification, must cover
HON's 34 images, and must replace the current Nova caps rather than copy them.
Reasons identify member IDs/filenames or actual/limit/bound; see CONTRACTS.

Target outcomes are `accepted`, `no_eps_extracted`, `review_required` and
`processing_failed`. Empty/review results complete without automatic inference
retry. Retry/rearm resumes saved checkpoints; deliberate extraction after inspecting
review/empty results needs a new run/configuration and can incur charges/publish a
new event. Milestone 3 supplies concrete CLI commands and status indexing. Until
then, the repository methods/demo below apply only to legacy records.

Preserve fenced leases, saved responses, atomic outcome/event/publication intent,
and identical saved-payload publication retries. Different filings/snapshots/runs
are independent even for equal EPS. New work/record namespaces preserve legacy
records without migration or automatic republication. A crash before saving the
response can repeat inference. Schemas/examples under `docs/contracts/` are
specifications; they are not loaded by this implementation.

## Current implementation

The first implementation lives in `src/finbot_earnings/processing/`, separate from
the existing artifact POC. It processes a complete selected filing snapshot with
injected document, model and publication adapters. It has no AWS SDK or live-model
dependency and does not load `.env`.

## Run and inspect

After installing the package and development dependencies as described in README:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m finbot_earnings.processing.demo \
  --output-dir /tmp/finbot-earnings-filing-demo
```

Use a new output directory. The synthetic demo reads three local files, calls a
fixture model once, persists one validated event, publishes to a local JSONL file
and acknowledges a duplicate without another read, model call or publication.
Inspect `filing-ready.json`, `synthetic-documents/`, `processing-record.json`,
`processing.sqlite3` and `published-events.jsonl`. These are local demo outputs,
separate from the POC registry and real shared data.

## Application boundary

`FilingPipeline(repository, documents, model, publisher, config).process(message)`
accepts either raw FilingReady JSON or an SNS Notification containing JSON in
`Message`. It independently verifies the producer's schema and manifest hash;
tests include the producer's golden hash vector without importing its package.
An optional expected topic ARN checks wrapped notifications. This is contract
validation, not authentication; the AWS queue policy owns transport access.

`DocumentSource.read` must perform bounded I/O and return the immutable bytes.
Every manifest document is loaded and checked against its stored size before
`FilingModel.classify_and_extract` receives one `ModelRequest` with all original
bytes and source labels. There is no truncation or per-document extraction call.
`EventPublisher.publish` receives the already serialized saved payload and returns
an acknowledgment ID. `SQLiteProcessingRepository` is the durable reference
implementation of `ProcessingRepository`. The DynamoDB adapter implements the
same boundary; [AWS_RUNTIME.md](AWS_RUNTIME.md) describes the cloud composition.

Defaults: 16 documents, 4 MiB aggregate input, 64 KiB saved model result, 32 facts,
three failures per stage and a 300-second claim. All are finite configurable
limits, not provider capacity claims. Supported inputs are UTF-8 HTML/plain text
and PDF bytes. The configured Nova runtime further limits inputs to five documents
and 128 KiB total document bytes. Supporting JPEG/PNG/GIF inputs are separate:
20 images, 3,750,000 bytes each, 12 MiB total, at most 8000 pixels per side and
one frame. Pillow verifies rasters before inference. All image bytes retain their
manifest identity and enter the same model request; no pages are truncated.
Unsupported formats, empty documents or an oversized
whole snapshot finish as `review_required` without a model call. Missing objects
or stored-size mismatches are technical failures.

## Evidence policy: `explicit-prose-v1`

This initial policy deliberately accepts a narrow fixture-verifiable subset:

- A document heading starts with the upstream company name and identifies results,
  earnings, financial information or a report. Explicit period headings establish
  one current end date per period kind, no later than the filing date.
- Evidence matches a complete short non-table prose block after whitespace/case
  normalization. It contains the original explicit period wording, diluted earnings
  or loss per share, GAAP/adjusted/non-GAAP basis, explicit currency and decimal.
- Currency, sign and reported precision match the candidate. Loss wording and
  parentheses preserve a negative sign. Guidance/forecast/negation qualifiers,
  scaled units, basic EPS and ambiguous share bases require review.
- Hidden HTML, tables, implicit currencies such as bare `$`, inferred fiscal
  periods and unsupported labels cannot establish an accepted fact. HTML views
  are for validation only; the model request retains all source bytes.
- PDF files enter the same model request, but PDF-sourced facts receive
  `pdf_evidence_requires_review` because independent PDF evidence checks are not
  implemented. They cannot become accepted facts. An invalid PDF header causes
  review before inference; provider PDF decoding restrictions still apply.
- Image files enter labeled image blocks; image-sourced facts receive
  `image_evidence_requires_review` and are withheld from accepted metrics.
  Independently supported prose facts can still pass, as with PDF evidence.

Conflicting candidate values block that reporting period, including otherwise
valid facts for it. An independent unsupported fact can be withheld while another
fact passes. Later canonical conflicts also block the affected period. Supported
quarterly and annual results become separate company-period events. Validation
is conservative rule-based acceptance, not a general financial-table parser;
evaluate and expand it using reviewed real filings before cloud activation.

## Durability, duplicates and recovery

Work identity includes `filing_id`, `snapshot_id`, `extraction_config_version`,
`run_mode` and `run_id` (default `initial`). Configuration is saved in full; reusing
an identity with changed configuration or input is rejected. Explicit experiments
use another run ID or configuration version. `evaluation` saves results but never
updates canonical events or publishes.

SQLite uses transactions for claims and all state changes. Claims expire and
every checkpoint is fenced by token and expiry. The model response is saved before
validation. Outcome, event revisions and pending publication payloads commit in
one transaction; conflicting concurrent filings reconcile against the latest
canonical revision inside that transaction. Prior revisions remain immutable.

Publication is at least once. A failure or lost acknowledgment retries the same
saved payload without reading documents or calling the model again. Completion
is acknowledged only after required publication acknowledgments are saved.
An extraction crash before response persistence may require another model call;
the implementation does not promise exactly-once inference.

`ProcessResult.acknowledge` tells the queue adapter whether processing is
finished. Non-earnings and review outcomes complete normally. Technical failures
retry within their stage budget, then remain unacknowledged with `exhausted=True`;
the SQS redrive policy must move them to its DLQ. Malformed notifications
also remain unacknowledged. No offline code sends directly to a DLQ. Explicit
`repository.rearm(work_id, now)` resets a terminal retry budget while preserving
saved model results and publications. It refuses active work. A new model run
requires a distinct identity rather than rearming the same job.

## AWS implementation

S3, Bedrock, SNS, DynamoDB and SQS Lambda adapters now exist alongside the offline
core. Python CDK and GitHub Actions define the disabled initial service and its
release process. See [AWS_RUNTIME.md](AWS_RUNTIME.md). Nova Lite is configured in source; the approved v6 baseline lives in the separate
evals package. Production-port parity, cloud setup and activation remain later milestones.
Actual live state was not inspected in this documentation session.
The local demo continues to use only its fixture model and local files.
