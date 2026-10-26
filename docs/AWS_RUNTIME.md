# AWS runtime and release setup

Updated 2026-10-25 for Milestone 1. This document separates the approved target
below from the unchanged Nova runtime/build/release tools under **Current runtime**.
No deployment, secret creation, provider call or cloud inspection occurred here.

## Approved launch target — pending implementation/release

Retain producer SNS → earnings SQS → Python Lambda → earnings SNS, with DynamoDB
processing storage and SQLite offline tests. Replace Nova inference with direct
OpenAI `gpt-6-luna`, v6 prompt, fiscal v2 schema, medium reasoning and 4,096 output
tokens. [CONTRACTS.md](CONTRACTS.md) defines new work/record namespaces, immutable
`earnings.extracted` 1.0 and `fiscal-eps-acceptance-v1`. No classification,
company-period revision/merge or independent per-fact evidence gate in the target.
The raw response/full source manifest remains inspectable through processing refs.

| Selected input | Target handling |
| --- | --- |
| HTML plus original JPEG/PNG/GIF supporting images | Tested plain-text preparation and all original images in one request |
| TXT/PDF/other unsupported member | Whole snapshot `review_required / unsupported_selected_format`, before inference |
| HTML with selected PDF supplement | Same whole-snapshot review; no partial HTML extraction/event |
| Oversized complete snapshot | `review_required / snapshot_bound_exceeded`; no truncation, discarded attachment or multi-call split |

Record artifact/filename and bound/actual/limit diagnostics. Milestone 2's isolated
extractor [freezes all bounds and dependency versions](EXTRACTOR.md): 16 HTML,
64 images, 64 MiB source, 2 MiB text, 96 MiB encoded request, a 900,000-token local
estimate and 2-MiB response, covering HON's 34-image case offline. Per-member
byte/pixel limits and the estimate's limitations are documented there.
The current Nova 128-KiB/five-doc/
20-image limits below are not the new launch limits. Invalid/missing objects follow
the contract's separate review/integrity-failure policy. Completed empty arrays
produce `no_eps_extracted`, no event and no automatic inference retry. Neither
empty nor review means definitive non-earnings.

Milestone 2 has implemented the isolated extractor, with 120-second timeout and
zero SDK retries. Milestone 3 must durably budget its three application attempts,
store full receipts beyond a single DynamoDB item's capacity, and reconcile lease/
worker timing. The current Lambda dependency manifest and handler are unchanged;
Milestone 6 must package and import-test the new dependencies on Linux.
Milestone 3 integrates storage,
consumer/demo and CLI; Milestone 4 removes POC/evaluation commands; Milestone 5
records parity with the saved checked 50-filing v6 baseline. No automatic paid
50-filing rerun or new local evaluation framework. Quality work belongs to
[finbot-filing-evals](../../finbot-filing-evals/README.md). Old evaluation invocations
below are historical implemented capabilities, not migration verification steps.

Milestone 3 must document real commands to inspect/list review, failed and empty
runs, inspect source/response/usage/timing, resume failed checkpoints, request a
fresh run and inspect output SQS. Retry resumes saved response/publication payload;
fresh extraction uses a new identity, can incur charges and can publish a new
event. Inspect the offending member/bound before explicitly reprocessing review
outcomes after a fix; do not discard the PDF/large attachment. CLI syntax is not
available yet. No target `operation=evaluate` endpoint is required.

### Target release prerequisites (Milestone 6)

- Use account `559007813222`, `us-east-1`, stack `finbot-earnings-prod`; verify the
  actual `finbot-prod-filing-ready` topic, source bucket
  `finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua`, stored state and producer
  contract before release. Preserve stateful logical IDs and old records.
- Provision a new dedicated Secrets Manager OpenAI project secret with ARN-only
  configuration and narrowly scoped runtime read permission. Securely populate
  its value; record only ARN/name/readiness, never credentials. Exact environment
  variable/physical key choices are Milestone 3/6 engineering work, not existing
  capabilities in the environment table below.
- Add an earnings-owned output inspection SQS subscription with 14-day retention
  and scoped delivery/operator access. Persist history in processing storage;
  inspection SQS is not an archive. Verify receipt beyond an SNS acknowledgment.
- Verify operational alerts for processing/delivery failures, dead letters, input
  delay and worker errors through earnings alarm SNS to `ilancooke@gmail.com`.
  Recipient confirmation and alert-path verification are required before activation.
- Retain usage/stage timing and provider quota/billing-failure recovery. User manages
  ongoing funding through OpenAI's UI; no application spend cap/alerts. Scoped live
  tests share USD 5 cumulatively across sessions; record unknown usage explicitly.
- Rebuild Linux Lambda dependencies for OpenAI/preparation; validate imports/Pillow
  decoder in target runtime, synthesize, verify manifest, and review removal of
  unused Bedrock permissions. No package assets were changed by Milestone 1.
- Verify OIDC/bootstrap roles, main CI, protected production environment and exact
  artifact/diff before required GitHub production approval. Source config is not
  proof of cloud/GitHub readiness.

First deployment alone starts disabled, then controlled live verification and
backlog inspection precede enabled release. Record backlog size/age and estimated
catch-up time/cost; process all retained notifications without silent purge/skip.
No automatic historical S3 scan. Final completion requires actual **enabled
SQS-triggered processing of a real complete snapshot and EPS event receipt in the
inspection queue**, with identities, provenance and stage timings retained. Direct
invocation or SNS publish acknowledgment alone does not satisfy this criterion.

Routine updates preserve consumption state through one normal release; do not
unconditionally disable/re-enable. Pausing is deliberate. Rollback checks stored
schema/configuration and the artifact's consumption setting, retaining prior
records and avoiding accidental restoration of a disabled setting. CONTRACTS
separates old `earnings.validated` revisions from new events without migration or
automatic republication. Release approval remains the protected workflow in D12.

## Current runtime — unchanged Nova implementation

Current-code baseline: implemented and tested offline, 2026-10-15. Historical
documentation records earnings as undeployed; actual AWS state has not been
verified in the 2026-10-25 Milestone 1 documentation session. The committed configuration disables queue consumption and selects
Amazon Nova Lite (`amazon.nova-lite-v1:0`) in `us-east-1`. The artifact POC and local filing demo remain usable.

## Current configuration and local checks

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

Selective inspection/redrive CLI tooling remains follow-up work. Repository methods
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
