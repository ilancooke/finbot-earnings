# finbot-earnings launch decisions and acceptance

Updated 2026-10-25 for Milestone 1. Filename retained for existing links. The
approved D01–D12 target **supersedes the 2026-10-14 v0 target**. Implemented
`FiscalConsumer` now implements the fiscal policy. Milestone 4 removes the legacy
`eps-v0`/`explicit-prose-v1` runtime; historical stored records remain separate.
[CONTRACTS.md](CONTRACTS.md) owns exact fields/identity/schemas;
[ROADMAP.md](../ROADMAP.md#decision-register--d01d12-approved) owns approvals.

## Version register

| Concern | Launch specification identity |
| --- | --- |
| Input | Producer-owned `filing.ready` / `1.0`, unchanged |
| Model response | `earnings_eps.fiscal.v2`, exact tested local schema |
| Prompt | `eps-v6`, unchanged tested prompt |
| Preparation | `filing-html-text-images-v1`, traceable port of evals preparation |
| OpenAI transport schema | `openai-fiscal-v2-union-v1`, tested conditional-to-union compilation |
| Acceptance policy | `fiscal-eps-acceptance-v1` |
| Output | `earnings.extracted` / `1.0`, new event family |
| Work/record namespaces | `earnings-work:v2` / `earnings-processing:v2` |
| Configuration version | `eps-openai-luna-v6-v1`, frozen in Milestone 2's isolated extractor |

The isolated port implements preparation/transport with [hashes, pins and bounds](EXTRACTOR.md).
Milestone 3 integrates that boundary with version-2 storage, transactional
status partitions and CLI; see OFFLINE_PROCESSING. No target version aliases a legacy record.

## One extraction call

Use direct OpenAI `gpt-6-luna`, plain-text HTML plus every supported original image,
with artifact/filing context and tested sequence. Preserve the checked Responses
request: strict `earnings_eps` structured output, medium reasoning,
`max_output_tokens=4096`, `store=false`, `truncation=disabled`,
`service_tier=default`, implicit prompt cache with `ttl=30m`. The evals candidate
uses a 120-second timeout and one SDK retry. The port retains that timeout but
uses zero SDK retries and at most three application attempts, durably
reserved and counted by the version-2 stores in Milestone 3. No model fallback/repair or
fabricated legacy classification/evidence fields.

These settings describe the checked local reference, not verified account access.
[OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs)
were checked 2026-10-25 for text/image and structured-output support. Concrete
request/image/token bounds and account quotas remain implementation/release checks.

## Tested response and financial meaning

Both arrays are required, including when empty:

```json
{
  "reported_diluted_eps": [
    {"value":"1.230","currency":"USD","period_type":"quarterly","fiscal_year":2026,"fiscal_quarter":3}
  ],
  "adjusted_diluted_eps": [
    {"value":"1.45","currency":"USD","period_type":"quarterly","fiscal_year":2026,"fiscal_quarter":3}
  ]
}
```

- Reported EPS is diluted EPS attributable to common shareholders. Prefer the
  explicitly disclosed total over its continuing-operations component. If no total
  is disclosed, use explicitly reported diluted EPS without deriving a total.
- Adjusted EPS is the primary explicitly disclosed adjusted/non-GAAP diluted
  measure, including qualifying “excluding special items/charges” wording. A
  continuing-operations basis is allowed for this metric. Exclude constant-currency
  or separate operational variants and adjustment components. Never calculate EPS.
- Select one issuer fiscal period across all observations: standalone current
  quarter for quarterly reports/releases, Q4 when both Q4/full year appear,
  complete year for annual-only reports/releases. Annual quarter is null.
- Exclude basic EPS, comparisons, earlier quarters, guidance and partial-year
  cumulative/YTD totals. Fiscal year is the issuer designation, not publication
  year. No calendar dates are required or inferred.
- Preserve signs, exact decimal strings and every qualifying disclosed currency.
  Deduplicate repeated disclosures during extraction: at most one observation per
  metric/currency/selected period. No currency/share-unit conversions.

No classification, confidence, period-end date, quote, per-fact source ID or
share-basis field. Source provenance belongs to the saved snapshot and processing
record. Currency alone cannot resolve share denomination.

## Acceptance policy

Apply `fiscal-eps-acceptance-v1` in this order:

1. Validate FilingReady/manifest and complete supported input before inference.
   Unsupported/oversized members send the whole snapshot to review; missing or
   size-mismatched objects are technical failures.
2. Save provider response/usage/timing. Require a completed response with exactly
   one complete assistant JSON text result and no tools/refusal. Refusal or
   incomplete output goes to review without automatic inference retry/repair.
3. Validate the whole object against the exact fiscal v2 local schema. Reject
   duplicate JSON keys/nonfinite constants and booleans as fiscal integers. Invalid
   JSON/schema is terminal `processing_failed / invalid_model_response`; retain
   diagnostics and do not automatically call inference again.
4. Require uniqueness within each metric on `(currency, period_type, fiscal_year,
   fiscal_quarter)`. Repeated rows, even identical ones, go to
   `review_required / duplicate_observation`; do not choose a winner.
5. Require a single `(period_type, fiscal_year, fiscal_quarter)` across both arrays.
   Multiple periods go to `review_required / multiple_fiscal_periods`; do not select
   a subset by dates/heuristics after extraction.
6. Both arrays empty: persist `no_eps_extracted`, acknowledge, publish nothing.
   Otherwise accept the complete valid object and persist one immutable event
   before publication. An absent metric stays an empty array.

These checks do not independently reread financial tables/images. Total/component
choice, current period, actual currency disclosure and YTD/guidance exclusion are
prompt instructions whose interpretation is not independently verified at launch.
Three uppercase currency letters meet the tested schema; no separate ISO registry
or disclosure verification is claimed. Confidence/schema compliance does not prove
factual truth. Do not apply the old prose-only validator to the new response.

No row-level salvage of invalid output. Partial publication means an available
valid metric with the other array empty. Different values across separate filings
never create a canonical conflict gate. Preserve raw outputs, findings and sources.
See [examples](CONTRACTS.md#acceptance-examples) for quarter/annual/YTD/currency,
conflict and empty-result boundaries.

## Identity, retries and compatibility

CONTRACTS defines canonical SHA-256 encoding of filing/snapshot, complete extraction
configuration digest and explicit run ID. Default run `initial`; fresh extraction
requires a new run ID/configuration. Retry/redrive resumes existing checkpoints.
Equal EPS in distinct filings/snapshots/runs does not suppress publication.

Commit outcome/event/publication intent atomically with fencing. Retry publication
with identical bytes/ID without inference. A crash before response persistence may
require another paid call: exactly-once inference is not promised. Review/empty
outcomes complete without automatic inference retry. Technical retries are bounded;
exhausted inputs remain inspectable/redrivable.

Preserve old `earnings.validated` / `1.0` company-period revisions and POC state
separately. No automatic migration, merge, overwrite or legacy republication.
Milestone 2 maintains the frozen boundary; Milestone 3 now connects the fiscal
consumer without modifying legacy records. Milestone 4 removes the legacy evaluation mode/endpoint; experiments
remain in `finbot-filing-evals`.
