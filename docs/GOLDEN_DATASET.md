# Golden dataset: finbot-filings product output

The active draft lives at
`$FINBOT_DATA_ROOT/earnings/evaluations/corpora/golden-s3-v1/`.
Open `REVIEW.md` there for labels, supporting extracts, original document links
and exact S3 references. Labels are `agent_draft`, pending human review.
Files and labels stay outside Git under the shared data root.

## Source boundary and sample

Use only filings discovered/selected/downloaded by finbot-filings and stored in
`finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua`. The bucket is organized as
`<ticker>/<filing-directory>/<filename>`. Older local collections used different
filters and are excluded, even when they contain desirable company names.
Do not supplement this sample with those archives or synthetic S3 references.

The active sample contains **UNH, ASML, BAC, JNJ, JPM, GS, MS, DAL and DPZ**:
nine filings, 22 unchanged S3 files and 14 draft EPS facts. It replaces both
`golden-v1` and the mixed-source `golden-v2`; those earlier drafts are inactive.

Every included file was freshly copied from this bucket and matched to its
production SELECT artifact record and listed S3 size. Each chosen filing includes
all its stored selected artifacts, including recovered JNJ and DAL attachments.
Selection follows the actual current product output in S3; existing records retain
their original acquisition-policy versions. No new SEC discovery or acquisition,
SNS publication, extra freezing procedure or production write is needed.

This set is naturally tilted toward financial companies reporting in this window.
It covers GAAP/adjusted EPS, basic/diluted distinctions, historical comparisons,
guidance exclusions, multiple attachments and EUR/USD currency context. All nine
cases currently report quarterly earnings. PDF/plain-text, non-earnings,
uncertain/conflict, current-loss and annual/half-year examples remain gaps; add
them when present in product output rather than importing other filtered sources.

## Metadata and review

`source-records.json` saves the production filing/artifact/company records and
S3 object listing used to assemble the sample. Each case's `provenance.json`
records its source bucket, object metadata, selection records and labeling notes.

These older completed filings have no saved FilingReady event. Equivalent
evaluator metadata was reconstructed from production records, retaining their
actual filing timestamps and real S3 URIs. `ready_at` is derived from the latest
included artifact `stored_at`; it does not claim an SNS event was published then.
No local-only bucket references or date-only archive conventions are used.

From the repository root, validate without AWS or model calls:

```bash
.venv/bin/python -m finbot_earnings.evaluation check \
  --corpus ../../data/earnings/evaluations/corpora/golden-s3-v1/corpus.json \
  --config ../../data/earnings/evaluations/corpora/golden-s3-v1/evaluation-config.json
```

Seven cases exceed production's provisional 128 KiB aggregate budget. The local
`evaluation-config.json` uses a distinct extraction version and a 4 MiB budget;
all nine inputs fit that budget and the current five-document/4.5 MB per-document
adapter caps. Production configuration remains unchanged. Provider context/output
constraints and evidence-policy reviews still apply.

Review and correct the `expected` fields against the source documents. After
review, set `label_source` to `human_reviewed` and record reviewer/date in
`label_notes`. No fixture responses are supplied for real cases: corpus checks
are offline, while an evaluation run needs model output. See
[LOCAL_EVALUATION.md](LOCAL_EVALUATION.md) for commands and score definitions.
