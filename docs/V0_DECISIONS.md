# finbot-earnings v0 decisions

Status: agreed target decisions, recorded 2026-10-14. These refine
[FUNCTIONAL_SCOPE.md](FUNCTIONAL_SCOPE.md); they are not yet implemented in the
existing POC. [ARCHITECTURE.md](ARCHITECTURE.md) records the working deployment
design and agreed runtime behavior, including complete filing snapshots as input.
Concrete model and deployment settings remain open.

## One call and one processing record

Use one LLM call to classify the complete filing snapshot and extract supported
earnings facts together. Supply every artifact listed in `FilingReady` in that
one request, preserving artifact IDs and filenames. Application code validates the
response afterward. This replaces the earlier per-document processing assumption.

Use one processing record containing the source reference, LLM result, validation
outcome, findings and accepted facts. Classification, extraction and validation
are responsibilities within that record; they do not require three separate
records, tables or LLM calls. Preserve distinguishable runs for explicit
reprocessing, as required by the functional scope.

The application supplies canonical `cik`, filing identity, artifact references and
processing timestamps from upstream metadata. The model checks whether the filing concerns the
supplied company; a mismatch produces uncertainty and review rather than a
validated event.

## Minimal extraction response

V0 extracts only `gaap_diluted_eps` and `adjusted_diluted_eps`. Keep them separate,
with a period and currency on each observation.

The following example is synthetic; its evidence strings illustrate the required
context rather than quote a real filing:

```json
{
  "classification": "reports_earnings",
  "facts": [
    {
      "metric": "gaap_diluted_eps",
      "value": "1.23",
      "currency": "USD",
      "period": {
        "kind": "quarter",
        "end_date": "2026-09-30",
        "label": "Three months ended September 30, 2026"
      },
      "source_artifact_id": "0000000000-26-000001/earnings-release.htm",
      "evidence": "For the three months ended September 30, 2026, GAAP diluted earnings per share were US$1.23."
    },
    {
      "metric": "adjusted_diluted_eps",
      "value": "1.45",
      "currency": "USD",
      "period": {
        "kind": "quarter",
        "end_date": "2026-09-30",
        "label": "Three months ended September 30, 2026"
      },
      "source_artifact_id": "0000000000-26-000001/financial-supplement.htm",
      "evidence": "For the three months ended September 30, 2026, adjusted diluted earnings per share were US$1.45."
    }
  ]
}
```

| Field | Contract |
| --- | --- |
| `classification` | `reports_earnings`, `does_not_report_earnings`, or `uncertain` |
| `facts` | Array of supported observations; empty when none are supported |
| `facts[].metric` | `gaap_diluted_eps` or `adjusted_diluted_eps` |
| `facts[].value` | Signed decimal string, in currency per share |
| `facts[].currency` | Explicitly supported currency code |
| `facts[].period.kind` | `quarter`, `half_year`, or `annual` |
| `facts[].period.end_date` | Supported reporting-period end date in `YYYY-MM-DD` form |
| `facts[].period.label` | Original reporting-period wording |
| `facts[].source_artifact_id` | Source document from the supplied filing manifest; application validates membership |
| `facts[].evidence` | Supporting quotation including the relevant metric labels, period and currency context |

Every returned fact must contain the listed fact fields. Omit missing or
unsupported metrics rather than returning null placeholders or partially
specified facts. There is no field-availability object. Neither EPS measure
inherits period or currency from the other.

Extract the filing's current reported earnings period, excluding historical
comparison columns. If it explicitly announces both quarterly and annual results,
keep those observations distinguishable by period. Preserve the reported sign
and precision; do not infer GAAP diluted EPS from basic EPS or adjusted EPS.

## Validation and publication acceptance

After the call, application code:

1. Checks the response structure, confirms each source artifact belongs to the
   input manifest, and resolves evidence against that document.
2. Verifies company identity, diluted EPS, accounting basis, reporting period,
   currency and sign.
3. Accepts supported facts and withholds facts that fail validation, retaining
   the original response and findings in the processing record.
4. Publishes a period's event when classification is affirmative, company and
   period checks pass, and at least one of the two EPS metrics passes validation
   for that period. Missing metrics are absent from the accepted result.
5. Records uncertainty or material conflicts for review. Processing errors remain
   distinct from semantic review outcomes.

A quotation's presence alone does not establish correct interpretation. If table
headings cannot be reliably associated with a value, that fact requires review.
An unresolved conflict affecting company, period or an otherwise accepted core
fact blocks publication of the candidate revision rather than being silently
discarded. Failure of an independent optional fact does not invalidate another
supported fact.

Persist the outcome and accepted event revision before publication, retaining the
source evidence. This is acceptance under documented checks, not reliance on the
model's confidence.

## Event identity and revisions

Use company and reporting period, not artifact or filing identity:

```text
<cik>:<period_kind>:<period_end>
```

For example, `0000320193:quarter:2026-09-26`. A quarterly event and an annual
event ending on the same date remain distinct. If company or period identity is
unresolved, retain a review candidate without assigning a canonical event ID.

Start validated events at revision 1. Exact duplicates create no new revision.
A changed accepted result creates a new preserved revision; it does not erase
the earlier result. Conflicting later evidence requires review rather than
automatic replacement. Consumers identify published versions by
`(event_id, revision)`. Detailed reconciliation and publication-envelope rules
remain subsequent decisions. Work deduplication uses filing snapshot, extraction
configuration and run mode; it is separate from canonical event identity. See
ARCHITECTURE.md for retries, evaluation isolation and publication recovery.
