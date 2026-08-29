# finbot-earnings

`finbot-earnings` is a low-latency, provenance-first Python pipeline for official public-company earnings artifacts. The MVP watches NVIDIA investor news and SEC submissions, saves every new source before analysis, extracts a compact earnings flash with OpenAI, and continuously records a UTC latency timeline.

The current implementation is intentionally optimized for the first NVDA live event. It does not try to discover every investor-relations site.

## Architecture

```text
NVIDIA official RSS ─┐
                     ├─ detect ─ download ─ immutable raw + SQLite registry
SEC submissions ─────┘                              │
                                                   parse (HTML/text/tables)
                                                        │
                                              explicit eligibility policy
                                                        │ new + eligible only
                                                OpenAI structured output
                                                        │
                                             versioned extraction + timeline
```

The source, parser, eligibility, extractor, and storage layers are separate. A source poll never calls an LLM by itself. On first startup, each live source establishes a persistent baseline of current discoveries; only later discoveries are downloaded and processed. Artifact registration provides a second idempotency barrier.

Raw files are immutable. Replaying changes parser/extraction outputs but never the captured source.

## Install

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Configuration and environment

Watched companies live in [`src/finbot_earnings/companies.toml`](src/finbot_earnings/companies.toml). NVDA is configured with CIK `0001045810` and the `nvidia` IR adapter.

Copy [`.env.example`](.env.example) to `.env`, then fill in the real contact and API key:

```bash
cp .env.example .env
```

The resulting `.env` contains:

```bash
EARNINGS_DATA_DIR=/Users/ilan/workspace/finbot/data/earnings
SEC_USER_AGENT=finbot-earnings your-real-contact@example.com
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.4-mini
EARNINGS_POLL_INTERVAL=5
```

Every `earnings` command automatically loads the nearest `.env` found from the current working directory. Values in `.env` take precedence over variables inherited from the shell. `SEC_USER_AGENT` must identify the application and contain a contact email. `.env` is ignored by Git and must never be committed.

## Safe offline demo and tests

No normal test makes a network or paid API call.

```bash
python -m pytest

# Or, with no test dependency installed:
PYTHONPATH=src python -m unittest discover -v

# Full fixture IR → SEC → parse → fake extraction → timeline path:
EARNINGS_DATA_DIR=/tmp/finbot-earnings-demo \
  PYTHONPATH=src python -m finbot_earnings demo NVDA \
  --data-dir /tmp/finbot-earnings-demo
```

The demo intentionally polls each fixture twice and asserts through its output that each of the four distinct eligible artifacts is extracted once.

## NVDA live watcher

Start this before the release is published:

```bash
earnings watch NVDA
```

The first successful poll records a baseline and logs its size. It does not backfill or extract old releases. Later new discoveries are printed immediately, persisted, parsed, and—if eligible—sent to OpenAI exactly once. `Ctrl-C` exits cleanly. Polls with no changes are quiet.

If the process is first started only after publication, explicitly process the current feed/filing snapshot with:

```bash
earnings poll NVDA --include-existing
```

That flag can process several historical eligible artifacts on an empty data directory and may incur multiple OpenAI calls; use it deliberately.

To observe acquisition without paid extraction:

```bash
earnings watch NVDA --no-extract
```

## Inspect and replay

```bash
earnings list-artifacts NVDA
earnings show-timeline NVDA

# Offline: reparses the immutable raw artifact, no network or API call.
earnings replay <artifact-id>

# Explicit paid run with the current prompt/model; persists a distinguishable run.
earnings replay <artifact-id> --extract
```

## Storage and deduplication

Under `$EARNINGS_DATA_DIR` (default `/Users/ilan/workspace/finbot/data/earnings`):

```text
registry.sqlite3
artifacts/NVDA/<artifact-id>/
  metadata.json
  raw.html
  parsed-html-v1.json
  extraction-<prompt>-<model>-<timestamp>.json
events/NVDA/<event-id>/
  event.json
  timeline.json
```

SEC identity is `CIK + accession number + document filename`. IR identity is canonical URL plus SHA-256 content hash, so identical polls deduplicate while genuinely changed content can be retained as another version. The SHA-256, source URL, HTTP metadata, accession/filename, source type, lifecycle timestamps, errors, retries, parser version, prompt version, schema version, model, and API usage are persisted.

Events group artifacts whose reliable publication/detection anchor dates are within three days. This is explicit MVP logic, not fiscal-period inference.

## Current live-test limitations

- NVIDIA detection uses its official press-release RSS and recognizes titles matching “NVIDIA Announces Financial Results.” It does not yet poll the quarterly-results JavaScript application or parse PDF commentary.
- SEC exhibit discovery handles explicit EX-99.1/99.2 names and NVIDIA's observed `q1fy27pr.htm` / `q1fy27cfocommentary.htm` convention. It does not parse the filing document table for arbitrary exhibit names.
- HTML tables are preserved as rows plus readable text; there is no perfect financial-table or inline-XBRL parser.
- 10-Q/10-K are eligible, but long-document chunking is not yet implemented. Very large filings may need the Milestone 7 parser before reliable live extraction.
- A discovery is marked seen only after download/persistence processing returns, so acquisition failures retry on later polls. Final LLM failures require explicit `replay --extract` rather than endless automatic retries.
- Company Facts enrichment and cross-source confirmation/conflict reconciliation remain roadmap work.

See [`ROADMAP.md`](ROADMAP.md) for acceptance state and next milestones.
