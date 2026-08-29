# finbot-earnings roadmap

The milestones deliberately optimize the NVDA live path first. A checked task is implemented in the current MVP; unchecked work remains planned.

## Milestone 0 — Architecture and package scaffold

- Goal: establish a small, replaceable pipeline with no network required by unit tests.
- Tasks: [x] `src/` package [x] TOML company config [x] models/enums [x] source, parser, extractor, persistence interfaces [x] CLI [x] tests.
- Inputs: watched-company configuration and environment variables.
- Outputs: installable `earnings` command and stable interfaces.
- Tests/acceptance: [x] package imports and deterministic tests run without credentials.
- Dependencies: Python 3.11+; OpenAI SDK only for live extraction.
- Out of scope: dependency injection framework, worker queue, service deployment.

## Milestone 1 — Artifact registry and immutable persistence

- Goal: capture every source version once, before analysis.
- Tasks: [x] SHA-256 [x] stable IDs [x] SQLite registry [x] immutable raw files [x] state/errors/retries [x] event/timeline files.
- Inputs: discovery metadata plus downloaded bytes/HTTP metadata.
- Outputs: artifact directory, registry row, one processing opportunity.
- Tests/acceptance: [x] repeated registration creates one artifact/job; changed IR content creates a new version.
- Dependencies: Milestone 0.
- Out of scope: external/object databases, distributed locks, retention policy.

## Milestone 2 — SEC earnings detector

- Goal: detect NVDA 8-K, 10-Q, 10-K and earnings exhibits from stable SEC data endpoints.
- Tasks: [x] submissions JSON [x] form/item classification [x] Item 2.02 [x] accession URLs [x] EX-99.1/99.2 discovery [x] fair-access User-Agent.
- Inputs: CIK, SEC submissions and filing-directory JSON.
- Outputs: downloadable SEC artifact discoveries with accession/filename provenance.
- Tests/acceptance: [x] fixture 8-K yields its primary document and EX-99.1/EX-99.2 exactly once after registry deduplication.
- Dependencies: Milestones 0–1.
- Out of scope: filing-page HTML scraping, every exhibit naming convention, amended-filing semantics.

## Milestone 3 — NVIDIA IR live-source adapter

- Goal: narrowly detect the earliest official NVIDIA financial-results release.
- Tasks: [x] official NVIDIA press-release RSS [x] title eligibility [x] publication timestamp [x] release download [x] content-version deduplication.
- Inputs: NVIDIA official press-release RSS XML.
- Outputs: an IR release discovery and immutable HTML.
- Tests/acceptance: [x] historical fixture is detected and registered once across repeated polls.
- Dependencies: Milestones 0–1.
- Out of scope: universal IR discovery, JavaScript browser automation, PDF parsing.

## Milestone 4 — OpenAI earnings extraction

- Goal: turn new eligible parsed artifacts into a compact, audited earnings flash.
- Tasks: [x] provider interface [x] Responses API adapter [x] strict JSON Schema [x] versioned prompt/schema [x] usage/timing [x] bounded retries [x] persisted runs.
- Inputs: parsed artifact text/tables.
- Outputs: validated `EarningsExtraction` with facts, guidance, highlights and locators.
- Tests/acceptance: [x] fake saved response validates core NVDA facts; [ ] opt-in paid historical extraction evaluated manually.
- Dependencies: Milestones 0–1; `OPENAI_API_KEY` for live calls.
- Out of scope: provider comparison, prompt optimization campaign, automatic consensus.

## Milestone 5 — Live watcher and latency timeline (highest priority)

- Goal: one command continuously runs detect → persist → parse → extract for NVDA.
- Tasks: [x] source polling [x] immediate event logs [x] new-only extraction [x] graceful Ctrl-C [x] continuous UTC timestamps [x] replay/demo paths.
- Inputs: company config, credentials, source endpoints.
- Outputs: artifacts, extraction JSON, event timeline and console flash.
- Tests/acceptance: [x] fixture vertical slice completes with one extraction and measured timeline; [ ] live event run.
- Dependencies: Milestones 1–4.
- Out of scope: daemonization, alert delivery, multi-process concurrency.

## Milestone 6 — Artifact/event reconciliation

- Goal: recognize confirmations and preserve conflicts across event artifacts.
- Tasks: [x] explicit approximate-date grouping [ ] canonical fact matching [ ] confirmation/conflict records [ ] explicit precedence rules.
- Inputs: multiple extraction runs for one event.
- Outputs: provenance-preserving `reconciliation.json`.
- Tests/acceptance: [ ] equal facts confirm; unequal facts coexist and flag conflict.
- Dependencies: Milestone 5.
- Out of scope: silently selecting a single “truth,” probabilistic entity resolution.

## Milestone 7 — 10-Q / 10-K and Company Facts enrichment

- Goal: enrich the fast event with later authoritative SEC data.
- Tasks: [x] 10-Q/10-K discovery [ ] optimized long-filing parsing [ ] Company Facts snapshots [ ] period/accession association [ ] deterministic validation.
- Inputs: SEC filing artifacts and `companyfacts` JSON.
- Outputs: additional observations and validations attached to the event.
- Tests/acceptance: [ ] historical event associates filing/XBRL facts without creating a duplicate event.
- Dependencies: Milestone 6.
- Out of scope: broad XBRL taxonomy normalization.

## Milestone 8 — Additional company IR adapters

- Goal: add companies without changing orchestration.
- Tasks: [x] adapter interface/config hook [ ] AAPL [ ] MSFT [ ] AMD [ ] META [ ] AMZN.
- Inputs: company-specific official publication mechanisms.
- Outputs: tested adapters producing common discoveries.
- Tests/acceptance: [ ] each adapter detects one historical release once.
- Dependencies: Milestone 5.
- Out of scope: assuming all IR sites share selectors or vendors.

## Milestone 9 — Replay and evaluation framework

- Goal: compare parser/prompt/model versions against immutable history.
- Tasks: [x] offline parse replay [x] distinguish extraction runs [ ] batch corpus runner [ ] accuracy/latency/schema metrics [ ] golden annotations.
- Inputs: stored raw artifacts and optional saved provider responses.
- Outputs: versioned runs and evaluation report.
- Tests/acceptance: [ ] a model/prompt upgrade runs on a corpus without redownload.
- Dependencies: Milestones 4–6.
- Out of scope: public benchmark service.

## Milestone 10 — Production hardening

- Goal: make proven live behavior operationally resilient.
- Tasks: [ ] resilient scheduler [ ] concurrency controls [ ] SEC/OpenAI rate limits [ ] alerting [ ] monitoring [ ] deployment [ ] distributed workers.
- Inputs: live-test evidence and failure modes.
- Outputs: production runbook and service.
- Tests/acceptance: [ ] soak, restart/recovery, rate-limit and alert tests pass.
- Dependencies: completed live experiments.
- Out of scope: premature infrastructure before the NVDA path is measured.

