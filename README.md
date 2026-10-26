# finbot-earnings

Status updated 2026-10-25: **Milestones 1–3 are complete.** The fiscal filing
consumer now integrates the tested extractor, acceptance, filing-specific storage,
publication recovery, Lambda source wiring, offline demo and operator CLI.
Next is **Milestone 4 — legacy cleanup** in [ROADMAP.md](ROADMAP.md).
Each milestone is intended for a separate agentic session.

This package consumes complete stored FilingReady snapshots from `finbot-filings`,
extracts reported and adjusted diluted EPS, persists all outcomes and publishes
immutable `earnings.extracted` results. Low discovery-to-reporting latency is a
priority. Discovery/acquisition belongs to `finbot-filings`; quality experiments
and golden-data review belong to `finbot-filing-evals`.

## Implemented state and remaining migration

| Area | Implemented now | Remaining work |
| --- | --- | --- |
| Filing processing | `FiscalConsumer`: frozen direct OpenAI `gpt-6-luna` v6 extractor, schema/business acceptance, complete snapshot provenance | Milestone 5 verifies production-port parity evidence |
| Output | `earnings.extracted` / `1.0`, immutable per snapshot/config/run, EPS arrays directly in event | Live delivery verification in Milestone 6 |
| Storage/recovery | SQLite and DynamoDB version-2 adapters, bounded receipt chunks, status queries, fenced writes, durable attempts, identical saved-payload recovery | Inspect actual stored cloud state before release |
| AWS source wiring | SQS Lambda handler builds fiscal consumer; lazy dedicated Secrets Manager credential access | Milestone 6 updates old CDK config, Linux dependencies, IAM, secret, inspection queue and alarms |
| Operator commands | `earnings-ops` inspect/event/list/retry/reprocess/output | Production operator permissions and live setup in Milestone 6 |
| Legacy paths | Nova pipeline/stores, NVDA acquisition POC, `earnings`, `earnings-eval`, local evaluator and evaluation endpoint remain separate | Remove obsolete source/commands/dependencies in Milestone 4; preserve historical data |

**The committed production configuration and Lambda dependency bundle still select
Nova and disable consumption. They cannot deploy the new source runtime as-is.**
The fiscal runtime requires new digest/secret environment variables and dependencies;
Milestone 6 finalizes these after cleanup and parity checks. No deployment or cloud
state has been verified here. Source configuration is not proof of deployed state.

## Start or resume a milestone

Read [the roadmap workflow and current checkpoint](ROADMAP.md#session-workflow),
the approved decisions, the latest completion record and the next milestone's
inputs. Implement only the first incomplete milestone, resume partial work there,
verify its exit criteria, update both documents and append the handoff, then stop.

| Order | Milestone | Status |
| --- | --- | --- |
| 1 | Formalize approved contracts and documentation | Complete |
| 2 | Implement tested extractor behind transition boundary | Complete |
| 3 | Integrate acceptance, filing-specific persistence, publication and CLI | Complete |
| 4 | Remove superseded NVDA POC and earnings-local evaluation paths | Not started |
| 5 | Verify production port against existing quality evidence | Not started |
| 6 | Prepare reviewed release, deploy and activate | Not started |

## Processing and limitations

`processing.fiscal_consumer.FiscalConsumer` validates complete FilingReady 1.0,
reserves work/attempts, calls the frozen `processing.fiscal.OpenAIFiscalExtractor`,
saves its exact native response/receipt, applies `fiscal-eps-acceptance-v1`, and
commits outcome plus event/publication intent atomically. The new contract is
[CONTRACTS.md](docs/CONTRACTS.md); storage/CLI details are in
[OFFLINE_PROCESSING.md](docs/OFFLINE_PROCESSING.md).

- Preserve reported/adjusted diluted EPS arrays, decimal strings/trailing zeroes,
  signs, disclosed currencies and issuer fiscal identity. Select one current
  period; prefer Q4 over full-year when both appear. Exclude YTD/comparisons/guidance.
  Share denomination is unspecified; no conversion or independent fact verification.
- Nonempty valid single-period output publishes immediately after persistence.
  Empty arrays complete `no_eps_extracted` without event or automatic inference
  retry; this is not a definitive non-earnings classification. Duplicate observation
  keys or multiple periods send the whole output to review; no row salvage.
- **HTML plus original JPEG/PNG/non-animated GIF images** is supported. **TXT/PDF
  and other formats are deferred.** Any unsupported selected member sends the
  whole snapshot to review before inference, including mixed HTML/PDF.
- Oversized complete snapshots go to review with member/bound diagnostics. Never
  truncate documents, transform images, omit selected attachments or split extraction.
- Different filings/snapshots/configurations/fresh runs publish independently even
  with equal EPS. Repeated delivery reuses saved result/event ID. Publication retries
  send identical saved bytes without source reads, credential access or inference.
- New `earnings-work:v2`, `earnings-processing:v2` and `EPS2#` storage namespaces
  preserve legacy jobs/events without migration, merging or automatic republication.

Frozen `eps-openai-luna-v6-v1` bounds: 16 HTML, 64 images, 16 MiB per HTML,
64 MiB total source, 2 MiB prepared text, 8 MiB/image, 48 MiB total images,
16 million pixels/8,192 longest-side pixels per image, 96 MiB encoded request,
900,000 locally estimated tokens, 2 MiB native response and 64 KiB extraction.
Events are bounded to 240 KiB. Receipts use immutable 128-KiB byte chunks, with a
24-MiB cap per logical JSON blob. See [EXTRACTOR.md](docs/EXTRACTOR.md) for exact
settings/pins, per-bound reasons and estimate limitations. All 50 saved inputs
fit offline, including HON's 34 original images; this is not live provider proof.

At most three application attempts are durably reserved per identity before
preparation/secret/provider work, including crashes. SDK retries are zero, provider
timeout 120 seconds, lease 360 seconds. Stage failures exhaust after three.
Redrive preserves provider reservations and saved receipts/events. A crash before
response persistence can require another paid attempt; exactly-once inference or
delivery is not promised. Unknown usage remains explicit.

## Local setup and offline verification

Use this repository's environment. Python 3.11+ is required; CI/Lambda uses 3.13,
and CDK tooling uses Node 24.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
git diff --check
.venv/bin/python -m finbot_earnings.processing.demo \
  --output-dir /tmp/finbot-earnings-fiscal-demo
```

Choose a new demo directory. It uses the real frozen extractor/SDK over mocked
HTTP: two mocked calls produce an accepted event and a separate empty run;
a duplicate is acknowledged without another read/call/send, and mixed HTML/PDF
is reviewed before inference. Inspect JSON records, `published-events.jsonl` and
`processing.sqlite3`. No credentials, provider calls or shared-data writes.
Milestone 3 verification results are recorded in the roadmap completion record.

## Operator commands and runtime configuration

`earnings-ops` (or `python -m finbot_earnings.processing.operator`) does not load
`.env`. Without `--sqlite`, it uses AWS identity and `EARNINGS_TABLE_NAME`.

```bash
earnings-ops inspect 'earnings-work:v2:DIGEST'
earnings-ops event 'earnings.extracted:1.0:DIGEST'
earnings-ops list review_required --limit 50
earnings-ops list processing_failed --limit 50
earnings-ops list no_eps_extracted --limit 50
earnings-ops retry 'earnings-work:v2:DIGEST'
earnings-ops reprocess 'earnings-work:v2:DIGEST' --run-id manual-20261025-001
earnings-ops output --limit 10
```

Copy real IDs from listings; `DIGEST` is a placeholder. Listing supports `--cursor`
and 1–100 rows per page using strongly consistent transactional status partitions,
without scans or a new GSI. Inspection exposes complete input/config, exact saved
response, outcome/reasons, attempt/usage and timing provenance, and resolves event
processing/manifest refs. `--sqlite PATH` reads an offline version-2 database.

**`retry` resumes failed checkpoints and may incur inference charges or publish.
`reprocess` requests a fresh extraction/new event identity and can incur charges.**
It requires an unused non-`initial` run ID and reuses the complete saved manifest.
Completed accepted/empty/review outcomes require a fresh run. Inspect unsupported
members/bounds before fixing input upstream; do not discard selected files.
`output` peeks without deleting, can repeat messages, and increments receive count;
SQS send time is separate from inspection time. The queue remains release work.

The source runtime requires `EARNINGS_TABLE_NAME`, `EARNINGS_SOURCE_BUCKET`,
`FILING_READY_TOPIC_ARN`, `EARNINGS_QUEUE_ARN`, `EARNINGS_TOPIC_ARN`,
`EARNINGS_FISCAL_CONFIG_SHA256` (matching packaged configuration) and
`EARNINGS_OPENAI_SECRET_ARN` (dedicated plain SecretString project credential).
`EARNINGS_OUTPUT_QUEUE_URL` is operator-only. Provider credentials are fetched
lazily for extraction; inspection and saved publication recovery do not read them.
See [AWS_RUNTIME.md](docs/AWS_RUNTIME.md) for the source contract, offline SDK
checks and pending CDK/packaging/IAM/release requirements.

`earnings` / `python -m finbot_earnings` still run the legacy NVDA watcher and
load the nearest `.env`, overriding inherited values. `earnings-eval` and the
publication-free legacy `operation=evaluate` endpoint remain until Milestone 4.
Their old local corpus docs are superseded; use the separate evals package.

## Quality and release boundaries

The [experiment report](../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md)
records 83/83 fiscal targets and 50/50 exact filings for saved v6 Luna run
`20261023T145725Z-9ff8c84b`. This is the approved launch baseline on a development
sample, not held-out/unseen-filing accuracy. Milestone 5 verifies production-port
parity; no new 20-filing campaign or automatic paid 50-case rerun is required.

Target release: account `559007813222`, `us-east-1`, stack `finbot-earnings-prod`,
existing producer topic/bucket, new dedicated provider secret, earnings-owned
14-day output inspection queue and alarm email `ilancooke@gmail.com`. Setup and
live readiness remain Milestone 6. Successful CI builds the exact release artifact;
review its infrastructure diff and use protected GitHub production approval.
First deployment starts briefly disabled, then backlog checks precede activation.
Routine updates preserve consumption state. Process all retained queued messages;
no automatic historical S3 backfill. Completion requires a real enabled
queue-triggered EPS event received in inspection SQS, beyond SNS acknowledgment.

Scoped API tests share USD 5 cumulatively; this milestone used USD 0 and USD 5
remains. Ongoing funding is user-managed through OpenAI's UI; no app spend cap or
spend-alert system is implemented.

## Code and document map

| Location | Responsibility |
| --- | --- |
| `processing/fiscal/`, [EXTRACTOR.md](docs/EXTRACTOR.md) | Frozen extraction/preparation/receipt boundary |
| `processing/fiscal_contract.py`, `fiscal_consumer.py` | Fiscal acceptance, identity, event construction, processing |
| `processing/fiscal_repository.py`, `fiscal_stores.py` | Shared v2 transitions, bounded blobs, SQLite/DynamoDB adapters |
| `processing/fiscal_runtime.py`, `lambda_handler.py`, `operator.py`, `demo.py` | AWS wiring, SQS handler, operator CLI and offline demo |
| Legacy `processing/pipeline.py`, stores, validation/reconciliation; top-level POC and `evaluation/` | Retained until Milestone 4 cleanup |
| `infra/cdk/`, `scripts/`, `.github/workflows/` | Existing Nova build/release assets; finalize for fiscal runtime in Milestone 6 |
| [ROADMAP.md](ROADMAP.md) | Approved decisions, milestone inputs and durable checkpoint/completion records |
| [Scope](docs/FUNCTIONAL_SCOPE.md), [decisions](docs/V0_DECISIONS.md), [contracts](docs/CONTRACTS.md), [architecture](docs/ARCHITECTURE.md) | Approved fiscal semantics and implemented boundaries |
| [Producer FilingReady](../finbot-filings/docs/FILING_READY.md) | Authoritative upstream contract, owned by filings |
