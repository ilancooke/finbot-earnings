# Production port parity — Milestone 5

Verified 2026-10-25. The focused production source preserves the measured v6
extraction configuration on all 50 saved filing packages. All 189 original members
were supplied in order; all 83 saved EPS observations and normalized usage values
survived replay unchanged and passed production acceptance. The full offline
suite passes **176 tests**. No runtime, prompt, schema, dependency or infrastructure
change was needed for this milestone.

This establishes implementation compatibility with the approved **development
sample**, not held-out accuracy, fresh provider behavior or deployed readiness.
Milestone 6 must build the Linux artifact and prove enabled SQS-triggered delivery
to inspection SQS. Existing CDK configuration still selects Nova and disables
consumption; it cannot deploy the fiscal runtime as-is.

## Quality baseline and immutable identities

The source [experiment report](../../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md#50-filing-luna-follow-up--2026-10-23)
identifies L5, run `20261023T145725Z-9ff8c84b`: **83/83 targets, 50/50 exact
filings**, zero extraction errors, 52 reported and 31 adjusted observations.
Its saved estimate is USD **0.159437190**, with complete response usage, and
**164.13145787734538 seconds** summed extractor duration. Those are historical
experiment measurements, not new test spend, provider invoices or production
latency. The sample was used for prompt development and model selection.

| Identity | Exact value |
| --- | --- |
| Production source | `finbot-earnings`, `main`, `e4aac9b0e15d5e10da706faed87b2dab74cd9ef1`; all application source unchanged in M5 |
| Reference source | `finbot-filing-evals`, clean `d105712812a3daaf0d958c0b9b180f41ca4703ce` |
| Saved run | `$FINBOT_DATA_ROOT/filing-evals/runs/20261023T145725Z-9ff8c84b` |
| Reviewed bundle | `$FINBOT_DATA_ROOT/filing-evals/golden/earnings-eps-50-v1` |
| Reviewed source revision | `1ba92bb772114407fe4000c9d6dd29f253df81c814db82cbc1cc4d9d922cd2c7` |
| Projected fiscal dataset revision | `48b0b27aaae67b263b409a98e193dc65c7eeab21f8f717b1de816f5a42db275a` |
| Source contract / projection | `earnings_eps.v1` → `earnings_eps.fiscal.v2`; 151 reviewed observations → 83 fiscal targets, 68 cumulative/YTD exclusions |
| Historical scoring policy | `eps_fiscal_exact.v2`; exact Decimal equality and fiscal identity |
| Candidate config | [openai-luna-6-prompt-v6-sample-50.json](../../finbot-filing-evals/configs/openai-luna-6-prompt-v6-sample-50.json); saved config digest `42b31225f4d05c21543ed30bfff5c1d7288039fedd67bd35f060d44e91f8bd02` |
| Production config | `eps-openai-luna-v6-v1`, canonical digest `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097` |
| Acceptance / event | `fiscal-eps-acceptance-v1`; `earnings.extracted` / `1.0`; processing record 2 |

The saved run, rather than mutable current labels, anchors this check. Both the
evals loader and the earnings audit verified its complete **353-file** SHA-256/size
inventory, including source documents/images, requests, native responses,
predictions, reviewed snapshot, projection, results and reports. No rescoring,
label editing, inference or historical artifact changes were performed.

| File or canonical inventory | SHA-256 |
| --- | --- |
| Saved `integrity.json` | `7c7d5df3a791fe96a9919ddb2ade91a9fb5a2638d023c74d5038a490325867e5` |
| Saved `run.json` | `564e65fe9fd38732d0d799874e381cf9148a9e9275b1b0db0bc8d19e73ab599d` |
| Saved `golden.json` | `f16774ef41312b5d0a7d4bb76a278049a266adc603c7f6cbb4dbb606c1fe7466` |
| Saved `source_snapshot.json` | `1f268e657b0d04ad1e8483ebe62c6d2d1f197c8d0be7a8a973a0b70c12bb2853` |
| Saved `target_projection.json` | `2da0b50fb0612d85f955fa988714e92fe1de43413a37f338a72de64befdc44f5` |
| Saved `results.json` | `0b63c80e7f55065bc87735da4fa0c036aac9e74fffb5dfadd4db2e6a8a61d275` |
| Prompt, source and production bytes | `54158e06ec22a876acb0272bc1674bdd5dbf0f5a489eb7d9c8c3e65fdaf40237` |
| Source and production local schema bytes | `658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94` |
| Canonical transport schema | `137dec3a52ac17713243b92ccbe5fe16184617ef1bbe09915b132095408e08bb` |
| Production preparation inventory | `5cfc53e8d4522b42d1ff69340c3861691839ae9e399fc53b32da7f56c4a6bd38` |
| Production implementation inventory | `5bbf49eee3d17a97a64904a7af3177727c92da378fdab10168b33e9c1c12de75` |
| [Reference fingerprints](parity/v6-reference.json), file bytes | `1a3b0c28c18c1db411259fd1ed0357d30e4273870b4cbc3cd656cb30eac0b289` |

[implementation.json](../src/finbot_earnings/processing/fiscal/resources/implementation.json)
contains every frozen module hash and the exact reference `direct.py`,
`bedrock.py`, `contracts.py` and `review/viewer.py` hashes. They match the saved
run's implementation inventory and current reference checkout. `load_config()`
verifies production code/resource/dependency identity before replay. The saved
`labels.schema.json` has pretty-print hash
`c96a9997522c555fdbc4e09296381ae457673cdb9c8bd1ab62229153d65b515a`;
it is structurally identical to the source schema. Serialization into actual
request instructions is covered by the complete request fingerprints.

## Comparison and compatible differences

| Boundary | Evidence and compatibility |
| --- | --- |
| Prompt and fiscal schema | Byte-exact source copies; strict quarterly/annual transport union unchanged; actual instructions/schema matched in every request. Total reported EPS, Q4 priority, YTD/comparison/guidance exclusion remain prompt-guided. |
| HTML preparation | Same html5lib body/tree cleaning, table separators, tails, whitespace and image-alt placeholders. CSS-hidden text remains retained as in the reference. All 50 request content sequences match, plus six frozen synthetic preparation fixtures. |
| Images and ordering | Original JPEG/PNG/GIF bytes, high detail, complete canonical artifact order and attachment headers. All 189 selected members retained, including HON's 34 original images. No transformations or splitting. |
| Provider request | Same endpoint `/v1/responses`, model `gpt-6-luna`, medium reasoning, 4,096 max output tokens, strict `earnings_eps`, `store=false`, disabled truncation, default service tier, implicit 30-minute cache. No fallback, tool call or repair stage. |
| Timestamp representation | **37/50 requests** change only `filing.filed_at` spelling inside the public context text, e.g. `...28Z` → `...28.000000Z`; 13 already have six digits. Both denote the same instant. This follows FilingReady 1.0 fixed-width UTC, does not select the issuer fiscal period, and is judged nonmaterial to extraction semantics. Exact raw and normalized fingerprints are both retained; no other text is normalized. It is not a claim of byte-identical prompts for those 37 cases or measured model invariance under respelling. |
| Manifest adaptation | The saved experiment lacks live FilingReady envelopes. The audit constructs valid synthetic envelopes from the exact selected members with their sizes, synthetic S3 references and readiness equal to filing time. Those extra fields stay outside model context. This proves preparation compatibility, not producer/cloud delivery. |
| Admission safeguards | Production adds finite member/aggregate/request/text/token/image/response/event limits, strict HTML decode and MIME/extension checks. All 50 pass. WEBP, TXT/PDF and other unsupported members remain whole-snapshot review under D07b; no subset salvage. Out-of-bounds behavior deliberately narrows supported inputs without changing admitted inputs. |
| Dependencies/runtime | The saved run and both current environments match OpenAI 2.54.0, httpx 0.28.1, html5lib 1.1, webencodings 0.6.1, six 1.17.0, Pillow 12.3.0 and jsonschema 4.26.0. Reference Python is 3.14.8; earnings is 3.11.17. All 50 SDK requests and outputs match across them with the timestamp exception. Python 3.13 Linux/native decoder verification remains M6. |
| Retries | Evals allows one SDK retry; production SDK retries are zero and the store durably reserves at most three application attempts. Both use 120-second timeout. This changes failure recovery, not successful request parameters; fault tests verify the approved budget and unknown-usage handling. |
| Native output | Evals uses SDK `model_dump`; production bounds the non-SSE HTTP response body while reading and saves exact bytes plus parsed JSON. All 50 saved native bodies replay unchanged. Production additionally rejects malformed envelopes, duplicate/nonfinite JSON, boolean/floating fiscal identifiers and oversized output; no valid baseline response is rejected. |
| Acceptance/persistence/publication | Source validation already rejects invalid schemas and duplicate observation keys. Production also requires one fiscal period across arrays, stores receipts/outcomes, and publishes immutable filing-specific events. All 50 saved outputs pass unchanged; empty arrays, conflicts, technical failures and recovery have separate offline tests. No cross-filing value comparison, share conversion or independent fact verification is introduced. |
| Evaluation-only features | Pricing, scoring, label projection/editor and alternate-provider branches stay in evals. Earnings retains usage, timings and saved responses. The audit reads fingerprints and artifacts; it does not score predictions or create an application evaluation endpoint. |

These differences are compatible with D01–D12 and do not introduce a material
prompt/schema/preparation/provider behavior change requiring a new quality
experiment. Any future material change needs separate attributable evaluation in
`finbot-filing-evals` before claiming this baseline applies. Because no unresolved
port mismatch needs live inference, no targeted paid parity check was justified;
account access, native Linux packaging and live delivery remain M6 checks.

## Reproduction and software verification

The reference fingerprints were exported by the real evals `DirectExtractor`
with its real pinned SDK over `httpx.MockTransport`, using saved native responses.
The [reference export recipe](parity/REFERENCE_EXPORT.md) verifies code/run identity,
runs only in evals' own environment and writes temporary files. The production
audit uses independent earnings code and imports no sibling package. Neither
step needs credentials or network; both explicitly forbid socket connections.
The committed fingerprints contain only identities/hashes/timestamp spellings,
dependency pins and the historical aggregate result, with no source text/images,
target labels, response bodies or secrets.

From `finbot-earnings`, with the saved data available read-only:

```bash
.venv/bin/python scripts/verify_production_parity.py \
  --run ../../data/filing-evals/runs/20261023T145725Z-9ff8c84b
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
.venv/bin/python -m pip check
git diff --check
```

The opt-in audit verifies full run integrity/membership and source SHA-256s,
then checks the actual SDK's complete serialized request against the independent
reference fingerprints. Reversing only timestamp spelling must also reproduce
the exact reference hash. Native bytes, extracted arrays, normalized usage,
production acceptance and every source read are checked. This is saved-response
replay; the socket ban and synthetic key prevent new paid calls. Do not interpret
50 mocked responses as 50 fresh model predictions. Missing/changed artifacts or
reference fingerprints fail verification.

Measured audit output on 2026-10-25:

| Measure | Observed |
| --- | --- |
| Cases / selected files / saved EPS observations | 50 / 189 / 83 |
| Maximum images / prepared text bytes | 34 / 521,300 |
| Maximum encoded request bytes / local token estimate | 5,189,881 / 546,849 |
| Summed mocked preparation / response handling / total | 11,145 / 448 / 11,593 ms |
| Fresh provider calls / new API cost / unknown usage introduced | 0 / USD 0 / none |

Mock timings measure this local replay only; they cannot estimate provider or
queue latency. The token estimate includes canonical timestamp spelling; it is
seven higher than the M2 record's 546,842, still below the frozen 900,000 bound.
HON's complete 34-image package is included. Real timing fields for preparation,
extraction, claim/outcome persistence and publication/ready-to-ack remain in the
source runtime. Upstream discovery is unavailable from these experiment envelopes;
queue/invocation/subscriber receipt timing and backlog catch-up must be measured
in M6, not inferred from SEC filing time or this replay.

The **176-test** suite passed in 8.24 seconds, including the real mocked SDK and
both SQLite/mocked DynamoDB: accepted/partial/empty/schema-invalid/business-review
outcomes; mixed HTML/PDF and every input bound; provider attempt budgets and crash
recovery; duplicate/new-snapshot/new-run identities; receipt checkpoint recovery;
lost publication acknowledgments with byte-identical saved payloads and no source,
secret or model reuse; fencing, chunk integrity and atomic rollback; handler/CLI
contracts. Six synthetic text fixtures additionally cover tables, inline and
CSS-hidden text, image alt text, Windows-1252, malformed tables and empty HTML.

## Budget and release handoff

D10b test allowance: prior USD 5, new known spend USD 0, no new unknown usage,
**USD 5 remaining cumulatively**. The historical USD 0.159437190 baseline is not
charged again. Production/backlog funding remains user-managed through the
provider UI. No paid test campaign, AWS/GitHub inspection or mutation, deployment,
secret access, shared-data write or catalog refresh occurred.

Milestone 5 is complete. M6 starts by reading this evidence and the roadmap,
then preparing the fiscal Linux dependency bundle/CDK configuration and inspecting
actual release prerequisites. Keep the frozen config identity; preserve existing
stored records/stateful resources and review the exact release artifact/diff
before protected deployment and first activation. Live EPS receipt in inspection
SQS remains required beyond an SNS acknowledgment.
