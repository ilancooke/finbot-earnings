# AWS runtime and release setup

Updated 2026-10-25 through Milestone 4. The SQS handler now selects the fiscal
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

## Package and build boundary after cleanup

Only the filing consumer runs in Lambda. The evaluation endpoint, Nova adapter,
old pipeline/repositories, NVDA watcher and local evaluation runner are removed.
Raw FilingReady or `operation=evaluate` direct invocations without a nonempty
SQS batch are rejected. Production fresh runs remain explicit through
`earnings-ops reprocess`; they are not an evaluation mode. Use
[finbot-filing-evals](../../finbot-filing-evals/README.md) for experiments, corpus
review and quality reports. No historical operational data was deleted.

`pyproject.toml` pins the fiscal extractor dependencies and exposes only
`earnings-ops`. The Lambda manifest currently contains the retained AWS SDK and
Pillow dependency closure; none is exclusive to the removed paths. It still lacks
the complete fiscal Linux dependency set. The builder copies only current source
and performs a lazy handler-import check; that check alone does not establish
that the frozen extractor or native image decoder works in Lambda. Milestone 6
must finalize and verify the bundle before any deployment.

`infra/cdk/settings.py` temporarily owns `LegacyExtractionSettings`, a validation
shape for the unchanged old CDK configuration. It has no inference or evaluation
behavior and is not imported by the application. This preserves offline synthesis
and stateful resource definitions during cleanup. Replace that compatibility shape,
old model environment and Bedrock permissions with fiscal configuration in
Milestone 6. No cloud resource or deployment configuration was changed here.

## Retained release tooling

CI runs offline tests and package builds, then builds a Linux asset, synthesizes
CDK without lookups and records a release manifest. The existing self-contained
`earnings-release-<commit>` artifact contains the cloud assembly, Lambda asset,
distributions and manifest. Current packaging/configuration is pending the
Milestone 6 changes above; a successful synthesis alone is not fiscal readiness.

The manually dispatched Deploy workflow requires successful push CI for the exact
main commit, downloads and verifies that artifact, then shows its manifest and a
read-only infrastructure diff. The protected GitHub `production` environment gates
the job that deploys the same assembly. Deployments are serialized. Preserve this
review flow and immutable Lambda version/production alias behavior.

GitHub setup still needs repository-scoped OIDC plan/deploy roles, variables
`EARNINGS_PLAN_ROLE_ARN` and `EARNINGS_DEPLOY_ROLE_ARN`, main-ref/environment trust
and confirmed protected production approval. Inspect the actual setup during
Milestone 6; neither workflow dispatch nor deployment occurred in cleanup.
