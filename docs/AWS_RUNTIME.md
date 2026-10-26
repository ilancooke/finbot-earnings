# AWS runtime and release setup

Updated 2026-10-25 through Milestone 3. The SQS handler now selects the fiscal
consumer. Its source wiring and SDK/Secrets Manager interactions are tested offline;
**the committed CDK configuration, dependency bundle and permissions still describe
Nova and are not ready to deploy this consumer**. Consumption remains disabled in
source. No actual AWS/GitHub deployment state, credential or provider access has
been inspected. Milestone 6 owns deployable packaging, IAM, resource setup and
protected release/activation.

## Implemented fiscal entry point

`finbot_earnings.processing.lambda_handler.handler` validates the expected SQS
queue and wrapped SNS FilingReady origin, checks remaining invocation time, and
returns partial batch failures. Cached `runtime()` builds `FiscalConsumer`,
`DynamoDBFiscalRepository`, `FiscalS3Documents`, `SecretFiscalExtractor` and
`SNSPublisher`. Clients use connect/read timeouts of 3/10 seconds and two total
AWS SDK attempts. The frozen provider client uses 120 seconds and zero SDK retries.
No clients, `.env` or credentials are resolved at import time.

The dedicated secret is resolved only for a reserved extraction attempt through
`GetSecretValue(SecretId=<ARN>, VersionStage="AWSCURRENT")`. Its **SecretString is
the plain OpenAI project credential**, not JSON. The provider client is scoped to
that attempt, so redrive sees a rotated key. Credential values never enter config,
receipts, errors or logs. Inspection/duplicate/publication recovery does not fetch
the secret. Secure population and runtime permissions remain Milestone 6.

| Environment variable | Fiscal source runtime contract |
| --- | --- |
| `EARNINGS_TABLE_NAME` | Existing earnings table with `pk`/`sk`; new `EPS2#` namespace |
| `EARNINGS_SOURCE_BUCKET` | Only allowed source bucket |
| `FILING_READY_TOPIC_ARN` | Required wrapped-notification SNS origin |
| `EARNINGS_QUEUE_ARN` | Required SQS event-source ARN |
| `EARNINGS_TOPIC_ARN` | Output topic for `earnings.extracted` |
| `EARNINGS_FISCAL_CONFIG_SHA256` | Must equal packaged frozen configuration digest; fail closed on mismatch/missing value |
| `EARNINGS_OPENAI_SECRET_ARN` | Complete dedicated Secrets Manager secret ARN |
| `EARNINGS_OUTPUT_QUEUE_URL` | Operator output peeking only; optional for worker |

Current frozen config `eps-openai-luna-v6-v1` digest:
`e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097`.
The fiscal path does not interpret legacy `EARNINGS_EXTRACTION_CONFIG` as its
configuration. Deploying old CDK environment/bundles with this handler would fail;
finish Milestone 6 before release. Actual quotas/access remain unverified.

## Storage, formats, recovery and operations

[Fiscal offline processing](OFFLINE_PROCESSING.md) documents physical keys/chunks,
status partitions, atomic state/event/intent commits, CLI syntax and tests.
[CONTRACTS.md](CONTRACTS.md) defines identity and acceptance. Receipts use bounded
128-KiB content-addressed chunks with a 24-MiB logical cap. Commit their pointers
only after all chunks persist. Status changes and accepted event pointers commit
atomically with version/token/lease fencing. Legacy `JOB#` / `EVENT#` records remain
untouched. No schema migration, scans or new GSI is required.

Accept single-period fiscal arrays after schema/business rules, preserving decimal
strings/currencies and source provenance. Independent fact evidence is not checked.
Empty arrays complete `no_eps_extracted`, no event or automatic inference retry.
HTML plus original JPEG/PNG/non-animated GIF is supported. Any selected TXT/PDF or
unsupported/oversized member sends the **whole snapshot** to review before inference,
including mixed HTML/PDF; never truncate or omit members. The frozen limits are
16 HTML, 64 images, 64 MiB total source, 2 MiB text, 96 MiB encoded request, 900,000
locally estimated tokens, 2 MiB native response and 240 KiB event; all per-member,
image/pixel limits remain in [EXTRACTOR.md](EXTRACTOR.md).

Lease is 360 seconds; durably reserve at most three application attempts before
preparation/secret/provider work, including crashes. SDK retries are zero. Per-stage
persistence/publication failures exhaust after three; explicit `retry` rearms stage
recovery without resetting provider reservations. Saved-response recovery avoids
S3/provider work; saved-event publication resends identical bytes without inference.
Accepted/empty/review completion acknowledges normally; failed/busy/stale processing
remains unacknowledged for the input queue's eventual DLQ. Invalid notifications
have no valid work identity: safe handler diagnostics and the queue/DLQ retain them.

Read-only `earnings-ops inspect/event/list` uses table access without provider secret
access. `retry` and `reprocess --run-id ...` can incur charges/publish; `output` peeks
SQS without deletion. See exact commands and caveats in OFFLINE_PROCESSING. Output
inspection retains queue send time separately from view time. The output queue is
not deployed by this milestone. Timing records include receipt stages, first-claim
and outcome checkpoints, publication attempt count/start/ack, readiness-to-ack and
last publication duration. Actual queue/invocation metrics and alert wiring remain
release work. Separate catch-up delay from fresh steady-state latency; do not infer
discovery time from SEC `filed_at`.

## Remaining release work — Milestone 6

Retain producer SNS → earnings SQS → Python Lambda → earnings SNS → inspection SQS.
Use account `559007813222`, `us-east-1`, stack `finbot-earnings-prod`, producer topic
`finbot-prod-filing-ready` and configured source bucket
`finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua`. Verify actual state read-only;
source configuration is not evidence of deployed resources. Preserve stateful IDs.

- Package pinned OpenAI/HTTP/parser/schema/Pillow dependencies for Python 3.13
  Linux x86_64, test imports and Pillow decoding in the Lambda container, rebuild
  source assets, synthesize and verify the release manifest. Remove unused Bedrock
  permissions/bundles after Milestone 4 cleanup; update old CDK config to fiscal env.
- Define a dedicated secret and scoped `secretsmanager:GetSecretValue` permission
  (and KMS decrypt if applicable); securely populate plain SecretString. Never put
  its value in Git, chat, commands, logs or release evidence.
- Define earnings-owned output inspection SQS/subscription with 14-day retention,
  scoped SNS delivery policy and operator access. Verify actual receipt beyond SNS
  acknowledgment. Read-only inspection needs GetItem/Query, recovery additionally
  needs writes/transactions, source reads, dedicated secret access and output publish;
  queue peeking needs ReceiveMessage. Finalize least-privilege IAM in the release.
- Complete processing/delivery/DLQ/input-delay/worker-error alarms and SNS email to
  `ilancooke@gmail.com`; confirm subscription and delivery. No app spend caps/alerts.
- Verify provider quotas, upstream image-compatible contract and object access,
  GitHub OIDC roles, protected production environment and exact successful-CI
  artifact/diff. Milestone 5 parity evidence precedes this release work.

First deployment starts disabled once; then verify provider/secret/alarm/output,
inspect backlog age/size and estimated catch-up usage/time, and release enabled.
Process all retained queued notifications: no silent purge/skip or historical S3
scan. Protected GitHub production approval gates each concrete release. Ordinary
updates preserve consumption state; no forced disable/enable cycle. Pauses are
explicit. Rollback must be compatible with both stored versions and consumption
state, preserving history. A completed release requires **real enabled SQS-triggered
EPS processing and inspection-queue receipt**; direct invocation or publish ack
alone is insufficient. Scoped live tests share USD 5 cumulatively; this milestone
spent USD 0. Ongoing OpenAI funding is user-managed through its UI.

## Legacy boundary retained until Milestone 4

The old `operation=evaluate` handler deliberately uses `legacy_runtime()` and
remains publication-free. Nova pipeline/repositories, the NVDA POC, local evaluator,
old entry points, dependencies and tests remain pending the explicit cleanup
milestone. They do not implement fiscal events. The historical baseline below
records existing build/CDK/release tooling and is **not a fiscal deployment recipe**.

## Legacy Nova configuration and build baseline

Current-code baseline: implemented and tested offline, 2026-10-15. Historical
documentation records earnings as undeployed; actual AWS state has not been
verified in the 2026-10-25 Milestone 1 documentation session. The committed configuration disables queue consumption and selects
Amazon Nova Lite (`amazon.nova-lite-v1:0`) in `us-east-1`. The artifact POC and local filing demo remain usable.

## Legacy build configuration and local checks

From this repository root:

```bash
.venv/bin/python -m pip install -e '.[dev]'
npm ci --ignore-scripts --no-audit --no-fund
export JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii
.venv/bin/python -m pytest
.venv/bin/python scripts/build_lambda.py
npm run synth
.venv/bin/python -m scripts.release_manifest
```

Use Node 24 and Python 3.11+ locally; CI and Lambda use Python 3.13. The asset
builder downloads the pinned SDK and Pillow wheels for Linux x86_64, adds the application and
verifies imports in isolation. Python 3.13 runs on Amazon Linux 2023/glibc 2.34;
the builder accepts manylinux_2_28 and manylinux2014 wheels. Pillow contains native
code, so validate its image decoder in the official Python 3.13 x86_64 Lambda
container as well as checking host imports. The SDK dependency set is pure Python. It excludes
the legacy POC's OpenAI dependencies. Synthesis uses explicit account/region and
no AWS lookups. Neither command deploys resources or invokes a model. Source changes
require rebuilding the asset before synthesizing.

`infra/cdk/config.prod.json` contains account/region, stack name, producer topic,
existing source bucket, extraction configuration and consumption state. Override
the configuration path with `FINBOT_EARNINGS_CONFIG` and the generated asset path
with `FINBOT_EARNINGS_ASSET` for local synthesis. CI builds the committed production
configuration. No secrets or AWS profiles belong in it.

The initial adapter uses Nova Lite in-region with its exact foundation-model ARN
in `bedrock_resource_arns`. Extraction version `eps-nova-lite-images-v1` pins prompt
`eps-nova-tool-v2`. Nova uses constrained tool inputs for structured extraction;
it does not use Converse `outputConfig.textFormat`. A replacement model needs a
verified adapter, model/region capabilities and explicit invocation ARNs.
For this pre-activation Nova baseline, consumption remains disabled. Bump the extraction version when
model, prompt, inference limits or validation settings change. The full
configuration is saved and checked against work identity to catch accidental reuse.

Supporting JPEG/PNG/GIF bytes use labeled Converse image blocks, separately from
the five document blocks. Bounds are 20 images, 3,750,000 bytes per image, 12 MiB
aggregate raster bytes, 8000 pixels per side and one frame. A conservative encoded
payload check reserves space below Nova v1's 25-MB request limit. Invalid or
excessive inputs go to review before a paid call; never drop pages to fit. Visual
facts receive `image_evidence_requires_review` and cannot become accepted metrics.
The legacy v1 prompt remains supported only for image-free snapshots. Evaluation
receipts hash the actual selected prompt. These behaviors are tested with SDK
Stubber and local synthetic images, without invoking Bedrock.

Runtime configuration is supplied by CDK, without `.env` loading:

| Environment variable | Meaning |
| --- | --- |
| `EARNINGS_TABLE_NAME` | Earnings-owned DynamoDB table |
| `EARNINGS_SOURCE_BUCKET` | Existing filings bucket; other buckets are rejected |
| `FILING_READY_TOPIC_ARN` | Expected upstream SNS notification origin |
| `EARNINGS_QUEUE_ARN` | Expected SQS event source |
| `EARNINGS_TOPIC_ARN` | Validated earnings SNS topic |
| `EARNINGS_EXTRACTION_CONFIG` | JSON representation of `ExtractionConfig` |

The current runtime budget is 128 KiB aggregate HTML/TXT/PDF, five documents,
4,096 output tokens and a 64 KiB saved response. The five-document cap follows
Nova v1; the adapter also bounds each document to 4.5 MB. The smaller aggregate
budget is provisional and needs tuning on real filings. Every file enters the
same request as original bytes in a Converse document block, with neutral document
names mapped to artifact IDs and filenames in the accompanying context. HTML/TXT
must be UTF-8 for the evidence validator. Unsupported/oversized snapshots receive
review; missing objects retry. No attachment is silently omitted or truncated.

The narrow `explicit-prose-v1` validator checks HTML/TXT evidence. It does not parse
PDF evidence: PDF-sourced facts are retained with `pdf_evidence_requires_review`
and cannot establish accepted facts. Independently supported HTML/TXT facts may
still pass; material candidate conflicts block the affected period. PDF-only
earnings results require review. Evaluate this policy before activation.

## Runtime and storage behavior

S3 object keys are URI-decoded once; streaming reads are bounded and always closed.
The worker has GetObject access only to the configured source bucket. For SSE-KMS
objects, configure `source_kms_key_arn` and ensure its key policy permits the new
worker role. The source bucket and producer SNS topic remain outside this stack.

Bedrock Converse defines one `report_earnings` tool whose input schema is the
minimal EPS schema, and forces it with `toolChoice.tool.name`. The adapter accepts
exactly one matching `toolUse` with `stopReason=tool_use` and reads its `input`.
There is no function execution, tool-result round trip or repair call. Missing,
multiple, wrong-name or incomplete tool responses fail. Schema-invalid input
objects are saved and rejected by application validation.

The request has an explicit output-token limit and versioned system prompt. SDK
inference retries are disabled; the persisted application retry budget owns
retries. Throttling/timeouts retry; configuration/access errors and incomplete
output do not loop. Raw provider error text and document bodies are not logged.

The DynamoDB table uses `pk`/`sk` and no scans or secondary indexes:

| Partition | Sort key | Stored record |
| --- | --- | --- |
| `JOB#<work_id>` | `STATE` | Configuration, identity, lease/token, attempt/version counters, completion and publication references |
| `JOB#<work_id>` | `INPUT` | Immutable FilingReady JSON |
| `JOB#<work_id>` | `RESPONSE` | Immutable model result, usage and timing |
| `EVENT#<event_id>` | `HEAD` | Latest canonical revision number |
| `EVENT#<event_id>` | `REV#<10-digit revision>` | Immutable saved payload plus publication acknowledgment/time |

Reads are strongly consistent. Each state mutation checks its version; owned
checkpoints also check claim token and expiry. Completion atomically commits all
event changes and the job outcome while checking every previously read head.
Concurrent conflicts re-read and reconcile, preserving earlier revisions. A saved
revision doubles as its publication intent, avoiding a second payload copy.
Publication retries load the identical payload without S3 reads or inference.
The adapter rejects oversized individual items and transactions conservatively
before calling DynamoDB; it never partially commits a filing's periods.

CDK defines a protected, retained table with point-in-time recovery, retained
14-day input/failure queues, a separate SNS-delivery failure queue, validated and
alarm SNS topics, and 30-day JSON logs. Runtime permissions target the specific
table, bucket, topic and model ARNs. SNS SendMessage policies restrict both source
topic and account. There is no producer-resource replacement or cross-stack export.

Lambda uses a retained immutable version behind `production`. SQS targets that
alias, batch size 1, maximum/reserved concurrency 2, 300-second function timeout,
360-second lease, 1,800-second visibility and five receives before DLQ. The handler
returns partial failures for retry/busy/exhausted jobs and acknowledges completed
review/non-earnings outcomes. Less than 240 seconds remaining defers a message.
Structured outcome logs complement alarms for both failure queues, 15-minute input
age and Lambda errors. Input-age alarms may fire while consumption is disabled.

## Existing release tooling and legacy evaluation endpoint

Initial setup is separate from local implementation. Configure a protected GitHub
`production` environment requiring approval and restricting deployment to `main`.
Create repository-specific OIDC roles and repository variables:

- `EARNINGS_PLAN_ROLE_ARN`: trust this repository's `main` ref. Allow read-only
  CloudFormation inspection and required CDK bootstrap lookup-role access.
- `EARNINGS_DEPLOY_ROLE_ARN`: trust only this repository's `production` environment.
  Allow the scoped CDK bootstrap publishing/deployment roles and the CloudFormation
  execution role needed for the earnings stack. Scope producer access to SNS
  subscription management on the existing filing-ready ARN. Do not grant management
  of the producer stack or raw bucket.

Both OIDC trusts must constrain `aud` to `sts.amazonaws.com` and `sub` to the
specific repository/ref or environment. Review bootstrap execution permissions,
role trust and alarm subscriptions during setup. No long-lived AWS keys are needed.

CI runs offline tests, package builds and CDK synthesis without AWS credentials.
It retains a self-contained `earnings-release-<commit>` artifact including the
cloud assembly, bundled Lambda asset, package distributions and release manifest.

Manually dispatch **Deploy** from `main`, optionally selecting a full main commit
SHA. It requires successful push CI for that exact commit and downloads its
artifact and verifies its assembly checksum. The prepare job shows a read-only
template diff and the release manifest.
After reviewing those results, approve the production job. It deploys that same
assembly, uploads assets through CDK and records stack outputs/Lambda version.
Deployments are serialized. No operator digest copying or separate code deployment
is required. Workflow dispatch and environment approval happen in GitHub; the
current task has not dispatched either workflow.

The current handler implements an explicit evaluation operation; a deployed alias
would accept it using configured Nova Lite. This endpoint is legacy and scheduled
for Milestone 4 removal; do not deploy/invoke it as the new migration verification:

```json
{"operation":"evaluate","run_id":"reviewed-corpus-v1","filing":{}}
```

The [local evaluation runner](LOCAL_EVALUATION.md) also remains implemented until
Milestone 4, but its migration instructions are superseded. Use the separate evals
package for quality work and the approved saved v6 baseline.

Replace `filing` with a complete valid FilingReady payload. Invoking this endpoint
reads S3 and makes a paid model call; it records legacy evaluation results without
canonical changes or publication. Normal tests/deployment do not invoke it. This
is not the approved launch-quality or activation procedure; use Milestones 5–6
and the target prerequisites above. Disabled consumption still permits SNS to
enqueue new notifications, retained for 14 days.

To pause, release a configuration with consumption disabled. For rollback, dispatch
a compatible earlier main commit whose CI artifact is retained, review the diff
and approve deployment. This restores its code/configuration and alias through CDK;
it does not erase processing records or event revisions. Check data/configuration
compatibility and the earlier consumption setting before rollback.

Legacy repository-only inspection/redrive is superseded by the fiscal CLI above. Repository methods
`get_job`, `event` and `rearm` are available to an operator adapter. Rearm a terminal
job before explicitly redelivering it; retain saved results/outbox payloads. A new
inference experiment needs a different run/configuration identity. SNS-delivery
failures have no job yet and must be inspected separately from processing failures.

AWS references: [Nova structured tool inputs](https://docs.aws.amazon.com/nova/latest/userguide/prompting-structured-output.html),
[Nova tool choice](https://docs.aws.amazon.com/nova/latest/userguide/tool-choice.html),
[Nova document limits](https://docs.aws.amazon.com/nova/latest/userguide/modalities-document.html),
[transaction constraints](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html),
[Lambda/SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html),
[CDK assets](https://docs.aws.amazon.com/cdk/v2/guide/assets.html).
