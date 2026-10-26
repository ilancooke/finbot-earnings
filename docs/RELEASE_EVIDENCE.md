# Milestone 6 release evidence

Updated 2026-10-26. **Milestone 6 remains in progress.** The production worker is
deployed with its queue trigger disabled. A genuine-filing direct smoke test passed,
including stored EPS and output SQS receipt. Source configuration now prepares
consumption=true for a protected release; enabled queue-triggered extraction and
duplicate-delivery verification are still required.

## Recovery and disabled release

The first protected Deploy
[40393601425](https://github.com/ilancooke/finbot-earnings/actions/runs/40393601425)
failed because the account's total/unreserved Lambda concurrency is 10/10 and it
cannot allocate the requested reservation of two. The user chose shared capacity,
keeping the SQS source maximum at two. Fix commit
`829d1a98a36e36e68cac6b8f3939b0f29fc584f7` passed
[main CI 40397320222](https://github.com/ilancooke/finbot-earnings/actions/runs/40397320222).

The user removed the failed stack record with the eight survivors' Retain policies
intact. Reviewed import change set
`arn:aws:cloudformation:us-east-1:559007813222:changeSet/recover-retained-resources/c740f8e8-4dc9-4209-8fbf-f36c69fa8a7b`
contained exactly eight Import actions: five SQS queues, the processing table,
secret and log group. Import completed and termination protection was restored.
Recovered stack ARN:
`arn:aws:cloudformation:us-east-1:559007813222:stack/finbot-earnings-prod/936a6ac0-d180-11f1-a965-12ffd3ec13f5`.
No retained resource identity or contents were discarded.

User-approved [Deploy 40402075873](https://github.com/ilancooke/finbot-earnings/actions/runs/40402075873)
succeeded from that exact main CI artifact, with source_dirty=false and
consumption_enabled=false. Independently verified artifact identities:

| Item | Value |
| --- | --- |
| Lambda asset SHA-256 | `e8e970ffa074829acd9b61e13610d01c9341d22728a049bbf14252ec66da7201` |
| Cloud assembly SHA-256 | `18ca13a6a2e3d6c03e2f7414efe751b1a770016ec3ba564f80456a6772b16a9d` |
| Frozen fiscal config | `eps-openai-luna-v6-v1` / `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097` |
| Production alias | `arn:aws:lambda:us-east-1:559007813222:function:finbot-earnings-prod:production` |
| Lambda version | `1` |
| Queue mapping UUID | `7d94af68-1f22-4d3b-b9e9-aac774412007` |
| Mapping inspection | Disabled, batch 1, maximum concurrency 2; no function reservation |
| Processing table | `finbot-earnings-prod` |
| Input queue | `https://sqs.us-east-1.amazonaws.com/559007813222/finbot-earnings-prod-filings` |
| Output queue | `https://sqs.us-east-1.amazonaws.com/559007813222/finbot-earnings-prod-output` |
| Output topic | `arn:aws:sns:us-east-1:559007813222:finbot-earnings-prod-validated` |
| Alarm topic | `arn:aws:sns:us-east-1:559007813222:finbot-earnings-prod-alarms` |
| Log group | `/finbot/finbot-earnings-prod` |

The artifact's full `deployment-outputs.json` is retained by GitHub as
`deployed-release-40402075873`, and locally at
`/tmp/finbot-earnings-deployed-40402075873/deployment-outputs.json`.
The diff preserves all eight imported resources' properties and retention settings;
its changes to those eight remove only temporary recovery annotations.

## Credential and alarm delivery

The user populated dedicated secret
`arn:aws:secretsmanager:us-east-1:559007813222:secret:finbot-earnings-prod/openai-project-key-YE9xRq`.
AWSCURRENT version is `6698a4d8-0a82-433d-a1c9-c983541442f0`. Only its name/ARN/version
are recorded; the plaintext credential was entered through a hidden local prompt
and is absent from source, scripts, arguments, output and evidence. The worker's
subsequent successful inference verifies runtime retrieval/access.

Alarm email `ilancooke@gmail.com` is confirmed under subscription
`arn:aws:sns:us-east-1:559007813222:finbot-earnings-prod-alarms:93b1fe51-668c-4eb8-9b57-0dd2704f9d87`.
The user received the controlled alarm-topic test message, SNS ID
`283917a8-4c83-5958-b264-74f1853004a4`. This verifies SNS-to-email delivery; a synthetic
CloudWatch alarm transition was not induced. Nine CloudWatch alarms and scoped
publication policies remain covered by deployment/offline assertions.

## Genuine HON direct smoke

The immutable producer notification for filing `0000773840-26-000143`, snapshot
`5e2356665a6b6d326eb81852e4d53fca331430c67ddfdfeb53be502d9cf9193e`, was fetched from
`finbot-prod-filings` and preserved intact. Its ready_at is
`2026-10-22T14:35:47.681581Z`. All **35** selected original members were read:
one HTML plus **34 JPEGs**. Preflight: 190,985 prepared text bytes, 2,118,320 encoded
request bytes and 496,387 locally estimated tokens. This heuristic differs from
provider billing tokens. No member was dropped, transformed or replaced.

The user explicitly invoked the production alias synchronously with one SQS-shaped
operator replay while the real event-source mapping remained disabled. StatusCode
200, FunctionError null, ExecutedVersion 1, batchItemFailures empty. This proves the
deployed worker/integration path, **not an actual SQS-triggered invocation**.

| Evidence | Value |
| --- | --- |
| Work | `earnings-work:v2:ea14fccac9f3736edbef289158d689af195b5f818f822c744096800011ac87d2` |
| Event | `earnings.extracted:1.0:ea14fccac9f3736edbef289158d689af195b5f818f822c744096800011ac87d2` |
| Run / outcome | `initial` / accepted; no review reasons |
| Extracted EPS | reported USD `2.08`, quarterly FY2026 Q3; adjusted array empty |
| Provider attempts / publication attempts | 1 / 1 |
| SNS acknowledgment | `cfa0992c-d5ee-5c5c-8c8e-fa751e482e30` |
| First claim | `2026-10-26T21:42:50.420045Z` |
| Preparation / extraction | 5,219 ms / 6,524 ms |
| Extraction start/end | `2026-10-26T21:42:55.973934Z` / `2026-10-26T21:43:02.498044Z` |
| Publication acknowledgment | `2026-10-26T21:43:02.697704Z` |
| First claim to publication acknowledgment | 12.277659 seconds |
| Last publication duration | 109 ms |
| SQS output message | `bd54948d-cc1c-449c-93ec-905c4cff7073` |
| Output SQS SentTimestamp | `1793050982725` = `2026-10-26T21:43:02.725Z` |
| Operator inspection started | `2026-10-26T21:51:19Z` |

The zero-visibility peek returned that same SQS message ID with receive counts
1, 2 and 3. This is repeated receipt evidence, not three provider calls/events.
Inspection time is distinct from queue enqueue time and is not a precise initial
subscriber-receive timestamp. The large ready-to-publication interval (371,235,021 ms)
is due to explicitly replaying a four-day-old stored snapshot; it is not normal
operating queue latency. No discovery timestamp or numeric SLA is fabricated.

Full source/config/native receipt/outcome/event are resolved through earnings-ops
inspect/event using the IDs above. Temporary operational copies are under ignored
`build/recovery/`: smoke-processing.json, smoke-output-receipt.json,
smoke-output-inspection-started-at.txt, smoke-preflight.json and api-test-ledger.json.
They contain no provider credential and are not committed as generated datasets.

## API ledger and activation readiness

The saved receipt has complete usage: **59,518 input tokens**, comprising 3 ordinary
and 59,515 30-minute cache-write tokens; **105 output tokens**, including 47 reasoning
tokens; no cached reads. Total **59,623 tokens**, usage_unknown=false. Using
[GPT-6 Luna pricing](https://developers.openai.com/api/docs/models/gpt-6-luna) checked
2026-10-26 (below the 272K long-context threshold), the receipt-based estimate is:

`(3 * 0.10 + 59515 * 0.125 + 105 * 0.50) / 1000000 = USD 0.007492175`.

The user's billing UI showed a USD 0.01 balance change. That display is separate
from this attributable receipt-based estimate and is not treated as a precise invoice.
Previous allowance USD 5; known new estimated spend USD 0.007492175; **USD 4.992507825
estimated allowance remains**, no unknown attempts. The pre-test USD 0.50 buffer
can be released. No complete paid 50-case repeat or failure experiment was run.
Normal production/backlog funding remains user-managed through OpenAI's UI; no app
spend cap, spend alerts or funding automation was added.

Input queue inspection returned visible/in-flight/delayed **0/0/0**. No retained
backlog was observed, so estimated catch-up work/cost at that inspection is zero;
oldest-message age is inapplicable to an empty queue. These are approximate live
counts, not a guarantee about future arrivals. Recheck before protected activation.
The user reports `gpt-6-luna` limits: **2,000,000 TPM, 5,000 RPM, 50,000 IPM** and
**20,000,000 TPD** as displayed. At the measured HON duration, two continuously busy
workers imply approximately 0.58M input tokens/minute for HON-sized requests. This
is illustrative capacity evidence for this filing, not a throughput guarantee for
all admitted inputs or other projects sharing organization limits.

Next: merge the prepared enabled configuration directly to main when authorized,
wait for its exact successful CI, review its infrastructure diff, and approve the
protected production release. Verify the mapping is actually Enabled. Then observe
fresh genuine SQS-triggered EPS extraction and inspection receipt, verify duplicate
reuse without another provider attempt, reconcile any additional test usage, and
only then mark Milestone 6 complete. Replaying the already completed HON input
alone would prove deduplication rather than fresh extraction.
