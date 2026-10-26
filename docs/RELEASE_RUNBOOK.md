# Reviewed release and initial activation

Milestone 6 is **in progress**, 2026-10-25. Local preparation is implemented;
no earnings resources have been deployed. Resume this milestone at the external
setup below. All commands run from `finbot-earnings`. Never put provider credentials
in command arguments, chat, Git, workflow inputs or release evidence.

## Observed prerequisites

Read-only AWS MCP checks used account `559007813222`, principal `codex-readonly`,
region `us-east-1`. `DescribeStacks` reports `finbot-earnings-prod` does not exist.
No earnings table, queues, dedicated secret or earnings GitHub roles were found.
There is consequently no earnings backlog to measure yet; measure again after the
disabled deployment creates the subscribed queue.

The producer topic `arn:aws:sns:us-east-1:559007813222:finbot-prod-filing-ready`
exists, with zero confirmed/pending subscriptions at inspection. The source bucket
`finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua` exists in us-east-1 and uses
AES256 server-side encryption. Its objects are under ticker prefixes, not `filings/`.
Producer task definition `finbot-prod-ingestion:32` references that topic and image
`sha256:b9882885cb763add9f0ddf5524ed6e51f95681d6adf778f6b656bd434ea007d2`.
This is a task-definition observation, not proof of a running task version.

A real immutable FilingReady 1.0 is available in producer table `finbot-prod-filings`:
filing `0000773840-26-000143`, HON, snapshot
`5e2356665a6b6d326eb81852e4d53fca331430c67ddfdfeb53be502d9cf9193e`.
Its reserved `accession_number` is
`__filing_ready__/0000773840-26-000143/5e2356665a6b6d326eb81852e4d53fca331430c67ddfdfeb53be502d9cf9193e`.
Its `event_json` retains readiness `2026-10-22T14:35:47.681581Z` and a complete
35-member manifest: one HTML plus 34 JPEGs. All 35 S3 HeadObject results match
manifest byte lengths/content types and use AES256. No source objects were changed.
A real worker GetObject/inference check remains required after deployment.

GitHub API inspection found public repository ID `1350331204`, owner ID `8453151`,
OIDC `use_default=true`, `use_immutable_subject=true`, prefix
`repo:ilancooke@8453151/finbot-earnings@1350331204`. Production environment lookup
returned HTTP 404; repository Actions variables are empty. Existing main CI
[40267303486](https://github.com/ilancooke/finbot-earnings/actions/runs/40267303486)
succeeded at `abc33ca2fd6b120f044fc0ce02b985353a439be5` before these changes;
it is **not** a release artifact for this work.

## External setup before release

The AWS owner reviews `infra/cdk/access_app.py` and its separate synthesized assembly
`build/release-access`. It imports the existing GitHub OIDC provider and creates
only earnings plan/deploy roles and policies. Do not change producer roles/trust.
Reproduce the review artifact without AWS calls:

```bash
JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii \
  node_modules/.bin/cdk synth --app '.venv/bin/python -m infra.cdk.access_app' \
  --output build/release-access --strict --no-lookups
```

After explicit bootstrap approval, an authorized AWS administrator can apply that
assembly. It is deliberately separate from the protected application release:
missing release roles cannot create themselves. Review its template/diff before
that action. The plan role allows template/stack inspection only; the deploy role
can assume the account's existing CDK deploy/file-publishing roles. Existing
`CDKToolkit` is version 32 and uses an AdministratorAccess CloudFormation execution
role. This inherits that bootstrap authority; it does not narrow the account's
existing execution role or provision another administrator policy.

The repository owner creates GitHub environment `production` with a required
reviewer and exactly one allowed deployment branch rule: branch `main`. Set
repository variables `EARNINGS_PLAN_ROLE_ARN` and `EARNINGS_DEPLOY_ROLE_ARN` from
the access-stack outputs. Deploy preflight reads these environment rules before
assuming AWS credentials. The deploy OIDC subject ends `:environment:production`;
the plan subject ends `:ref:refs/heads/main`, using the immutable prefix above.
Recheck OIDC customization if ownership or repository settings change.

Review and commit/push this implementation when authorized. No commit or push was
requested in this session. Wait for successful push CI on that exact main commit.
It must build the fiscal bundle, pass the target-container check and upload
`earnings-release-<full SHA>`. Local dirty-source artifacts are review previews;
`verify_release` intentionally refuses them for deployment.

## Build and review

```bash
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
.venv/bin/python -m build
.venv/bin/python scripts/build_lambda.py --verify-target
JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii npm run synth
.venv/bin/python -m scripts.release_manifest
git diff --check
```

The builder installs the fully pinned binary closure for Python 3.13 Linux x86_64.
The target check uses `public.ecr.aws/lambda/python:3.13`, `--network none`, read-only
mounts and asset-only imports, validates frozen config/pins and JPEG/PNG/GIF decoding.
Record the container image digest when repeating checks. Changes to frozen
extraction behavior require new attributable evaluation; dependency/platform work
must preserve [parity](PRODUCTION_PARITY.md).

Manually dispatch Deploy for the exact successful-CI main SHA. Its prepare job
verifies commit, clean source, assembly and Lambda asset checksums, packaged fiscal
digest and consumption state, then shows the read-only template diff and manifest.
The GitHub production reviewer approves that concrete release. Apply uses that
assembly without rebuilding. Retain workflow URL, manifest, diff, outputs and
Lambda alias/version. First release must have `consumption_enabled=false`.

## Disabled deployment and secure provider setup

After protected deployment, record actual stack outputs and verify the event source
mapping is disabled. The retained empty secret is named
`finbot-earnings-prod/openai-project-key`; its full ARN is `OpenAISecretArn`.
The AWS owner opens that exact secret in Secrets Manager, chooses a new secret
value in **plaintext**, and securely supplies the dedicated OpenAI project key as
the entire SecretString, without JSON or wrapping quotes. No random key is generated
by CloudFormation. Verify AWSCURRENT exists via DescribeSecret metadata; do not
retrieve or print it for inspection. Runtime GetSecretValue access is tested through
the controlled worker check. Use the same secure console flow for rotation.

The provider owner verifies project model access, funding and rate limits in the
OpenAI UI. Concurrency starts at two; ensure RPM/TPM accommodate two complete
requests and the actual issuer volume. Account limits have not been verified.
Funding is user-managed. API tests share **USD 5 cumulatively**; no live calls have
been made. Before each test reserve a conservative cost estimate including image
input/output and any remaining retry attempts. Inspect exact usage and reconcile
unknown attempts before further dispatch; stop conservatively within the allowance.
No application spend cap or spend alerts exist.

The user confirms the SNS email to `ilancooke@gmail.com`. Verify the subscription
ARN is confirmed, then test the alarm notification path with an authorized SNS
publish and record receipt. An email subscription definition alone proves neither.

Use actual outputs to set the operator environment: `AWS_REGION=us-east-1`,
`EARNINGS_TABLE_NAME`, `EARNINGS_SOURCE_BUCKET`, `EARNINGS_TOPIC_ARN`,
`EARNINGS_QUEUE_ARN`, `FILING_READY_TOPIC_ARN`, `EARNINGS_FISCAL_CONFIG_SHA256`,
`EARNINGS_OPENAI_SECRET_ARN`, and `EARNINGS_OUTPUT_QUEUE_URL`.
Attach `OperatorInspectionPolicyArn` to a deliberately selected operator identity
for GetItem/Query and non-deleting output peeks. Attach `OperatorRecoveryPolicyArn`
only to identities authorized for charged inference/publication. Policies are
unattached at creation. Provisioning secret values, replaying input, invoking the
worker, reading upstream notification records and SQS redrive require separate
explicit operator access; neither policy grants these administrative operations.

## Controlled genuine-snapshot replay

With approved live-test allowance and first-release prerequisites satisfied, fetch
the immutable producer notification named above using strongly consistent GetItem,
extract its `event_json` unchanged into a local `filing-ready.json`, and validate
it with `FilingReady.parse`. Preserve the entire original manifest, snapshot and
readiness. Do not synthesize a subset, change its source identity or publish a new
notification to the shared producer topic.

Wrap that payload for the earnings worker and save it for the explicit replay:

```bash
jq -c --arg topic "$FILING_READY_TOPIC_ARN" \
  '{Type:"Notification",TopicArn:$topic,Message:(tojson)}' \
  filing-ready.json > earnings-notification.json
```

A controlled disabled-worker smoke invocation uses an SQS-shaped `Records` envelope
around this saved wrapper, the actual earnings input queue ARN, and a unique
message ID. The handler intentionally rejects raw FilingReady/direct evaluate
requests. Record the invocation as an explicit operator replay, not a naturally
received producer notification. Inspect persisted acceptance/event/SNS acknowledgment
and output receipt. This does **not** prove the SQS trigger.

Before activation inspect input SQS visible/in-flight/delayed counts and oldest
message age. Use CloudWatch for age; a ReceiveMessage inspection changes receive
counts/visibility. Estimate backlog catch-up from observed extraction duration,
input size/usage, two concurrent workers and provider quotas; separate catch-up
latency from normal traffic. Process every retained message. Do not purge, silently
skip, or enumerate historical S3 to backfill. Resolve incompatible inputs and
funding concerns before enabling.

Change only the intended release configuration to `consumption_enabled=true`,
commit/push when authorized, wait for exact successful CI and use the same protected
Deploy review. Keep true for subsequent normal releases. To prove fresh extraction
via the trigger after the direct smoke, choose another genuine producer snapshot
whose work does not already exist; resending the direct-smoke snapshot only proves
deduplication. An authorized operator may submit its saved wrapper to the earnings
input queue explicitly:

```bash
aws sqs send-message --region us-east-1 --queue-url "$EARNINGS_INPUT_QUEUE_URL" \
  --message-body file://earnings-notification.json
```

Record the submission ID/time as operator replay. Confirm an actual event-source
mapping invocation and accepted EPS-bearing event received by inspection SQS.
Use `earnings-ops output --limit 10` and `event EVENT_ID` / `inspect WORK_ID`.
Record filing/snapshot/work/event IDs, config, persisted response/usage, publication
ack/time, queue message ID/SentTimestamp, receive metadata and inspection time.
SQS SentTimestamp is enqueue time; inspection time is not initial receipt time.
Resubmit the same wrapper and verify the saved work/event ID is reused without
another provider attempt. Do not run paid failure experiments to duplicate the
offline saved-publication-recovery evidence.

## Routine operations, pause and rollback

```bash
earnings-ops list review_required --limit 50
earnings-ops list processing_failed --limit 50
earnings-ops list no_eps_extracted --limit 50
earnings-ops inspect WORK_ID
earnings-ops retry WORK_ID
earnings-ops reprocess WORK_ID --run-id UNUSED_NON_INITIAL_ID
earnings-ops output --limit 10
```

Use real IDs from listings. `retry` can charge/publish; it preserves provider attempt
reservations and resumes failed checkpoints. `reprocess` makes a fresh paid run and
new event identity. Unsupported selected formats/bounds require upstream resolution
or a new supported snapshot, never dropping attachments. DLQ redrive is deliberate:
inspect/fix the cause, rearm failed work if appropriate, then use SQS console redrive
from FailedWork to the input queue. Redrive does not reset provider reservations.
For SNS delivery DLQs, distinguish upstream wrapped FilingReady from output raw
`earnings.extracted`; never redrive output into the input queue. Recover output
subscriber delivery using the saved immutable event, without new extraction.

A deliberate pause releases `consumption_enabled=false` through the same protected
workflow. For urgent incident pause, an authorized operator may disable the mapping
in AWS and record/reconcile that drift before the next release. Leave queues and
storage intact. Roll back through a reviewed successful-CI artifact with compatible
fiscal v2 storage and the desired consumption state. Pre-fiscal Nova artifacts are
incompatible. An older disabled artifact pauses consumption: review that field
explicitly. Normal updates have no forced disable/enable cycle.

Handler logs include work/event/outcome, queue-to-invocation delay, invocation time
and processing duration without source/secret/provider error bodies. Persisted
receipts retain preparation/extraction times and token usage/unknown flags; work
state retains first claim, outcome/publish times and readiness-to-publication delay.
Use these with Lambda duration/queue age and downstream receipt metadata. Nine
alarms cover input/output delivery DLQs, failed SNS output delivery, input age
(900 seconds), worker errors/throttles and partial-batch processing failures. Review
and empty results remain CLI-visible. No numeric latency SLA is claimed.

Milestone 6 remains incomplete until the enabled queue-triggered event and actual
inspection receipt are recorded with deployed identities and the live-test ledger.
