# finbot-earnings roadmap

Updated 2026-10-25. **All migration decisions D01–D12 are approved. Milestone 1
is complete; Milestones 2–6 have not started.** This document is the durable plan
and checkpoint for separate agentic sessions. README describes implemented status; the approved
decision register below governs the target. Design documents were reconciled
in Milestone 1; runtime behavior remains unchanged. A decision approval is not a
completed implementation milestone.

## Required end state

By the end of Milestone 6, the deployed, enabled worker must consume a real
producer-compatible FilingReady snapshot through its SQS trigger, read its stored
files, extract EPS, persist the accepted result and publish `earnings.extracted`
containing EPS data to the earnings SNS topic. Verify receipt in the earnings-owned
inspection SQS queue. A disabled stack, direct worker invocation or SNS publish
acknowledgment alone is insufficient.

Accepted results are filing-specific; empty, review and failed outcomes follow
the approved policy. Delivery is at least once and consumers deduplicate by event
ID. Routine releases preserve consumption state; the disabled rollout stage is
for first deployment only.

## Session workflow

1. Read workspace/package AGENTS guidance, README, this current checkpoint and the
   approved decision register. Inspect each relevant repository's git status.
2. Select the **first incomplete milestone** in the progress table. Resume it if
   partially implemented. Every milestone depends on all preceding milestones
   being complete, even where its code could otherwise be developed independently.
3. Read that milestone's listed inputs and the preceding completion record. Verify
   referenced files/commits and checks; do not assume conversation history exists.
4. Implement **one milestone per session**. Make the smallest coherent change,
   keep offline checks passing, and document engineering choices within approved
   constraints. Do not reopen settled decisions or start the next milestone.
5. Verify its exit criteria. Update its task checkboxes, progress row, current
   checkpoint and README's status/command/documentation descriptions. Append a
   completion record using the template below, including exact checks and next action.
6. Stop and return a handoff at that milestone boundary. If incomplete or awaiting
   an operator prerequisite/approval, mark it in progress, record the exact resume
   step and stop without marking it complete. Resume the same milestone next time.

Treat uncommitted work as existing user/session work to preserve. Commit only
when requested or otherwise authorized; if uncommitted, list the relevant files
in the completion record. Do not commit shared operational data. Test every
modified repo using its own environment.

Suggested new-session instruction:

> Read this package's README and ROADMAP, including the current checkpoint,
> approved decisions and last completion record. Implement only the first
> incomplete milestone, verify its exit criteria, update both documents and
> append a handoff record, then stop before the next milestone.

## Current checkpoint

- Date: 2026-10-25.
- Planning: all 24 entries under D01–D12 approved; none unanswered.
- Completed: **Milestone 1 — contracts and documentation**. See its
  [completion record](#milestone-1--complete--2026-10-25) for versions, files,
  source hashes, checks and compatibility notes.
- Current work: documentation/schema/example changes are uncommitted. Runtime,
  dependencies, shared data, live inference and AWS resources are unchanged.
  Nova core/adapters, legacy NVDA POC and local evaluator still coexist.
- Source configuration disables consumption; actual cloud/GitHub state has not
  been inspected. No deployed-state claim follows from source configuration.
- Verification: compilation, 171 offline tests, schema/example/identity checks
  and documentation link/diff checks passed; exact commands below.
- Next session: **Milestone 2**. Read the completion record and finalized contracts,
  then implement the isolated tested extractor behind a transition boundary.
  Freeze finite provider-specific bounds, dependencies and preparation hashes;
  do not integrate the consumer/storage or begin Milestone 3 yet.
- API test ledger: USD 5 previous balance, USD 0 used in Milestone 1, no unknown
  usage from this session, **USD 5 remaining** cumulatively. No provider calls.
  Ongoing production funding is user-managed under D11e.
- External setup remains Milestone 6: actual deployed-state inspection, GitHub/OIDC
  readiness, dedicated secret/secure credential population, alarm-email
  confirmation and output subscription/delivery verification.

Replace this checkpoint after each milestone; preserve historical evidence below.

## Milestone progress

| Milestone | Status | Required starting state | Completion record |
| --- | --- | --- | --- |
| 1 — Contracts and documentation | Complete | Approved decisions below | [2026-10-25 completion](#milestone-1--complete--2026-10-25) |
| 2 — Tested extractor | Not started | Milestone 1 complete | None |
| 3 — Filing consumer integration | Not started | Milestone 2 complete | None |
| 4 — Legacy cleanup | Not started | Milestone 3 complete | None |
| 5 — Production parity evidence | Not started | Milestone 4 complete | None |
| 6 — Reviewed release and activation | Not started | Milestone 5 complete | None |

Use Not started, In progress, or Complete. Put a link to the durable completion
record in the final column when complete. Keep this table and README in sync.


## Milestone 1 — Revise the earnings contract and acceptance policy

**Prerequisite:** planning complete; no prior implementation milestone.

**Read:** approved decisions, README, FUNCTIONAL_SCOPE, V0_DECISIONS, CONTRACTS,
ARCHITECTURE, OFFLINE_PROCESSING and AWS_RUNTIME; producer FilingReady contract;
evals v6 prompt, fiscal schema/configuration and experiment report.

**Session scope:** documentation and contract specification. Turn approved
decisions into exact field/schema/configuration versions, identity semantics,
business checks, outcomes and examples. Clearly label current code versus target
behavior. Do not change the runtime or create cloud resources in this milestone.

Goal: make production semantics explicit before changing extraction or storage.

- [x] Adopt the tested reported/adjusted diluted EPS semantics, including total
  diluted EPS versus continuing operations, explicitly disclosed adjusted measures,
  and exclusion of basic EPS, guidance and derived values.
- [x] Adopt issuer fiscal year/quarter identity and one current reporting period
  per filing: select Q4 when both Q4 and full-year results are reported; select an
  annual period for a full-year-only report. Exclude cumulative/YTD observations.
- [x] Define versioned filing-snapshot event identity under D04–D05 and preserve
  all extracted currencies without cross-filing merging. Document unspecified
  share denomination under D03b; do not infer conversions or calendar dates.
- [x] Remove required period-end dates from the launch contract and define the
  separation from existing company/period-end event IDs and stored revisions.
- [x] Define schema validity, acceptance and independent evidence verification
  separately. The tested response has no per-fact quote or source-artifact field;
  the existing prose-only validator cannot accept many table/image results.
- [x] Apply D01: independent per-fact evidence verification is not required for
  launch. Preserve source snapshots, model responses and processing provenance;
  publish `earnings.extracted` after the agreed schema/business-rule checks.
- [x] Apply D02: no classification field, publication with at least one accepted
  observation and completed `no_eps_extracted` for empty arrays. Define separate
  review/technical-failure reasons without claiming a definitive non-earnings result.
- [x] Update FUNCTIONAL_SCOPE, V0_DECISIONS, CONTRACTS, ARCHITECTURE and the README
  together, clearly versioning changed semantics and defining compatibility.
  Include D07b's supported-format matrix and whole-snapshot limitations explicitly.

Acceptance: documented examples cover quarterly/annual selection, YTD exclusions,
multiple currencies/share units, total versus continuing-operations EPS, empty
outputs, conflicts and the meaning of an accepted published event.

**Exit criteria and handoff:** the target extraction/event contract and acceptance
policy are concrete enough for Milestones 2–3 to implement without inventing product
semantics. Include example full/partial/empty results, mixed HTML/PDF review,
duplicates, changed snapshots/new runs and unspecified share denomination.
Existing software checks still pass. Record chosen versions/field names, changed
documents and compatibility notes. Mark Milestone 1 complete, update README,
append its completion record and stop. Next session starts the isolated extractor.

## Milestone 2 — Implement the tested extraction configuration

**Prerequisite:** Milestone 1 complete and its contract versions/examples recorded.

**Read:** Milestone 1 completion record and updated contracts; current model/config
interfaces and adapter tests; referenced evals direct adapter, input-preparation
helpers, fiscal validation/schema, v6 prompt and candidate configuration.

**Session scope:** implement and independently test the new extractor boundary,
including its declared Python dependencies and finite verified input bounds.
Keep the current pipeline usable until Milestone 3 switches its contract; a
versioned module/configuration or explicit transition adapter is acceptable.
Do not fabricate legacy classification/evidence fields to fit the old schema.
Production Lambda packaging/infrastructure rollout is finalized in Milestone 6.

- [ ] Implement the direct OpenAI Luna adapter using the tested v6 prompt,
  structured response schema and inference settings; do not reuse the old NVDA
  extractor as though it implements this contract.
- [ ] Port the tested HTML-to-plain-text preparation and original-image handling,
  preserving document identity, package membership and ordering context.
- [ ] Use provider-specific document/image/request limits. Support HON's 34-image
  case; do not carry the Bedrock 20-image cap into the OpenAI path.
- [ ] Replace the provisional 128 KiB production budget with bounded limits
  informed by observed filing sizes and the selected provider. Never silently
  truncate a filing or omit selected attachments; enforce D07b's review-before-
  inference policy for unsupported PDF/TXT and oversized complete snapshots.
  Document the actual limits and artifact/bound-specific review reasons.
- [ ] Save the exact model, prompt/schema/preparation versions, request settings,
  response, token usage and timing with each distinguishable processing run.
- [ ] Keep SDK retry behavior consistent with persisted application retry budgets
  and distinguish transient failures, invalid outputs and review outcomes.
- [ ] Define how production and evals use the same versioned extraction behavior
  without a direct sibling import or a dependency on the evaluation application.
  Start with a traceable port and offline parity fixtures; defer a shared library
  unless maintenance needs justify it.

Acceptance: mocked provider tests exercise the real adapter and input preparation,
including table text, multiple attachments, 34 images, malformed output, provider
failure and whole-snapshot bounds. No credentials or paid calls in normal tests.

**Exit criteria and handoff:** mocked SDK tests demonstrate exact request settings,
plain-text/image preparation, complete membership, 34 images, strict fiscal output
handling and rejection of unsupported/oversized whole snapshots. All existing
checks remain green through the transition. Record module/API names, selected
dependency versions, prompt/schema/preparation identities, verified numeric bounds
and differences from the evals implementation. No deployment or paid benchmark
campaign. Mark complete, update README/checkpoint, append the record and stop.
Next session integrates this extractor with processing/storage/publication.

## Milestone 3 — Adapt acceptance, filing-specific results and persistence

**Prerequisite:** Milestone 2 complete with an independently tested extractor.

**Read:** prior completion records, finalized contracts and new extractor API;
processing pipeline/domain/validation, SQLite and DynamoDB repositories,
reconciliation, S3/SNS adapters, Lambda handler, CLI entry points and recovery tests.

**Session scope:** wire the new extraction contract end to end, replace canonical
cross-filing reconciliation with immutable filing-specific events, and implement
the approved operator CLI. Keep obsolete paths only where needed for the explicit
Milestone 4 removal. Document pending deployment configuration/packaging work.

- [ ] Implement the agreed acceptance policy and distinguish accepted, empty,
  review and technical-failure outcomes without claiming unperformed checks.
- [ ] Replace cross-filing reconciliation with immutable filing-snapshot results,
  retaining fiscal identity, currencies, exact decimal strings and source provenance.
- [ ] Preserve duplicate suppression and immutable history. Apply D05's final
  event identity and explicit-reprocessing policy; do not wait for or merge later
  disclosures before publishing a ready filing's accepted result.
- [ ] Version stored payloads/configuration and handle old records explicitly;
  changed model, prompt, schema or acceptance behavior needs a new work identity.
- [ ] Verify atomic outcome/publication commits, stale-worker fencing, independent
  concurrent filing processing and retry of saved publication payloads without
  new inference. A crash before response persistence can still require inference
  again; do not promise exactly-once provider invocation.
- [ ] Provide focused inspection and explicit reprocessing/redrive commands for
  stored jobs and immutable events, with distinguishable new inference runs.
- [ ] Update the offline filing demo/fixtures to exercise the new EPS arrays and
  `earnings.extracted` output, empty/review outcomes and duplicate handling.
- [ ] Wire the new consumer entry point and document required environment/secret
  references. Use mocks for SDK/Secrets Manager access; leave live setup to Milestone 6.

Acceptance: both storage adapters pass offline tests for the revised contract,
repeated deliveries, distinct snapshots/filings, concurrent updates and recovery
after publication failure. Equal EPS in different filings is not an input
duplicate. Review and failure outcomes never enter the accepted-event stream.

**Exit criteria and handoff:** one synthetic complete filing passes through the new
model boundary, checks, durable storage and publication with a stable event ID.
Both stores and the handler/CLI have offline coverage for duplicate delivery,
distinct snapshots/new runs, fencing/concurrency, errors and saved-payload recovery.
The new demo runs offline, and operator-command tests exercise mocked SDK/storage
without requiring a new production fixture mode.
Record actual persistence/version/key/index decisions, CLI syntax, entry points,
environment contract and remaining legacy references. Update README and
OFFLINE_PROCESSING/AWS_RUNTIME to distinguish implemented behavior from pending
deployment. Mark complete, append the record and stop before legacy removal.

## Milestone 4 — Retire superseded POC and evaluation paths

**Prerequisite:** Milestone 3 complete; replacement behavior and operator commands
are covered by passing tests.

**Read:** prior completion record, README, pyproject/package entry points,
Lambda dependency manifests/build scripts, legacy modules/tests/evaluations and
documentation links. Check consumers before deleting shared helpers.

**Session scope:** remove obsolete code, dependencies, commands and instructions
while keeping the new filing consumer and its tests intact. Historical shared-data
artifacts are preserved. Update references in both README and this roadmap if a
retired document is removed or renamed.

- [ ] Remove the NVDA watcher, SEC/IR acquisition adapters, legacy extraction,
  approximate-date event grouping, latency-flash commands and POC-only configuration.
- [ ] Remove the earnings-local evaluation runner, `earnings-eval` entry point,
  starter corpus and obsolete evaluation/golden-dataset instructions.
- [ ] Remove the runtime evaluation endpoint/mode where it exists solely to
  support the retired workflow; retain explicit production reprocessing identities.
- [ ] Remove unused dependencies, tests and packaging assets associated with those
  paths. Preserve or replace tests that protect production behavior.
- [ ] Rewrite README and runtime instructions around the filing consumer and link
  to `finbot-filing-evals` for experiments, corpus review and quality results.
  Include the D07b limitations, mixed-format example, configured numeric limits
  and operator steps for inspecting and explicitly reprocessing review outcomes.
- [ ] Preserve historical shared-data corpora, source artifacts and run results;
  retiring code does not require deleting operational data.

Acceptance: installed commands, documentation, dependencies and Lambda assets have
one focused purpose. No golden-label editor, benchmark runner or acquisition
workflow remains in earnings.

**Exit criteria and handoff:** package entry points, imports, dependencies, tests and
documentation serve the focused filing consumer. The old evaluator, NVDA watcher,
acquisition paths and evaluation-only runtime endpoint are removed, with useful
production regression coverage preserved. Run package/import/build checks and the
offline suite. Record deletions/replacements and current commands; confirm shared
data was untouched. Mark complete, update README/checkpoint, append the record and
stop. Next session verifies production-port parity against the saved quality result.

## Milestone 5 — Verify production parity against the existing quality baseline

**Prerequisite:** Milestone 4 complete; the focused implementation is the code
being verified.

**Read:** completion records, current extractor/configuration/validator and tests,
approved v6 config/prompt/schema and saved 50-case run/report references.

**Session scope:** verify implementation parity and compile durable release
evidence. This is not a new earnings-local evaluation framework or an obligatory
fresh model benchmark. Keep quality experiments in finbot-filing-evals.

- [ ] Reference the existing checked 50-filing v6 result (83/83 targets, 50/50 exact)
  as the D10a launch quality baseline; preserve its run and reviewed-data identity.
- [ ] Compare the production port's prompt, schema, input preparation, provider
  request settings and output handling to that measured configuration. Use
  traceable code/configuration comparisons and offline parity fixtures.
- [ ] Pass offline acceptance, empty-result, unsupported-input, retry, duplicate
  and publication-recovery checks, retaining the tested EPS/fiscal semantics.
- [ ] Perform only justified targeted live integration/parity checks within D10b's
  approved test scope/budget. A complete paid repeat of the 50 filings or a new
  20-filing study is not required solely to implement the migration.
- [ ] Evaluate any material prompt/schema/input/provider behavior change through
  `finbot-filing-evals` before treating the saved quality result as applicable.
  Keep prompt and provider/input changes separate so results remain attributable.
- [ ] Record production-port verification and source run IDs in release docs.
  Capture stage timing and test usage/cost; prove actual event receipt in Milestone 6.

Acceptance: the production extraction path demonstrably preserves the checked
configuration, software checks pass and the existing quality evidence is linked.
Activation additionally requires Milestone 6's live delivery proof. Further
unseen-filing evaluation is follow-up quality work rather than a launch blocker;
the tuned sample must still be described accurately as development-set evidence.

**Exit criteria and handoff:** record the exact production-port code/configuration,
source experiment/run/data references, prompt/schema/preparation hashes or equivalent
traceable comparisons, tests and intentional differences. Save the parity
evidence in a durable document such as `docs/PRODUCTION_PARITY.md` and link it from
the completion record. Document compatibility of every difference before relying
on the saved baseline. Charge any justified live checks to the cumulative USD 5
ledger. Mark complete, update README/checkpoint and stop. Next session prepares the
concrete release and completes live deployment prerequisites.

## Milestone 6 — Release and controlled activation

**Prerequisite:** Milestone 5 complete with linked production-parity evidence.
All prior implementation and cleanup work must be complete.

**Read:** all completion records, current README/contracts/runtime/parity docs,
CDK settings/stack/configuration, bundle/release scripts and CI/Deploy workflows.
Verify actual cloud and GitHub setup read-only; repository configuration is not
proof of deployment.

**Session scope:** finalize deployable packaging/infrastructure, resolve external
setup, prepare the exact reviewed release and perform the approved initial rollout.
D10b permits up to USD 5 total scoped API test spend across all sessions; use the
remaining ledger balance. Deployment/activation uses D12's protected release
approval. Do local preparation before requesting approval of a concrete release.

### 6.1 Prepare the release and inspect prerequisites

- [ ] Update Lambda runtime dependencies and Linux-compatible build assets for
  the new OpenAI/input-preparation path. Remove obsolete Bedrock permissions and
  bundles only after verifying they are unused. Validate packaged imports and the
  Pillow decoder in the target Lambda environment as described in runtime docs.
- [ ] Define the dedicated Secrets Manager secret, narrowly scoped worker access
  and ARN-only runtime configuration. Arrange secure key population without
  embedding its value in source, templates, command output or handoff notes.
- [ ] Define output SNS and D06b inspection SQS/subscription with 14-day retention,
  scoped delivery policies and operator inspection access.
- [ ] Define D11b's operational alarm/email subscription to `ilancooke@gmail.com`
  and stage timing/usage observability. Do not implement application spend alerts.
- [ ] Verify producer topic, source bucket, complete-snapshot contract and image
  compatibility; preserve producer ownership. Inspect existing stack/state before
  changing resource identities or applying any migration.
- [ ] Check GitHub OIDC roles, successful main CI and protected production approval.
  Prepare any missing bootstrap/operator setup as concrete reviewed work.
- [ ] Complete operator instructions for secret setup, alert confirmation,
  inspection, retry/redrive, new runs, pause and rollback.
- [ ] Run offline checks, package build, Lambda asset build, CDK synthesis and
  release-manifest verification. Rebuild assets after source/dependency changes.
  Use the exact successful-CI artifact and its visible infrastructure diff.
  If packaging/dependency changes affect extraction behavior, update Milestone 5's
  parity evidence and perform the required verification before seeking approval.

### 6.2 First deployment, with consumption disabled

- [ ] Obtain the release's required GitHub production approval, then deploy the
  reviewed artifact with consumption disabled. Record the release/commit, artifact
  identity, actual stack outputs, alias/version, resource ARNs and consumption state.
- [ ] Securely populate the new secret and verify runtime access/provider readiness.
  The user confirms the alarm email subscription; verify the alert path.
- [ ] Perform a controlled real-filing worker/integration smoke check within the
  remaining API test allowance and inspect the persisted result/output receipt.
  This direct check does not by itself verify the SQS trigger or complete Milestone 6.

### 6.3 Activate and prove queue-triggered delivery

- [ ] Inspect and record input backlog size/age and estimated catch-up time/usage.
  Apply D09b: process all retained notifications, do not silently purge or skip
  them, and resolve readiness/funding concerns with the operator before enablement.
- [ ] Prepare the enabled configuration, successful-CI artifact and reviewed
  release. Enable consumption through the normal protected release workflow.
  Keep the enabled setting in subsequent releases.
- [ ] Demonstrate actual enabled SQS-triggered processing of a real complete
  producer-compatible snapshot and receipt of its EPS-bearing event in inspection
  SQS. A suitable stored real snapshot can be explicitly submitted through the
  documented operator path if needed; preserve its genuine source identity.
- [ ] Record filing/snapshot, work/event IDs, extraction configuration, persisted
  outcome, SNS acknowledgment and queue receipt, plus available stage timings.
  Distinguish actual receipt time/metadata from the time an operator inspected it.
- [ ] Verify a completed input's duplicate delivery reuses its result/event ID.
  Retain offline publication-recovery evidence and confirm saved-payload retry
  behavior without introducing unnecessary paid failure experiments.
- [ ] Document normal updates: preserve consumption state, with no unconditional
  disable/enable hook. Review consumption settings when choosing rollback artifacts
  so an older disabled configuration is not accidentally restored.
- [ ] Update the cumulative live-test usage ledger, deployed-state record, README,
  runtime/runbook instructions, progress table and final completion record.

**Exit criteria and handoff:** all six milestones are complete only when
consumption is actually enabled and the real queue-triggered EPS event has been
received. Operators can inspect outcomes, recover failed work and deliberately
pause/roll back while retaining records. The completion record links exact release,
configuration, resource outputs and delivery evidence without secrets.

If awaiting credential population, email confirmation, release approval or a live
check, keep Milestone 6 **In progress**, record the exact outstanding action and
resume step, and stop there. A prepared release or partially deployed service is
not completion. Routine future updates use one normal release preserving state;
the disabled stage is specific to this first rollout.


## Milestone completion records

Milestone 1 is complete. Append one durable record at each session boundary;
preserve earlier records. Link completed milestones from
the progress table. For partial work, record which task is next and why exit
criteria have not yet been met.

Use this template (include actual paths/values, not just "tests passed"):

```markdown
### Milestone N — complete or in progress — YYYY-MM-DD

- Scope delivered: concrete behavior/documents changed.
- Repositories and versions: branch/commit when committed; otherwise changed files
  and uncommitted state. Preserve unrelated user work.
- Exit criteria: evidence for each, or exact outstanding criterion.
- Checks: exact commands, outcomes/counts, date and relevant environment.
- Engineering decisions: field/schema/configuration versions, module interfaces,
  input bounds, storage/index choices, CLI syntax and compatibility as applicable.
- Documentation: README/current checkpoint/progress updated; changed reference docs.
- Live actions: none, or exact release/resources/alias/consumption state and evidence.
- API test ledger: previous balance, known spend, unknown usage and remaining
  allowance; cumulative across sessions. Never record credentials.
- External actions needed: owner, requested action and how to verify completion.
- Next session: milestone and first concrete task; record partial work to resume.
```


### Milestone 1 — complete — 2026-10-25

- Scope delivered: formalized the approved fiscal EPS response, schema/business-rule
  acceptance and immutable filing-snapshot event contract; reconciled scope,
  decisions, architecture and current-versus-target runtime guidance. No runtime
  implementation or later milestone begun.
- Repository/version: `finbot-earnings`, branch `main`, starting HEAD
  `163a8a4682a200e2f38b3de2615ca22ad96ad8c0`; initially clean. Changes remain
  **uncommitted** in `README.md`, `ROADMAP.md`, `docs/FUNCTIONAL_SCOPE.md`,
  `docs/V0_DECISIONS.md`, `docs/CONTRACTS.md`, `docs/ARCHITECTURE.md`,
  `docs/OFFLINE_PROCESSING.md`, `docs/AWS_RUNTIME.md`, and new
  `docs/contracts/README.md`, `docs/contracts/earnings_eps_fiscal_v2.schema.json`,
  `docs/contracts/earnings_extracted_v1.schema.json`, `docs/contracts/examples.json`.
  No source, dependency, infrastructure or workflow changes. Sibling filings/evals
  checkouts were read-only and initially clean; no unrelated user changes found.
- Exit evidence: CONTRACTS and the documentation schemas specify fields/types,
  canonical encoding, stable work/event/record references and provenance. Synthetic
  examples cover full/partial/empty results, Q4 versus annual, YTD exclusion,
  total versus continuing operations, multiple currencies/unspecified share basis,
  duplicate/conflicting rows, mixed HTML/PDF and oversized snapshot review,
  repeated delivery, changed snapshots/amendments/configurations and fresh runs.
  The complete event validates; empty-result events are explicitly rejected.
- Engineering choices: response `earnings_eps.fiscal.v2` copied byte-for-byte;
  prompt `eps-v6`; preparation `filing-html-text-images-v1`; transport
  `openai-fiscal-v2-union-v1`; policy `fiscal-eps-acceptance-v1`; output
  `earnings.extracted` / `1.0`; processing record version 2. Identity hashes the
  new namespace, filing/snapshot, configuration version/content digest and run ID.
  Work/reference/event prefixes are `earnings-work:v2`, `earnings-processing:v2`,
  `earnings.extracted:1.0`. Canonical JSON/SHA-256 vector and full example are in
  CONTRACTS/examples. Reserve `eps-openai-luna-v6-v1` until Milestone 2 freezes its
  complete manifest; no persistent work uses it yet.
- Acceptance: both metric arrays required; at least one observation publishes;
  empty arrays complete `no_eps_extracted`; duplicate observation keys or multiple
  fiscal periods send the whole response to review. No invalid-row salvage or
  cross-filing gate. Invalid JSON/schema is a terminal failed result without
  automatic inference retry. Source semantics are prompt-guided; no independent
  per-fact verification, classification, calendar dates or share conversions.
- Compatibility: keep existing `eps-v0`/`explicit-prose-v1`, old company/period-end
  `earnings.validated` revisions and POC/evaluation behavior accurately labeled as
  implemented. No legacy record migration, overwrite, merge or republication.
  New documentation schemas are not loaded by runtime. Milestone 2 preserves the
  old path through a transition boundary; Milestone 3 switches the consumer.
- Reference evidence: read the producer-owned FilingReady contract and evals
  v6 prompt/fiscal schema/configuration, direct adapter/preparation and experiment
  report at evals commit `d105712812a3daaf0d958c0b9b180f41ca4703ce`.
  [CONTRACTS reference identity](docs/CONTRACTS.md#reference-identity) records exact
  file hashes. Baseline L5 run `20261023T145725Z-9ff8c84b`, 83/83 targets, 50/50
  exact, is development-set evidence. This is not production-port parity proof.
- Checks on 2026-10-25 using this repo's `.venv` (Python 3.11.17):
  `.venv/bin/python -m compileall -q src tests infra scripts` passed;
  `.venv/bin/python -m pytest` passed **171 tests**;
  `.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'`
  passed two schema checks, 16 response cases, six identity vectors, one full event,
  three input-policy examples and **75 local links/fragments across 11 Markdown files**;
  `git diff --check` passed. The [checker source](docs/contracts/README.md) is
  durable and offline. It verifies specification consistency, not runtime/provider
  behavior. Source-diff inspection confirms only the listed documentation files.
- Documentation: README status/table/map and ROADMAP checkpoint/table/checkboxes
  now agree; scope/contracts/architecture/acceptance and offline/runtime docs are
  reconciled. Legacy evaluator/golden instructions remain for Milestone 4 removal,
  explicitly superseded by README and runtime guidance.
- Live actions: none. No provider calls, deployed-state inspection, AWS/GitHub
  mutation or shared-data changes. API ledger: previous USD 5, spent USD 0,
  no unknown usage introduced, **USD 5 remaining**, cumulative across sessions.
- Deferred engineering: verified finite input/image/request/token/response bounds,
  SDK pins/attempt budgets and preparation/adapter hashes are Milestone 2; physical
  storage/index/CLI/env choices Milestone 3; packaging/secret/inspection queue,
  confirmed alarm email and reviewed deployment/activation Milestone 6. These are
  planned milestone deliverables, not unresolved product decisions or Milestone 1
  blockers. Actual cloud/GitHub/account access remains unverified.
- External action needed now: none. Milestone 6 will require secure credential
  population, email confirmation and protected release approval after concrete
  release preparation; do not request them for this milestone.
- Next session: **Milestone 2 only**. Read this record, finalized contracts and
  source references, then implement/test the direct Luna extractor separately from
  the legacy pipeline, verify complete input bounds including HON 34 images and
  mixed HTML/PDF review, and freeze traceable configuration/dependencies. Stop
  before consumer/storage/CLI integration.


## Reference sources and implementation constraints

Existing defaults to retain unless a decision above changes them: at-least-once
input/output delivery; work identity includes snapshot and complete extraction
configuration plus explicit run identity; durable result before publication;
publication retries reuse identical payloads without inference; review/failure outcomes
remain inspectable; ordinary tests are offline; no production AWS changes through
AWS MCP. Use AWS MCP only for documentation and read-only inspection.

The implementing agent should verify and record request/image/token limits,
Lambda timeout/memory/concurrency, queue visibility/retention, lease and retry
budgets, item/event size bounds, SDK versions, network egress, secret permissions,
and alarm thresholds. These are engineering tasks, not reasons to invent new
product scope or ask the user to choose SDK parameters. Any limit that rejects
an otherwise supported real filing must be visible and testable.

Primary handoff references:

- [Scope](docs/FUNCTIONAL_SCOPE.md), [v0 decisions](docs/V0_DECISIONS.md),
  [contracts](docs/CONTRACTS.md), [architecture](docs/ARCHITECTURE.md),
  [runtime/release setup](docs/AWS_RUNTIME.md) and
  [current processing policy](docs/OFFLINE_PROCESSING.md).
- [Producer-owned FilingReady contract](../finbot-filings/docs/FILING_READY.md).
- [Experiment report](../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md),
  [candidate config](../finbot-filing-evals/configs/openai-luna-6-prompt-v6-sample-50.json),
  [v6 prompt](../finbot-filing-evals/prompts/eps-v6.txt) and
  [fiscal schema](../finbot-filing-evals/src/finbot_filing_evals/evaluation/schemas/earnings_eps_fiscal_v2.schema.json).
- Extraction behavior to port is in the evals package's `evaluation/direct.py`,
  `evaluation/bedrock.py` (shared input preparation) and related helpers; its
  evaluation runner and label editor are not production dependencies.
- Shared reviewed bundle: `$FINBOT_DATA_ROOT/filing-evals/golden/earnings-eps-50-v1`.
  Candidate saved run: `filing-evals/runs/20261023T145725Z-9ff8c84b` under that
  data root. Preserve labels, raw documents, images and historical run receipts.

## Shared engineering and deployment prerequisites

Each session implements its selected milestone, not the whole roadmap or a new
decision questionnaire. Formalize exact field names, schema/configuration versions,
stable work/event ID encoding, status-query storage/indexes, numeric limits and operator
command syntax as engineering details consistent with the approved register.
Use the fiscal schema and local structural validation in the evals package's
`evaluation/contracts.py` as port references; retain the approved single-period
semantics and do not apply the old independent-prose evidence gate to launch EPS.

Current filing-code starting points are `src/finbot_earnings/processing/`
(pipeline, domain/contracts, validation, repositories, adapters and Lambda handler),
`infra/cdk/` (stack/settings/configuration), `scripts/` (Lambda build/release
verification) and `.github/workflows/`. Legacy acquisition/extraction modules and
the `evaluation/` subtree are removed only after replacement behavior is covered.
Milestone 1 reconciled the scope/acceptance/contract/architecture documents and
labeled current offline/AWS behavior separately from target semantics. The approved
roadmap still takes precedence; code remains the old NVDA/Nova/canonical-event
implementation until subsequent milestones.

Operational setup is still required; it is not an unresolved design choice:

- Inspect actual AWS stack/source-topic/bucket state and producer compatibility
  read-only. Preserve existing stateful resources/logical IDs unless a deliberate
  migration is included in the reviewed diff. Record actual outputs after release.
- Verify GitHub main-branch CI, OIDC roles, protected production environment and
  permissions. Prepare any missing setup as a concrete reviewed change.
- Set up the dedicated secret and have the credential supplied securely; record
  name/ARN and readiness without its value. OpenAI project access, funding and
  account quotas must be checked through the appropriate operator setup.
- Provision the output inspection queue/subscription and the alarm subscription.
  The user must confirm the email subscription; record delivery verification.
- Inspect retained backlog before initial enablement and apply D09b. Do not wait
  for a naturally occurring future filing to prove the pipeline if a suitable
  stored real snapshot can be explicitly processed for the approved live check.
  A direct worker smoke invocation does not itself prove the SQS trigger; final
  acceptance must also demonstrate actual enabled queue-triggered processing.
- Maintain a live-test usage ledger within the USD 5 allowance. Ongoing provider
  funding is user-managed; do not build application spend alarms or a spending cap.

Run checks from this package's own environment, and run each other touched repo's
checks separately. Current offline checks:

```bash
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
git diff --check
```

Rebuild changed Lambda dependencies/assets before synthesis; use the build,
package and release verification commands in AWS_RUNTIME/CI as they are updated.
Do not execute a deployment until the exact release has its required approval.
Once that approval/authorization exists, do not ask for duplicate chat permission.

For current API/deployment assumptions consult the
[OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna),
[structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs)
and [AWS Lambda/SQS documentation](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html).
Documentation checks are not proof of account access or deployed configuration.

## Approved launch limitations — required documentation

The following decisions describe the planned launch behavior; the existing
Nova/POC implementation has not yet been migrated to enforce them.

- Supported source formats are HTML plus original JPEG/PNG/GIF supporting images.
  TXT, PDF and other unsupported selected formats go to review for launch.
- The input unit remains the complete selected FilingReady snapshot. One
  unsupported member causes the whole snapshot to go to review before inference,
  even if another HTML document might contain readable EPS. No EPS event is emitted.
- Oversized snapshots likewise go to review before inference. Documents are not
  truncated and selected attachments are not discarded to fit provider limits.
- Exact finite document/image/request limits must be documented after provider
  verification and implementation. The current Nova limits (128 KiB/five documents/
  20 images) are not the approved limits for the direct OpenAI implementation;
  launch bounds must accommodate the evaluated HON 34-image case.

Milestones 1–4 must put the support matrix, examples, configured numeric bounds,
review reason codes and explicit reprocessing procedure into the README,
FUNCTIONAL_SCOPE/CONTRACTS, AWS_RUNTIME and operator guidance. An operator must be
able to identify which selected artifact or bound caused review. Include the
mixed HTML/PDF example in docs and offline tests. Do not describe deferred formats
as accepted, silently skipped or automatically retried when they require review.

## Purpose and package boundaries

`finbot-earnings` consumes complete stored `FilingReady` snapshots from
`finbot-filings`, extracts earnings observations, applies a documented acceptance
policy, persists processing outcomes and immutable filing-specific extraction
events, and publishes accepted results. Discovery and document acquisition belong
to `finbot-filings`. Cross-filing canonical aggregation is deferred under D04.

The user prioritizes end-to-end discovery, extraction and reporting latency.
Start work when a complete snapshot is ready and publish its accepted EPS without
waiting for later filings, company-period merging or a human review step for an
otherwise accepted result. Preserve required durable writes and complete inputs.
Measure stage durations and available upstream-to-output timestamps so queueing,
acquisition, inference and publication delay can be distinguished. The current
FilingReady envelope supplies `filed_at` and `ready_at`; filing acceptance is not
the discovery timestamp. Use actual discovery timestamps only when available,
mark unavailable measurements explicitly and do not invent timing data. D11c–D11d
approve launch-and-measure with bounded engineering settings; a numeric latency
SLA or peak-volume guarantee is not a prerequisite for launch.

`finbot-filing-evals` owns golden datasets, label review, model/prompt experiments,
scoring and comparison reports. Earnings should retain ordinary offline unit,
contract and recovery tests, but should not maintain a second evaluation workflow.
Packages remain independent; do not import code directly from a sibling checkout.

## Evidence informing this plan

The [model experiment report](../finbot-filing-evals/docs/MODEL_EXPERIMENT_REPORT.md)
records the candidate baseline: Luna 6 through the direct OpenAI API, prompt v6,
HTML-derived plain text plus all original supporting images, medium reasoning
effort and a 4,096-token output budget. Its 50-filing run matched all 83 fiscal EPS
targets, with an estimated total cost of $0.15944 and 164.13 seconds of recorded
extractor time. Earlier v4 runs matched all 20 targets on 13 filings three times.

Both samples were used during development; these results are not held-out
accuracy. The report measures fiscal EPS extraction, not independent evidence
verification, classification quality or production reliability. Its Nova results
use Nova 2 Lite, whereas earnings currently configures Nova Lite v1. Preserve the
saved experiments as historical evidence rather than treating them as validation
of the current earnings adapter. Budget fresh documents separately from cached
repeats.

## Existing foundations to retain or adapt

- [x] Complete filing-snapshot parsing and manifest identity checks.
- [x] Filing-level processing with injected document, model, storage and publication adapters.
- [x] Durable model responses, bounded retries, lease fencing and work deduplication.
- [x] SQLite reference storage and DynamoDB persistence with atomic event/outcome commits.
- [x] Canonical revisions/conflict review in the existing implementation; replace
  cross-filing aggregation with D04's filing-specific results while retaining
  immutable history and recoverable publication of saved payloads.
- [x] S3/SNS adapters, an SQS Lambda handler, CDK definitions and CI/release workflows.
- [x] Offline tests for processing, adapters, concurrency and publication recovery.

The legacy NVDA watcher and earnings-local evaluation runner still coexist with
this core. Repository documentation records the earnings service as undeployed;
committed production configuration disables consumption. Recheck actual cloud
state before release work.

## Decision register — D01–D12 approved

All entries below were approved on 2026-10-25. The implementing agent can choose
and document engineering details within these constraints without reopening the
settled decisions. Material changes to scope, extraction semantics or release
policy need an explicit new decision. Record subsequent decisions with dates and
their consequences, and distinguish them from implementation progress.

| ID | Decision topic | Approved decision |
| --- | --- | --- |
| D01 | What permits publication: structural/business-rule acceptance of the tested extraction, or independently verified evidence for each fact? What should the event be called? | **Approved 2026-10-25: option 1.** Publish model extraction after schema and business-rule checks, retain complete source references and the model response, and use event type `earnings.extracted` with a new versioned contract. Independent per-fact evidence verification is not a launch requirement. Do not describe the event as independently fact-verified. Per-fact citations/verification remain a separate enhancement requiring evaluation. |
| D02 | Is explicit earnings/non-earnings classification required, or is EPS extraction sufficient? What happens with empty arrays or only one metric? | **Approved 2026-10-25.** Preserve the tested two-array response without adding an earnings-classification field. Publish both metrics when accepted observations exist for both, or the available metric when only one is present; an absent metric stays an empty array. When both arrays are empty, persist `no_eps_extracted`, acknowledge the input and publish nothing. This does not establish that the filing contains no earnings. Do not automatically retry a completed empty result; explicit reprocessing remains available. |
| D03a | Do we adopt the tested EPS definitions and fiscal-period selection rules? | **Approved 2026-10-25.** Adopt prompt v6's reported/adjusted diluted EPS rules, preserving signs, precision and disclosed currencies. Use the disclosed total for reported EPS when both total and continuing-operations EPS appear. Use the primary explicitly disclosed adjusted measure without calculating it. Select the latest standalone fiscal quarter for quarterly reports/releases and the latest full fiscal year for annual-only reports/releases; when both Q4 and full-year results appear, select Q4 only. Exclude prior-period comparisons, cumulative/YTD amounts and guidance. Use issuer fiscal year/quarter identity without requiring calendar dates. |
| D03b | Must ordinary-share versus ADR/ADS denomination be represented explicitly at launch? | **Approved 2026-10-25: option 1.** Keep the tested schema, preserving disclosed EPS values and currencies without adding a share-basis field for launch. Retain source references, document that share denomination is unspecified and perform no conversions. Currency alone cannot resolve every unit ambiguity. D04 must account for this limitation; do not assume observations on different share bases are equivalent during cross-filing reconciliation. Explicit share denomination is a later schema/prompt enhancement requiring evaluation in `finbot-filing-evals`. |
| D04 | Is the published object a result for each filing snapshot, or a canonical company/fiscal-period event across filings? | **Approved 2026-10-25: option 1.** Publish filing-snapshot extraction results. An earnings release and a later periodic report each produce their own event even for the same company/fiscal period; retain issuer/fiscal identity for downstream association, without automatic cross-filing merging. Duplicate delivery of the same input remains suppressed. The user prioritizes combined discovery, extraction and reporting latency: process each complete ready snapshot immediately without waiting for later filings or reconciliation. Canonical company-period aggregation is deferred. Exact publication identity/reprocessing semantics are settled under D05. |
| D05 | How do duplicate delivery, changed snapshots, amendments and explicit reprocessing affect filing-specific publication? Must older published schemas be supported? | **Approved 2026-10-25.** One immutable output event per accepted snapshot/configuration/run identity. Duplicate delivery reuses the saved result and event ID; publication retries resend the identical saved event without new inference. Transport may repeat the identical payload; consumers deduplicate by event ID, not EPS value. Changed snapshots and amended filings are independent work and publish accepted results even when EPS equals an earlier filing. Explicit reprocessing uses a new run/configuration identity and publishes a new traceable event if accepted, preserving earlier results. No cross-filing value-conflict gate, automatic legacy POC migration or automatic legacy republication. Verify actual stored state and use a new contract/configuration namespace. Recovery before response persistence can require another model call; exactly-once inference is not promised. |
| D06a | What exactly travels in an event? | **Approved 2026-10-25.** Include event type `earnings.extracted`, schema version and immutable event ID; issuer CIK/ticker/name; source filing ID/snapshot ID/form type and filing/readiness timestamps; the tested reported/adjusted EPS arrays with decimal values, currencies and fiscal identifiers; model, extraction configuration version, run ID, acceptance policy and processing-record reference; extraction start/end and event-creation timestamps. Include EPS directly, not just a pointer. No canonical company-period revision counter. Keep raw model responses, original documents and full manifests in processing/source storage accessible through references. Actual publication acknowledgment and subscriber receipt times are recorded separately so retries resend an identical event. |
| D06b | Who receives the event and how is end-to-end delivery verified? | **Approved 2026-10-25.** Use an earnings-owned SQS inspection queue subscribed to the output SNS topic, with 14-day message retention, for the Milestone 6 delivery check and later operator inspection. Processing storage remains the historical record; the queue is not a permanent archive. Receipt must be observable beyond an SNS publish acknowledgment. Inspection is asynchronous and publication does not wait for a human to read an event. No downstream strategy application is required. |
| D07a | Which model and extraction configuration ship at launch? | **Approved 2026-10-25.** Use the measured direct OpenAI `gpt-6-luna` configuration, v6 prompt and tested fiscal EPS schema, with HTML-derived plain text plus original supporting images, medium reasoning effort and a 4,096-token maximum output budget. One combined extraction request per complete supported snapshot; preserve tested transport settings and version the port. No automatic fallback model or model-based repair loop. Bounded retries for temporary technical failures and response-persistence recovery are separate operational behavior, not extra planned extraction stages. Further latency tuning is evaluated in `finbot-filing-evals`. |
| D07b | Which source formats are supported at launch, and what happens to unsupported or oversized snapshots? | **Approved 2026-10-25, with explicit documentation required.** Support HTML documents and original JPEG/PNG/GIF supporting images, matching the evaluated workflow. Defer TXT and PDF. If any selected artifact is unsupported, or the complete snapshot exceeds supported bounds, persist a review-required outcome before inference and publish no EPS event. This includes an HTML package containing a selected PDF; do not extract from just the HTML portion. Never truncate documents or drop selected files. Choose provider-specific finite limits that accommodate evaluated cases, including HON's 34 images. Document these limitations and the whole-snapshot policy in README, scope/contracts, runtime configuration and operator guidance. |
| D08a | Do we retain the current cloud and release architecture? | **Approved 2026-10-25.** Retain producer SNS → earnings SQS → Python Lambda → earnings SNS → D06b inspection SQS. The worker reads all selected snapshot documents from existing source S3 storage, calls the approved direct OpenAI extractor, persists processing outcomes and immutable events in DynamoDB, then publishes accepted events immediately after persistence. Keep GitHub Actions/CDK releases, immutable Lambda versions behind a production alias and SQLite for offline development/tests. Measure queue, invocation, extraction and publication delays against the end-to-end latency priority. |
| D08b | Which AWS account and region host the service? | **Approved 2026-10-25.** Use AWS account `559007813222`, region `us-east-1`, and earnings-owned stack `finbot-earnings-prod`. Reuse the configured upstream topic `finbot-prod-filing-ready` and existing finbot-filings source bucket (`finbot-prod-state-artifacts82dd59a1-8gt63rcgmaua` in the current configuration). Verify actual deployed resources, producer contract and permissions before release; committed configuration is not proof of deployment. |
| D08c | How are provider credentials supplied and provisioned? | **Approved 2026-10-25: new dedicated secret.** Include setup of a new dedicated AWS Secrets Manager secret containing an OpenAI project credential. Deployment configuration references its ARN; the Lambda role can retrieve that specific secret at runtime with narrowly scoped permissions. Supply the value through secure setup, keeping it out of Git, logs, chat and documentation. Record only name/ARN, ownership and setup status. Verify the secret is populated and runtime access works before activation; no credential or secret has been created during this design discussion. |
| D09a | Which filing population is processed, and is historical backfill required? | **Approved 2026-10-25.** Process new FilingReady snapshots received from finbot-filings across its configured issuer universe; finbot-filings owns company selection and discovery. Apply the agreed format/size policy to every snapshot, recording review outcomes for unsupported inputs. No separate earnings ticker list, automatic historical backfill or scan of existing S3 filings. Historical processing is an explicit operator action using complete immutable manifests and distinct work/run identity. |
| D09b | What happens to messages accumulated while consumption is disabled? | **Approved 2026-10-25.** Process all retained queued notifications when consumption is enabled, including those accumulated while disabled. Before activation inspect backlog size/age and estimate catch-up time/cost against the agreed release budget and latency requirements; resolve incompatibilities before enabling consumption. Never silently purge or skip retained messages. A large backlog can delay fresh filings, so report catch-up delay separately from normal operating latency. This handles notifications already delivered to earnings and does not introduce historical S3 backfill. |
| D10a | What quality checks gate activation? | **Approved 2026-10-25: option 1, using the existing checked 50 filings.** Use the saved reviewed 50-filing v6 result (83/83 targets, 50/50 exact) as the launch extraction-quality baseline. A new 20-filing study is not a launch requirement. Verify that the production port preserves the tested prompt, schema, input preparation and inference settings through traceable code/configuration comparison and offline parity checks, pass software correctness/recovery tests, and confirm live EPS delivery to the inspection queue. Do not automatically repeat the complete paid 50-filing experiment solely for migration; justify targeted live parity checks under the agreed test budget when needed. Changes that materially alter tested behavior require evaluation in `finbot-filing-evals` before relying on the saved baseline. Preserve report/run references and implementation identity. The existing tuned sample is not held-out evidence or a universal accuracy guarantee. |
| D10b | What paid-test budget and scope are authorized? | **Approved 2026-10-25: up to USD 5 total API spend.** Covers controlled integration and event-delivery tests plus justified targeted live parity checks. No new held-out campaign or blanket 50-filing rerun is required under D10a. Track usage/cost and remaining estimate; stop dispatching tests conservatively before the budget is exhausted and resolve unknown usage rather than treating it as free. Normal production and backlog processing are separate from this testing budget. This decision approves the scoped API test spend; cloud deployment/activation remains subject to D12. |
| D11a | Which operator tools are required at launch? | **Approved 2026-10-25.** Provide a focused CLI to inspect processing runs/events including sources, saved response, outcome/reasons, usage and timings; list review-required, failed and empty-result outcomes; resume failed processing from saved checkpoints; explicitly request a fresh extraction with a new run identity; and inspect output-queue events. Clearly document commands that incur inference charges or publish events. A web review interface remains future work. Choose a deliberate status-listing/index design during implementation; the current table has no review-list index. |
| D11b | Where should operational alerts be delivered? | **Approved 2026-10-25.** Send operational alerts through the earnings alarm SNS topic to `ilancooke@gmail.com`. Cover processing/event-delivery failures, dead-lettered messages, excessive input-queue delay and worker errors. Empty/review-required outcomes remain visible through the CLI. The recipient must confirm the SNS email subscription before alerts begin; record confirmed delivery/setup status before activation. No subscription or email has been sent during this design discussion. |
| D11c | Is a numeric latency target required before launch? | **Approved 2026-10-25: launch and measure.** Treat latency as an explicit optimization priority, measuring filing readiness → event publication plus queueing, input preparation, extraction, persistence and publication stages, and upstream discovery/acquisition delay where timestamps are available. Use observed delays to identify bottlenecks and establish a realistic numeric target after launch; a hard numeric SLA is not a launch requirement. Report backlog catch-up separately. Preserve the one-call immediate-publication path and do not silently discard an otherwise accepted result because it is slow. |
| D11d | What throughput and concurrency constraints guide implementation? | **Approved 2026-10-25.** Let the implementing agent choose and document bounded worker concurrency, timeouts, memory and retry settings using existing producer traffic, actual OpenAI account rate limits, agreed operating spend constraints, and observed queue delay/extraction duration. Start with controlled concurrency, then tune to reduce queue delay within provider/budget constraints. No specific numeric peak-volume requirement was supplied. Concrete queue visibility, lease and payload bounds are implementation decisions that must remain finite and consistent with worker timing and complete-snapshot handling. |
| D11e | What ongoing production/backlog API budget and cost controls apply? | **Approved 2026-10-25: user-managed provider spending.** The user monitors API spend independently in OpenAI's UI and controls funding by replenishing funds there. Do not implement the proposed USD 10 monthly application budget, USD 8/10 spend-alert thresholds, application-side spending cap or billing/replenishment automation. Retain usage/timing provenance and handle provider billing/quota failures through the documented bounded failure/recovery and operational-alert path. Record this as the user's funding-control arrangement, not a verified guarantee about exact provider billing cutoff behavior. D10b's USD 5 API test budget remains separate and in force. AWS infrastructure costs are separate from OpenAI funding. |
| D12a | Is a separate staging stack required, and when is consumption disabled? | **Approved 2026-10-25: production-only initial rollout, with a one-time disabled stage.** Use the existing production stack, deploy initially with consumption disabled, complete controlled live verification, then enable consumption. A separate staging stack is not required for launch. Routine updates preserve the configured consumption state and must not automatically disable/re-enable processing on every change. Once activated, keep the enabled setting in subsequent release configurations. Pausing is a deliberate operational action for a change that needs it, not a mandatory release stage. Verify OIDC roles, protected environment, upstream contract, provider access, dedicated secret, inspection queue and confirmed alarm email before first activation. |
| D12b | What release review and approval workflow should the next session follow? | **Approved 2026-10-25.** Successful CI builds the exact release artifact; the manually dispatched Deploy workflow verifies it and shows the infrastructure diff; GitHub's protected production environment requires approval before deployment. The agent prepares implementation, checks and concrete release evidence before seeking approval. First deployment and first activation follow D12a's explicit initial rollout steps. Ordinary updates use one normal release preserving consumption state, without a disable/enable cycle or redundant chat confirmation for already authorized actions. This approves the release policy, not an unreviewed deployment of unfinished code. |

