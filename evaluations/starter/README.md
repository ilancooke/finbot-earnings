# Synthetic starter corpus

These eight cases are fictional. They exercise the local evaluation runner and
known evidence-policy limitations; they are not a reviewed real-filings baseline.

Each case includes the complete synthetic FilingReady event, original document
bytes, SHA-256 hashes, expected labels and a separate fixture response. The two
small PDF fixtures are valid single-page text documents. Fixture token usage is
invented (100 input, 50 output tokens per case).

Run the offline command in [LOCAL_EVALUATION.md](../../docs/LOCAL_EVALUATION.md).
Expected smoke-check results: 8 correct classifications/extractions; 10 expected
facts, of which the current validator accepts 5. Three cases validate, three
require review, and two report no relevant earnings. PDF and table-only evidence
account for the withheld facts. No Bedrock quality claim follows from these scores.
