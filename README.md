# finbot-earnings

Status updated 2026-10-25: **migration decisions are complete; implementation of
the six-milestone migration has not started.** Start with Milestone 1 in
[ROADMAP.md](ROADMAP.md). Each milestone is intended for a separate agentic session.

This package is becoming a filing-level EPS extraction service. It will consume
complete stored snapshots from `finbot-filings`, extract reported and adjusted
diluted EPS, persist processing outcomes, and publish `earnings.extracted` events.
The priority is low end-to-end discovery, extraction and reporting latency.
Discovery and acquisition remain owned by `finbot-filings`; model experiments and
golden-data review belong to `finbot-filing-evals`.

## Implemented state versus approved target

The repository currently contains three overlapping paths. The approved target
below describes upcoming work, not functionality already available.

| Area | Implemented now | Approved migration target |
| --- | --- | --- |
| Filing processing | Complete FilingReady manifest validation, bounded input, one combined classification/extraction call, conservative evidence checks | One EPS extraction call using the tested fiscal schema; schema/business-rule acceptance with filing provenance |
| Model/input | Bedrock Nova Lite v1 (`amazon.nova-lite-v1:0`), original document bytes and supporting images | Direct OpenAI `gpt-6-luna`, v6 prompt, HTML-derived plain text plus original images; medium reasoning, 4,096 output tokens |
| Output | `earnings.validated` company/period-end events and canonical revisions | Immutable `earnings.extracted` results for each filing snapshot/configuration/run; no cross-filing merging |
| Persistence/recovery | SQLite reference store, DynamoDB adapter, leases, fenced writes, retries and saved-payload publication recovery | Adapt these guarantees to filing-specific event identity and preserve prior records |
| AWS delivery | S3/SNS adapters, SQS Lambda handler, Python CDK and GitHub CI/Deploy workflows | Retain the architecture; add direct-provider secret access and an output inspection queue |
| Operator commands | `earnings` still runs the original NVDA acquisition/watcher POC | Focused inspect/list/retry/reprocess/output-inspection CLI |
| Evaluations | Older earnings-local runner and `earnings-eval` entry point still exist | Retire them; use `finbot-filing-evals` for quality work |

The checked-in [production configuration](infra/cdk/config.prod.json) selects Nova
and sets `consumption_enabled: false`. Existing deployment documentation records
earnings as undeployed; **live AWS state has not been verified in this documentation
session**. Source configuration is not proof of deployed resources or runtime state.

The current v0 validator accepts a narrow explicit-prose subset of HTML/TXT.
PDF and image inputs can reach the model, but facts sourced from them require
review. The configured document budget is 128 KiB across at most five standalone
documents, with separate bounds including 20 supporting images. These are current
Nova implementation limits, not the approved limits for the OpenAI migration.

## Start or resume a milestone

Read [the roadmap session workflow and current checkpoint](ROADMAP.md#session-workflow),
then implement **only the first incomplete milestone**. Resume partial work on that
milestone before moving on. At its exit boundary, update both documents and leave a
durable completion record for the next session.

| Order | Milestone | Current status |
| --- | --- | --- |
| 1 | Formalize the approved contracts and documentation | Not started |
| 2 | Implement the tested extractor behind a transition boundary | Not started |
| 3 | Integrate filing-specific acceptance, storage, publication and CLI | Not started |
| 4 | Remove superseded NVDA POC and earnings-local evaluation paths | Not started |
| 5 | Verify the production port against existing quality evidence | Not started |
| 6 | Prepare the reviewed release, deploy and activate | Not started |

The roadmap contains all approved decisions, per-milestone inputs, deliverables,
checks and handoff requirements. Treat it as the source of truth for migration
intent. Older documents under `docs/` describe the previous Nova/canonical-event
design until Milestone 1 reconciles them. Updating those documents does not by
itself mean that their target behavior has been implemented.

## Approved launch behavior and limitations

These rules are approved but are not yet implemented in the current filing core:

- Publish accepted EPS directly in `earnings.extracted`, together with issuer,
  filing/snapshot, processing and timing provenance. Independent per-fact evidence
  verification is not required for launch.
- Keep the tested reported/adjusted EPS arrays, decimal precision and disclosed
  currencies. Use issuer fiscal year/quarter identity, choose one current period,
  prefer Q4 over full-year figures when both are reported, and exclude YTD,
  comparisons and guidance. Share denomination is unspecified; perform no conversions.
- Publish each filing snapshot independently. Duplicate delivery reuses its saved
  result/event ID; changed snapshots and explicit new runs remain distinguishable.
- Publish when at least one observation is accepted. Empty arrays produce
  `no_eps_extracted` without publication or an automatic inference retry.
- Support **HTML plus original JPEG/PNG/GIF supporting images**. **TXT and PDF
  are deferred.** Any unsupported selected member sends the entire snapshot to
  review before inference, including a mixed HTML/PDF package.
- Oversized complete snapshots also go to review. Never truncate documents or
  discard selected attachments. Document actual verified OpenAI bounds during
  implementation, accommodating the evaluated HON 34-image case.
- Process retained queued notifications after activation. No automatic historical
  S3 scan/backfill is part of launch.

## Quality evidence and evaluation ownership

The [experiment report](../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md)
records 83/83 fiscal EPS targets and 50/50 exact filings for the reviewed v6 Luna
run. It is the approved launch quality baseline. The sample was used during
development and does not establish unseen-filing accuracy.

Milestone 5 verifies that the production port preserves that tested behavior.
A new 20-filing study or automatic paid rerun of all 50 is not required.
Evaluation datasets, label review, model comparisons and reports stay in
[finbot-filing-evals](../finbot-filing-evals/README.md); material extraction changes
must be evaluated there.

The old local corpus instructions in [GOLDEN_DATASET.md](docs/GOLDEN_DATASET.md)
and [LOCAL_EVALUATION.md](docs/LOCAL_EVALUATION.md) are superseded for the migration.
They describe legacy tooling still present until Milestone 4 and should not be
used to restart an earnings-local evaluation campaign.

## Local setup and offline verification

Use this repository's own virtual environment. The current package requires
Python 3.11+; current CI and Lambda use Python 3.13. Node 24 is used for CDK tooling.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
git diff --check
```

The latest documentation-session check passed 171 tests. Normal tests use offline
fixtures/mocks and do not require provider credentials or shared-data writes.

The existing filing-core demo is also offline and does not load `.env`:

```bash
.venv/bin/python -m finbot_earnings.processing.demo \
  --output-dir /tmp/finbot-earnings-filing-demo
```

Choose a new output directory. It writes `processing-record.json`,
`published-events.jsonl` and `processing.sqlite3`, demonstrating one fixture-model
call, one v0 validated event and an acknowledged duplicate. This is the current
Nova-era contract demonstration, not proof of the planned `earnings.extracted`
runtime. Update the demo as the core changes in Milestone 3.

## Existing commands and configuration

- `earnings` / `python -m finbot_earnings` still enter the NVDA POC. Its
  `watch`, `poll`, `list-artifacts`, `show-timeline` and `replay` commands
  are legacy acquisition/inspection tools; they do not run the filing consumer.
- The POC loads the nearest `.env`, overriding inherited values. It uses
  `companies.toml`, `EARNINGS_DATA_DIR`, `SEC_USER_AGENT` and OpenAI settings.
  This is separate from the filing runtime, which uses CDK-provided configuration.
- `earnings-eval` / `python -m finbot_earnings.evaluation` is the legacy
  local evaluator scheduled for removal. Use the separate evals package for work
  on the approved baseline.
- `infra/cdk/config.prod.json` and the `EARNINGS_*`/`FILING_READY_TOPIC_ARN`
  runtime variables currently configure the Nova Lambda path.
  [AWS_RUNTIME.md](docs/AWS_RUNTIME.md) describes that existing implementation;
  its model, secret, queue and release instructions will be revised before deployment.

## Release destination and completion

The approved target is account `559007813222`, `us-east-1`, stack
`finbot-earnings-prod`, using the existing filing-ready topic and source bucket.
The future worker retrieves its OpenAI project credential from a new dedicated
Secrets Manager secret. An earnings-owned SQS inspection queue retains output
messages for 14 days; operational alerts go to `ilancooke@gmail.com`.

A successful-CI artifact, infrastructure diff and protected GitHub production
approval govern releases. The first deployment briefly starts with consumption
disabled for checks, then enables it. **Routine updates preserve consumption
state and do not require a disable/enable cycle.**

Scoped live integration tests have a USD 5 total API allowance, tracked in the
roadmap. Ongoing API spend is monitored/funded by the user through OpenAI's UI;
the app will not add a monthly spend cap or spend-alert system.

Milestone 6 is complete when enabled queue-triggered processing produces a real
EPS-bearing event received by the inspection queue. A disabled deployment, direct
worker invocation or successful SNS publish acknowledgment alone does not meet
that end state.

## Code and document map

| Location | Responsibility/status |
| --- | --- |
| `src/finbot_earnings/processing/` | Existing filing core, storage/adapters, validation and Lambda entry point; main migration starting point |
| `src/finbot_earnings/evaluation/` | Legacy local evaluator; remove in Milestone 4 |
| `cli.py`, `pipeline.py`, `sources/`, `extractors/` under the package | Original NVDA POC; replace/retire after the new core is covered |
| `infra/cdk/`, `scripts/`, `.github/workflows/` | Infrastructure, bundle/release tools and CI/deployment |
| [ROADMAP.md](ROADMAP.md) | Approved decisions, sequential implementation plan and durable session checkpoint |
| [FUNCTIONAL_SCOPE.md](docs/FUNCTIONAL_SCOPE.md), [V0_DECISIONS.md](docs/V0_DECISIONS.md), [CONTRACTS.md](docs/CONTRACTS.md), [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Previous target design; reconcile with approved decisions in Milestone 1 |
| [OFFLINE_PROCESSING.md](docs/OFFLINE_PROCESSING.md), [AWS_RUNTIME.md](docs/AWS_RUNTIME.md) | Existing processing/runtime behavior; retain accurate current-versus-planned status as milestones proceed |
| [Producer FilingReady contract](../finbot-filings/docs/FILING_READY.md) | Authoritative upstream input contract; owned by `finbot-filings` |
