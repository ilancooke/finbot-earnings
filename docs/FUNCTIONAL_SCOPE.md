# finbot-earnings functional scope

Updated 2026-10-25 through Milestone 3. The fiscal consumer, acceptance,
immutable storage/events, recovery and operator CLI now implement this approved
scope offline. Fiscal packaging/infrastructure is prepared locally; protected deployment remains
Milestone 6. Legacy
Milestone 4 removes Nova processing, the NVDA POC and the local evaluator. [OFFLINE_PROCESSING.md](OFFLINE_PROCESSING.md) and
[AWS_RUNTIME.md](AWS_RUNTIME.md) distinguish current code from this target.
[ROADMAP.md](../ROADMAP.md) governs the migration and approved D01–D12 decisions;
[CONTRACTS.md](CONTRACTS.md) specifies exact fields, schemas and identity.

## Purpose and ownership

Consume complete stored FilingReady snapshots from `finbot-filings`, extract
reported and adjusted diluted EPS, apply schema/business-rule acceptance, persist
all outcomes and publish immutable `earnings.extracted` results. Prioritize
readiness-to-publication latency: process each complete snapshot immediately and
publish accepted EPS after durable persistence.

`finbot-filings` owns discovery, issuer selection, acquisition and readiness.
`finbot-filing-evals` owns reviewed datasets, prompt/model experiments and quality
reports. Earnings owns processing, acceptance, persistence, recovery, publication
and an operator CLI. No sibling imports. Cross-filing aggregation, portfolio
construction and trading execution are outside launch scope.

## Input and flow

```text
FilingReady → claim work → load/check complete snapshot → prepare text/images
    → one EPS extraction call → schema/business checks → persist outcome/event
    → publish saved accepted event → save acknowledgment → acknowledge input
```

The producer's [FilingReady 1.0 contract](../../finbot-filings/docs/FILING_READY.md)
is authoritative. Read precisely its selected manifest; do not infer readiness
from S3 listings, add unselected files, or process attachments separately. Preserve
artifact identity, filenames, original bytes, membership and ordering context.

Use direct OpenAI `gpt-6-luna`, prompt v6, tested `earnings_eps.fiscal.v2` schema,
HTML-derived plain text and original supporting images, medium reasoning and
4,096 output tokens. No classification field, fallback model, model repair loop
or second planned inference stage.

## Launch support matrix

| Selected member | Launch target |
| --- | --- |
| HTML, including XHTML HTML content | Supported through tested HTML-to-text preparation |
| Original JPEG/PNG/GIF supporting image | Supported after format/decoder checks; preserve bytes/context |
| TXT or PDF | Deferred; whole snapshot requires review before inference |
| Other format or invalid/unsupported image encoding | Whole snapshot requires review before inference |
| Complete snapshot exceeding any configured bound | Whole snapshot requires review before inference |

An HTML release with a selected PDF supplement receives
`review_required / unsupported_selected_format`: no model call or EPS event,
even if HTML appears sufficient. Never truncate text, resize/re-encode images,
drop selected files, or split extraction to fit bounds. Missing objects and
stored-size mismatches are technical failures, not format review.

Milestone 2's isolated extractor freezes [finite numeric bounds](EXTRACTOR.md#frozen-bounds-and-unsupported-inputs):
16 HTML documents, 64 images, 64 MiB total source, 2 MiB prepared text, 96 MiB
encoded request, a 900,000-token local estimate and a 2-MiB native response.
The reference inputs, including HON's 34 images, pass these bounds offline; live
account/provider checks remain release work. Fiscal CDK settings are prepared; live activation is pending.
[Review reasons](CONTRACTS.md#review-and-failure-reasons)
identify the affected artifact/bound. Explicit reprocessing follows operator
inspection and a reviewed fix; completed review outcomes do not retry inference.

## EPS and fiscal semantics

Keep `reported_diluted_eps` and `adjusted_diluted_eps` as separate arrays. Preserve
signs, decimal precision/trailing zeroes and all qualifying disclosed currencies.
Reported EPS uses disclosed total diluted EPS when both total and continuing
operations appear. Adjusted EPS uses the primary explicitly disclosed adjusted
measure, including one based on continuing operations. Do not derive values,
substitute basic EPS, or copy reported EPS into an absent adjusted metric.

Select one current issuer fiscal period: latest standalone quarter for quarterly
reporting, Q4 when both Q4 and full year appear, latest complete fiscal year for
annual-only reporting. Exclude comparisons, guidance and cumulative/YTD amounts.
Do not infer calendar dates, derive a quarter by subtraction, or relabel partial
years as annual EPS. See [acceptance policy](V0_DECISIONS.md#acceptance-policy).

Share denomination is **unspecified** in the tested schema. Preserve ordinary-share
and ADR/ADS values in disclosed currencies; no conversion or assumed equivalence.
The schema cannot represent every same-currency share-basis ambiguity. Explicit
share denomination requires a later evaluated prompt/schema change.

## Outcomes and acceptance meaning

| Outcome | Meaning and delivery |
| --- | --- |
| `accepted` | Valid response/business checks and at least one EPS observation; persist and publish one event |
| `no_eps_extracted` | Both arrays empty; persist, acknowledge, no publication or automatic inference retry |
| `review_required` | Unsupported/oversized snapshot or unresolved output business rules; retain reasons, acknowledge, no publication |
| `processing_failed` | Technical/input-integrity/response-format/delivery failure; bounded recovery, then inspection/redrive |

Schema checks structure/types; business checks enforce a single period and unique
observation identities. Financial interpretation is guided by prompt v6, not
independently verified against each fact. There are no per-fact quotes or artifact
fields. **Independent per-fact evidence verification is not required for launch**;
`earnings.extracted` must not be described as independently fact-verified. Preserve
complete sources and model-response provenance. Empty output does not establish
that a filing contains no earnings.

Partial means a valid metric with the other array empty; do not silently prune
invalid/conflicting rows to manufacture acceptance. Internal conflicts go to review;
a different filing's EPS never blocks this filing. CONTRACTS includes examples.

## History and operations

One accepted snapshot/configuration/run produces one immutable event. Duplicate
delivery reuses its saved result/ID. Changed snapshots, amendments, later reports
and explicit new runs remain separate even when EPS is equal. No company-period
canonical merge or revision counter. Publication retries reuse identical bytes
without inference; delivery is at least once and consumers deduplicate event IDs.

Launch CLI requirements: inspect runs/events, sources, saved response, outcomes,
reasons, usage and timing; list review/failed/empty outcomes; resume failed
checkpoints; request fresh extraction with a new identity; inspect output-queue
events. Milestone 3 implements these commands and transactional status queries in
[OFFLINE_PROCESSING.md](OFFLINE_PROCESSING.md). Commands identify inference and
publication effects. A web review UI is deferred; preserve prior/shared-data history.

Process new and all retained queued notifications after activation. No automatic
historical S3 scan/backfill. Measure stage and readiness-to-output latency with
unavailable timestamps explicit and backlog catch-up separate. No hard numeric SLA
is required at launch. Funding is user-managed through OpenAI; no application spend
cap/alert system. Scoped API tests share a cumulative USD 5 allowance.

Deployment/activation is Milestone 6 through the protected reviewed release flow.
Completion requires real queue-triggered EPS receipt in the earnings inspection
queue; a disabled deployment/direct invoke/SNS acknowledgment is insufficient.
