# Offline filing processing

Updated 2026-10-25 through Milestone 4. `FiscalConsumer` now connects the frozen
OpenAI boundary to fiscal acceptance, durable storage and `earnings.extracted`
publication. Normal tests and the demo are offline. Superseded acquisition, Nova and evaluation code is removed; historical records
and shared-data artifacts remain preserved separately.

## Run and inspect the demo

From the package root, using its own environment:

```bash
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
.venv/bin/python -m finbot_earnings.processing.demo \
  --output-dir /tmp/finbot-earnings-fiscal-demo
```

Choose a new directory. The demo uses the real frozen extractor and OpenAI SDK
over `httpx.MockTransport`, three synthetic local HTML documents and a JSONL
publisher. It makes two mocked calls: an accepted extraction and an explicit
empty-result run. It also acknowledges a duplicate without another read/call/send,
and records mixed HTML/PDF review before inference. There is one EPS-bearing event.
No `.env`, credentials, network, catalog or shared-data writes are needed.

Inspect `filing-ready.json`, `synthetic-documents/`, `processing-record.json`,
`empty-record.json`, `review-record.json`, `published-events.jsonl` and
`processing.sqlite3`. These are synthetic software checks, not quality evidence.

```bash
.venv/bin/python -m finbot_earnings.processing.operator \
  --sqlite /tmp/finbot-earnings-fiscal-demo/processing.sqlite3 list accepted
```

`earnings-ops` is the installed equivalent. Reinstall editable entry points after
pulling this change to remove the retired `earnings` and `earnings-eval` scripts.
`earnings-ops` is the only installed application command. Experiments and corpus
review belong to [finbot-filing-evals](../../finbot-filing-evals/README.md).

## Application boundary and acceptance

`FiscalConsumer(repository, documents, extractor, publisher).process(message,
run_id="initial")` independently validates FilingReady 1.0 and claims version-2
work. It calls `OpenAIFiscalExtractor.extract(filing, source, run_id=..., attempt=...)`
once per reserved attempt, saves the complete receipt before acceptance, then
commits the outcome and any immutable event/publication intent together.
`FiscalResult` exposes work ID, outcome, acknowledgment, reasons, event ID and
exhaustion. There is no evaluation mode on this boundary.

`fiscal_contract.accept` implements `fiscal-eps-acceptance-v1`: strict fiscal schema
and integer types, one period across both metric arrays, no repeated
metric/currency/period key (even equal values). Values and trailing zeroes are
retained as strings; currencies are preserved. Multiple periods/duplicates send
the whole response to review. No row salvage, share conversion, canonical merge,
prose gate, classification or independent fact verification. Financial selection
is prompt-guided; the software cannot detect a mislabeled YTD value by structure.

| Outcome | Delivery behavior |
| --- | --- |
| `accepted` | Save `earnings.extracted` 1.0, publish immediately, save acknowledgment, then acknowledge input |
| `no_eps_extracted` | Save empty arrays, acknowledge, no event or inference retry; not definitive non-earnings |
| `review_required` | Save reasons/receipt, acknowledge, no event or automatic inference retry |
| `processing_failed` | Retain checkpoint/reasons; unacknowledged for bounded recovery and eventual SQS DLQ |

Supported inputs are complete HTML plus original JPEG/PNG/non-animated GIF
snapshots. TXT, PDF, WEBP or any other unsupported selected member rejects the
**whole snapshot before inference**, including HTML with a PDF supplement. Bounds
are frozen in [EXTRACTOR.md](EXTRACTOR.md): 16 HTML, 64 images, 64 MiB total source,
2 MiB text, 96 MiB encoded request, 900,000 locally estimated tokens, and 2 MiB
native response; per-member/image/pixel limits apply too. Never truncate, resize,
omit selected members or split inference. Missing/size-mismatched objects are
technical failures. Member/bound reasons remain inspectable. Output events are
bounded to 240 KiB; overflow is review with no partial EPS publication.

## Identity, history and storage

[CONTRACTS.md](CONTRACTS.md) defines canonical identity and logical references.
`FiscalIdentity` hashes namespace, filing/snapshot, config version/content digest,
and run ID. Work, record and event prefixes are `earnings-work:v2`,
`earnings-processing:v2` and `earnings.extracted:1.0`. Different filings, changed
snapshots and explicit fresh runs publish independently even with equal EPS.
Repeated deliveries reuse the saved event bytes. `inspect` resolves processing
refs and `/input` manifest refs. No migration or republication of legacy records.

`SQLiteFiscalRepository` stores the new layout in `fiscal_v2_items` alongside any
old tables. `DynamoDBFiscalRepository` uses the existing table's `pk`/`sk` shape in
new `EPS2#` partitions. Both use the same logical transitions and tests:

| Partition | Sort key / role |
| --- | --- |
| `EPS2#WORK#<work_id>` | `STATE`: version, identity/refs, token/lease, reserved attempts, outcome/event/publication refs, failure counters and timestamps |
| `EPS2#CONFIG#<version>` | `DIGEST`: immutable global version/content mapping; changed content under an existing version is rejected across filings |
| `EPS2#BLOB#<sha256>` | `CHUNK#0000` etc.: base64 of canonical JSON byte chunks |
| `EPS2#EVENT#<event_id>` | `PAYLOAD`: immutable accepted event blob reference; no HEAD/revision |
| `EPS2#STATUS#<status>` | `<work_id>`: compact status/publication summary |

Chunks are at most 128 KiB before base64 encoding; a logical JSON blob is capped
at 24 MiB (at most 192 chunks). This accommodates the bounded exact native body,
base64 copy, parsed response, config, manifest and receipt. Chunks are written
immutably before their pointer becomes reachable. Each read verifies complete
membership, total byte count and SHA-256. Partial uploads/crashes can leave
unreferenced chunks; there is no automatic garbage collector or TTL deletion.
No partial receipt is presented as saved. Receipt overflow is an explicit failure;
no data is truncated. Old chunks/receipts/attempt reservations remain immutable.

DynamoDB commits compact state, event pointer and status insertion/removal in one
transaction, checking state version and, for owned writes, token and lease expiry.
SQLite does the same under `BEGIN IMMEDIATE`. Event/receipt blobs are staged before
that transaction, so the transaction remains below the service's item/action/byte
limits. The adapter conservatively bounds transaction items to 380 KiB and total
JSON to 3,800,000 bytes. Separate filings have no shared canonical head to contend
on. Strongly consistent status partitions support bounded key-ordered pages
(limit 1–100, opaque work-ID cursor), without scans, GSI or infrastructure changes.
The view is current per page; it is not a frozen multi-page snapshot.

## Attempts, leases and recovery

Lease: 360 seconds. Provider timeout: 120 seconds, SDK retries: zero. Each
application attempt is durably reserved before source preparation/secret access/
inference, at most three per work identity **including crashes without receipts**.
Reservations without a saved response show `usage_unknown=true`; they never imply
free usage. Source/preparation/credential failures can consume reservations without
a model call. Receipt flags distinguish known no-call outcomes. Automatic transient
retries use the next ordinal; third-attempt failure is terminal. Invalid output,
refusal, incomplete output, empty and review outcomes never trigger model repair.

Failures in persistence/publication have three failures per stage before terminal
state. A busy/expired/replaced claim is unacknowledged; all owned commits are
fenced. Response checkpoint recovery skips source/secret/provider work. Publication
retries send the identical saved canonical bytes/ID and separately store attempt
count, last start, acknowledgment and first successful acknowledgment time. A
lost acknowledgment can deliver duplicates. Exactly-once inference/delivery is
not promised; a crash before receipt persistence can require another paid attempt.

`retry` explicitly rearms failed work with the same saved configuration, retaining
receipts/events and **never resetting the three provider reservations**. A saved
configuration failure can use a remaining reservation after the operator fixes
access/billing/credentials; invalid output remains terminal on checkpoint replay.
Exhausted/invalid/review/empty cases needing inference use `reprocess` with a new
run ID. Completed accepted/empty/review outcomes cannot be rearmed as failures.

## Operator commands

Without `--sqlite`, commands use `EARNINGS_TABLE_NAME` and normal AWS identity.
Read-only inspection/list/event commands do not resolve the provider credential.
Output peeking requires `EARNINGS_OUTPUT_QUEUE_URL` or `--queue-url`.

```bash
earnings-ops inspect 'earnings-work:v2:DIGEST'
earnings-ops event 'earnings.extracted:1.0:DIGEST'
earnings-ops list review_required --limit 50
earnings-ops list processing_failed --limit 50
earnings-ops list no_eps_extracted --limit 50
earnings-ops list accepted --limit 50 --cursor 'WORK_ID_FROM_PREVIOUS_PAGE'
earnings-ops retry 'earnings-work:v2:DIGEST'
earnings-ops reprocess 'earnings-work:v2:DIGEST' --run-id manual-20261025-001
earnings-ops output --limit 10
```

`DIGEST` and cursor values above are placeholders; copy actual IDs from listing.
**`retry` may incur inference charges and/or publish a saved event. `reprocess`
requests a fresh extraction and can publish a new event.** Run IDs must be unused,
non-`initial`, 1–100 characters from letters/digits/dot/underscore/hyphen.
The complete saved manifest is reused. Inspect source membership and reasons first;
fix acquisition/unsupported-input problems upstream without removing members from
the immutable snapshot. A changed manifest is a distinct snapshot. Start with
`list review_required`, then `inspect WORK_ID` to identify the exact member/bound.
For HTML plus a selected PDF, the whole snapshot stays in review; a new run of
the same unsupported manifest does not fix it. Explicitly reprocess only after
confirming that the complete saved snapshot is supported by the selected configuration.

`output` uses `ReceiveMessage` with zero visibility timeout and no delete. It can
repeat the same messages, increments receive count, and may return fewer than the
requested limit. It reports SQS `SentTimestamp` separately from the inspected SNS
body; this is not a permanent archive or a claim of subscriber processing time.
The inspection queue and unattached operator IAM policies are defined in CDK;
deployment/setup remain Milestone 6. See [RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md).

Timing provenance includes first claim/readiness delay, reservations, receipt-save
and outcome timestamps, receipt preparation/extraction durations, last publication
start/duration and readiness-to-ack delay. These can include backlog catch-up;
`filed_at` is not discovery time. Detailed live queue/invocation metrics, alerts,
quotas and tuning remain release/operational verification.
