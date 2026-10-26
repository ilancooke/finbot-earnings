# AWS runtime and release setup

Updated 2026-10-26: **Milestone 6 is complete.** The recovered production
stack has its SQS trigger Enabled, batch size one and maximum concurrency two,
without a Lambda reservation. Protected activation and genuine TSM queue-triggered
EPS extraction, persistence and inspection SQS receipt passed. Duplicate processing
reused the saved result with no additional provider call or publication. Secret
access and confirmed alarm-topic email are verified. Exact resource/release/usage/timing
identities are in [RELEASE_EVIDENCE.md](RELEASE_EVIDENCE.md); procedures are in
[RELEASE_RUNBOOK.md](RELEASE_RUNBOOK.md).

[Production parity evidence](PRODUCTION_PARITY.md) retains the 50 saved request/output
Linux replays and 189 members/83 observations. That offline comparison cost USD 0.
The HON direct and TSM queue tests total an estimated USD 0.008010475;
USD 4.991989525 of the shared test allowance remains, with no unknown usage.

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
the secret. CDK scopes runtime permission to that exact secret ARN; secure population and runtime retrieval are verified by the direct smoke.

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
configuration. CDK now supplies the digest and dedicated secret ARN. The direct smoke verifies provider access; user-reported model limits and
activation readiness are recorded in RELEASE_EVIDENCE.

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
inspection retains queue send time separately from view time. The output queue/operator policies are deployed and direct-smoke receipt is verified. Timing records include receipt stages, first-claim
and outcome checkpoints, publication attempt count/start/ack, readiness-to-ack and
last publication duration. Handler logs additionally record queue delay and invocation/processing timing;
nine alarms are deployed; the confirmed SNS email path was tested successfully. Separate catch-up delay from fresh steady-state latency; do not infer
discovery time from SEC `filed_at`.

## Local release implementation

Retain producer SNS → earnings SQS → Python Lambda → earnings SNS → inspection SQS.
Target account `559007813222`, `us-east-1`, stack `finbot-earnings-prod`; source
bucket/topic remain producer-owned. Existing table/queue/topic construct IDs stay
stable. `ValidatedEarnings` / `finbot-earnings-prod-validated` remains the physical
output topic name for infrastructure compatibility; its payload is `earnings.extracted`.
No old EPS records are migrated or republished.

`Settings` rejects legacy model overrides and requires the packaged fiscal digest,
earnings-owned secret name and approved email. `OpenAIProjectKey` creates a retained
empty secret, with no SecretString/random value in the template. It uses the service
managed key; the worker only gets GetSecretValue for its exact ARN. Optional source
KMS decrypt remains scoped to the configured key and S3 service. Bedrock access is
removed. Worker table access includes Query and transactional DeleteItem needed to
remove old status rows; it has no Scan or source writes.

OutputInspection retains raw EPS events for 14 days, with an SNS subscription,
source-topic/account-scoped send policies and separate output delivery DLQ. The
unattached OperatorInspection/OperatorRecovery managed policies distinguish table
and output inspection from charged inference/publication access. The runbook lists
separate administrative permissions needed for live replay and redrive.

Lambda remains Python 3.13/x86_64, 1024 MiB, 300 seconds, batch one, partial batch
responses, 1800-second input visibility and five receives before DLQ. The SQS
event-source mapping caps queue-driven concurrency at two. The function has no
reserved concurrency and shares the regional account pool; other Lambda workloads
can delay processing when that pool is exhausted. Other invocation paths do not
inherit the SQS cap. Removing the reservation does not mean setting it to zero,
which would throttle all worker invocations.
The 360-second work lease exceeds invocation timeout. These are initial bounded
settings. The user reports 2M TPM and 5,000 RPM for the chosen model; the
observed complete smoke is within these limits. Real traffic will guide tuning. Do not
claim a verified throughput estimate. Alarms cover work/input-delivery/output-delivery
DLQs, SNS output delivery failure, input age, worker errors/throttles and caught
processing failures. The email subscription is confirmed and its controlled topic test was received.
No spending alarms, caps or application funding automation are implemented.

## Packaging and release verification

Only the fiscal filing consumer runs in Lambda. Evaluation, acquisition and legacy
Nova paths remain removed. requirements-lambda.txt pins the complete runtime closure;
seven frozen fiscal pins are unchanged. build_lambda.py uses Linux x86_64 binary
wheels with no dependency resolution; --verify-target checks asset-only imports,
frozen identities, HTML and native JPEG/PNG/GIF decoding in the network-disabled
Lambda Python 3.13 container. CI requires that check. Source/dependency changes
require rebuilding before synthesis. See the runbook for commands.

CI packages the cloud assembly with its staged Lambda asset and distributions.
release-manifest.json records source commit/dirty status, asset/assembly hashes,
fiscal config/digest and consumption state. verify_release rejects dirty sources,
wrong commits/hashes and asset/template/configuration/consumption inconsistencies.
A local uncommitted manifest is a preview, never a successful-CI release.

Deploy selects successful push CI for the exact main SHA, verifies the downloaded
assembly, and shows its template diff/manifest. Preflight verifies the production
environment has required reviewers and exactly the main branch rule. The protected
environment gates apply of the same artifact. No rebuild occurs during deployment.
The separate access_app.py prepares earnings-only OIDC roles using the verified
GitHub immutable subject; it does not change producer access or apply itself.

First deployment starts disabled, then secret/provider/email checks and controlled
smoke precede backlog review and a protected enabled release. Routine updates preserve
consumption state. A completed milestone requires enabled SQS-triggered extraction
and actual inspection receipt. All these rollout checks passed, including live
duplicate reuse. Keep the committed enabled state in ordinary releases. Exact prerequisites,
operator commands, secure setup, replay, pause and rollback are in the
[release runbook](RELEASE_RUNBOOK.md).
