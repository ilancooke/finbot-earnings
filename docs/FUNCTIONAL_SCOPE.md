# finbot-earnings functional scope

Status: agreed target scope, recorded 2026-10-14. This document describes the
intended repurposed package; it does not claim that the existing POC implements
these capabilities. [ARCHITECTURE.md](ARCHITECTURE.md) records the working cloud
design and agreed operational behavior; detailed contracts and deployment settings
remain to be decided.

Implementation status: [OFFLINE_PROCESSING.md](OFFLINE_PROCESSING.md) describes
the first filing-level core with fake I/O/model boundaries and a SQLite reference
store. The AWS adapters, CDK and release workflows are implemented as documented in
[AWS_RUNTIME.md](AWS_RUNTIME.md); Nova Lite is configured, while evaluation and deployment remain pending.

[V0_DECISIONS.md](V0_DECISIONS.md) records the agreed initial EPS schema,
single-call processing approach, acceptance criteria and event identity/revisions.
It refines the general scope below.

## Purpose and ownership

`finbot-earnings` consumes stored filing artifacts, determines whether they report
earnings, extracts structured facts with source evidence, validates those facts,
persists canonical `EarningsEvent` records and processing outcomes, and publishes
validated event revisions. It supports inspection and explicit reprocessing of
uncertain or failed outcomes.

Discovery and source-document acquisition have moved to `finbot-filings`, which
is deployed on AWS. The repurposed `finbot-earnings` owns classification,
extraction, validation, event reconciliation, persistence and publication.

The current NVDA-focused POC and its roadmap describe the earlier use case.
They are implementation history, not the target scope for this repurposing.

## Input and functional flow

The target system listens for a new `FilingReady` event from `finbot-filings` and
reads all stored documents in its selected package manifest. It processes the
complete filing snapshot in one combined classification/extraction call.
`FilingReady` establishes that the listed selected documents are stored, not that
the filing has validated earnings. The producer implementation emits filing-level `filing.ready`; production adoption
requires its normal release. It no longer publishes per-document `ArtifactReady`. See
ARCHITECTURE.md for readiness and duplicate handling.

```text
Receive filing snapshot → classify + extract → validate → persist outcome
                                                       │
                                             validated event only
                                                       │
                                                       ▼
                                              publish EarningsEvent
```

1. **Classify.** Ask an LLM whether the filing/document reports earnings.
   Distinguish affirmative classification, no relevant earnings, and uncertainty.
2. **Extract.** For relevant documents, extract a small structured schema with
   evidence references for the reported facts. Preserve missing information rather
   than inventing values. The initial fields are specified in V0_DECISIONS.md.
3. **Validate.** Check schema compliance, company identity, reporting period,
   currency, units, GAAP versus adjusted figures, and supporting evidence.
   Withhold unsupported facts for review. Unresolved company/period evidence or
   material conflicts affecting accepted facts block candidate publication.
4. **Persist.** Record the classification, candidate facts, evidence references,
   validation findings and processing outcome. Persist the canonical event and
   its revision before publishing it. Retain the extraction version and original
   source references so results remain inspectable and reproducible.
5. **Publish.** Publish validated `EarningsEvent` revisions for downstream
   consumers. Review candidates and processing failures do not enter the
   validated-event stream.

Document preparation is not a required functional stage. Direct document input
is the initial baseline to evaluate; preprocessing can be introduced if measured
quality, cost or document limits justify it. The initial baseline is Nova Lite
with direct HTML/TXT/PDF document input and schema-defined tool responses.
PDF-derived facts remain review-only under the initial evidence policy.

## Outcomes and meaning of validation

| Outcome | Meaning |
| --- | --- |
| No relevant earnings | Classification finds no relevant reported earnings in the document |
| Review required | Classification is uncertain, or extraction/validation encounters missing required evidence or conflicting facts |
| Validated | Required facts pass the documented checks against the supplied evidence |
| Processing failed | A processing error prevents completion; this is distinct from a semantic review outcome |

Record each outcome, including why review or failure occurred. Optional missing
metrics are omitted from extraction results rather than represented as null.
Publication requires at least one supported core metric; missing required evidence
blocks acceptance of the affected fact. Unresolved identity or material conflicts
block candidate publication.
Schema compliance and the LLM's own confidence do not establish factual validity.
A matching evidence quote alone does not prove that the period, units or meaning
were interpreted correctly. Validation is evidence-backed acceptance under
documented rules, not an independent guarantee of the issuer's financial accuracy.

## Canonical events and revisions

A release, supplement and periodic report can describe the same company and
reporting period. They contribute evidence to one logical `EarningsEvent` rather
than automatically producing separate events for each artifact. Event association
must use company and reporting-period identity; the POC's approximate grouping by
nearby publication dates is not sufficient for this purpose.

One filing snapshot can establish an initial validated event, including a package
with only one selected document. Later filings or explicit new snapshots can
enrich it when supported, while conflicts require review. Later disclosures,
amendments and reprocessing must preserve prior event revisions and their evidence
rather than erase what was previously known. Repeated delivery of the same input
must not create a new logical event merely because it was received again.

## Inspection and reprocessing

Retain review candidates with their available facts, evidence and reasons for
non-acceptance. Support inspection and explicit reprocessing of uncertain or
failed outcomes against the stored source documents. New runs remain
distinguishable from prior runs. A review interface and an automatic correction
loop are later design choices, not prerequisites for the agreed functional scope.

## Decisions to make next

- Detailed evidence verification for the agreed v0 fields.
- Document reconciliation and remaining revision rules.
- Detailed conflict handling within the agreed v0 acceptance criteria.
- Exact input/output envelopes and recovery implementation under ARCHITECTURE.md.
- Model selection, document handling and concrete storage/deployment settings.

This scope leaves those implementation details open and does not authorize deployment. Model
evaluation and a reviewed document corpus should inform the subsequent extraction
and validation decisions.
