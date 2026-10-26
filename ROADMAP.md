# finbot-earnings roadmap

Updated 2026-10-25. **All migration decisions D01–D12 are approved. Milestones 1–5
are complete; Milestone 6 is in progress.** This document is the durable plan
and checkpoint for separate agentic sessions. README describes implemented status; the approved
decision register below governs the target. Design documents were reconciled
in Milestone 1; Milestone 2 adds the frozen extractor; Milestone 3 integrates
the fiscal consumer/storage/publication/CLI. Milestone 4 removes legacy paths. A decision approval is not a
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

- Date: 2026-10-26. Milestones **1–5 complete; 6 in progress**. Recovery and the
  disabled release/direct smoke passed. Source activation is prepared, not deployed.
- Repository: clean starting `main` at `829d1a98a36e36e68cac6b8f3939b0f29fc584f7`.
  Current uncommitted changes set consumption_enabled=true, assert the activated
  default while retaining explicit-pause coverage, and reconcile release/evidence
  docs. No extractor/runtime/dependency/identity change. The user commits/pushes
  directly to main and runs cloud/GitHub mutation commands step by step.
- Recovery: the failed stack record was removed while preserving all eight Retain
  resources. Reviewed import completed; recovered stack
  `finbot-earnings-prod/936a6ac0-d180-11f1-a965-12ffd3ec13f5`, termination protection
  true. Protected Deploy **40402075873** succeeded from successful main CI
  **40397320222** for `829d1a9...`. Exact release/artifact/resource identities are in
  [RELEASE_EVIDENCE.md](docs/RELEASE_EVIDENCE.md).
- Actual deployed state: production alias version **1**, SQS mapping
  `7d94af68-1f22-4d3b-b9e9-aac774412007` **Disabled**, batch one, source maximum two,
  no Lambda reservation. The next protected release must enable this mapping;
  routine updates retain enabled consumption. Source true is not live activation.
- Setup: dedicated secret AWSCURRENT populated securely, runtime secret/source/
  provider access verified. Alarm email confirmed and controlled SNS test received.
  User-reported model limits: 2M TPM, 5,000 RPM, 50,000 IPM and 20M TPD as displayed.
  SQS counts visible/in-flight/delayed were **0/0/0** before activation preparation;
  no retained catch-up work/cost observed. Recheck for arrivals before approval.
- Smoke: genuine HON filing `0000773840-26-000143`, all **35** selected originals
  including **34 images**, accepted reported USD **2.08**, FY2026 Q3; adjusted empty.
  Work/event suffix `ea14fccac9f3736edbef289158d689af195b5f818f822c744096800011ac87d2`.
  One provider attempt and publication; SNS acknowledgment and actual inspection
  SQS receipt verified. This synchronous operator replay does **not** prove the
  enabled queue trigger. Persisted receipt/full IDs/usage/timings are in the evidence.
- Verification: **180 tests** pass, compilation and strict offline CDK synthesis
  pass. Template comparison finds only mapping Enabled=false to true and its
  ConsumptionEnabled output false to true. Resource identities/settings, no-reserve
  policy and frozen fiscal bytes/pins/digest remain unchanged; prior Linux parity
  applies. Explicit pause still preserves stateful resources.
- API ledger: 59,518 input tokens (59,515 cache write + 3 ordinary), 105 output,
  complete usage, estimated spend **USD 0.007492175**; estimated remaining
  **USD 4.992507825**, no unknown attempts. Provider UI displayed USD 0.01 decrease.
  This estimate is separate from the invoice and user-managed production funding.
- Next action: user reviews/commits/pushes activation to main, waits for exact
  successful CI, reviews the prepared diff and approves the protected enabled
  release. Recheck backlog, verify actual Enabled state, then prove fresh genuine
  queue-triggered EPS extraction/output receipt and duplicate reuse. Record final
  deployed identities and cumulative usage, mark M6 complete only after those pass.
  Latest [handoff](#milestone-6--in-progress--activation-prepared--2026-10-26).


Replace this checkpoint after each milestone; preserve historical evidence below.

## Milestone progress

| Milestone | Status | Required starting state | Completion record |
| --- | --- | --- | --- |
| 1 — Contracts and documentation | Complete | Approved decisions below | [2026-10-25 completion](#milestone-1--complete--2026-10-25) |
| 2 — Tested extractor | Complete | Milestone 1 complete | [2026-10-25 completion](#milestone-2--complete--2026-10-25) |
| 3 — Filing consumer integration | Complete | Milestone 2 complete | [2026-10-25 completion](#milestone-3--complete--2026-10-25) |
| 4 — Legacy cleanup | Complete | Milestone 3 complete | [2026-10-25 completion](#milestone-4--complete--2026-10-25) |
| 5 — Production parity evidence | Complete | Milestone 4 complete | [2026-10-25 completion](#milestone-5--complete--2026-10-25) |
| 6 — Reviewed release and activation | In progress | Milestone 5 complete | [Activation handoff](#milestone-6--in-progress--activation-prepared--2026-10-26) |

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

- [x] Implement the direct OpenAI Luna adapter using the tested v6 prompt,
  structured response schema and inference settings; do not reuse the old NVDA
  extractor as though it implements this contract.
- [x] Port the tested HTML-to-plain-text preparation and original-image handling,
  preserving document identity, package membership and ordering context.
- [x] Use provider-specific document/image/request limits. Support HON's 34-image
  case; do not carry the Bedrock 20-image cap into the OpenAI path.
- [x] Replace the provisional 128 KiB production budget with bounded limits
  informed by observed filing sizes and the selected provider. Never silently
  truncate a filing or omit selected attachments; enforce D07b's review-before-
  inference policy for unsupported PDF/TXT and oversized complete snapshots.
  Document the actual limits and artifact/bound-specific review reasons.
- [x] Save the exact model, prompt/schema/preparation versions, request settings,
  response, token usage and timing with each distinguishable processing run.
- [x] Keep SDK retry behavior consistent with persisted application retry budgets
  and distinguish transient failures, invalid outputs and review outcomes.
- [x] Define how production and evals use the same versioned extraction behavior
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

- [x] Implement the agreed acceptance policy and distinguish accepted, empty,
  review and technical-failure outcomes without claiming unperformed checks.
- [x] Replace cross-filing reconciliation with immutable filing-snapshot results,
  retaining fiscal identity, currencies, exact decimal strings and source provenance.
- [x] Preserve duplicate suppression and immutable history. Apply D05's final
  event identity and explicit-reprocessing policy; do not wait for or merge later
  disclosures before publishing a ready filing's accepted result.
- [x] Version stored payloads/configuration and handle old records explicitly;
  changed model, prompt, schema or acceptance behavior needs a new work identity.
- [x] Verify atomic outcome/publication commits, stale-worker fencing, independent
  concurrent filing processing and retry of saved publication payloads without
  new inference. A crash before response persistence can still require inference
  again; do not promise exactly-once provider invocation.
- [x] Provide focused inspection and explicit reprocessing/redrive commands for
  stored jobs and immutable events, with distinguishable new inference runs.
- [x] Update the offline filing demo/fixtures to exercise the new EPS arrays and
  `earnings.extracted` output, empty/review outcomes and duplicate handling.
- [x] Wire the new consumer entry point and document required environment/secret
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

- [x] Remove the NVDA watcher, SEC/IR acquisition adapters, legacy extraction,
  approximate-date event grouping, latency-flash commands and POC-only configuration.
- [x] Remove the earnings-local evaluation runner, `earnings-eval` entry point,
  starter corpus and obsolete evaluation/golden-dataset instructions.
- [x] Remove the runtime evaluation endpoint/mode where it exists solely to
  support the retired workflow; retain explicit production reprocessing identities.
- [x] Remove unused dependencies, tests and packaging assets associated with those
  paths. Preserve or replace tests that protect production behavior.
- [x] Rewrite README and runtime instructions around the filing consumer and link
  to `finbot-filing-evals` for experiments, corpus review and quality results.
  Include the D07b limitations, mixed-format example, configured numeric limits
  and operator steps for inspecting and explicitly reprocessing review outcomes.
- [x] Preserve historical shared-data corpora, source artifacts and run results;
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

- [x] Reference the existing checked 50-filing v6 result (83/83 targets, 50/50 exact)
  as the D10a launch quality baseline; preserve its run and reviewed-data identity.
- [x] Compare the production port's prompt, schema, input preparation, provider
  request settings and output handling to that measured configuration. Use
  traceable code/configuration comparisons and offline parity fixtures.
- [x] Pass offline acceptance, empty-result, unsupported-input, retry, duplicate
  and publication-recovery checks, retaining the tested EPS/fiscal semantics.
- [x] Perform only justified targeted live integration/parity checks within D10b's
  approved test scope/budget. A complete paid repeat of the 50 filings or a new
  20-filing study is not required solely to implement the migration.
- [x] Evaluate any material prompt/schema/input/provider behavior change through
  `finbot-filing-evals` before treating the saved quality result as applicable.
  Keep prompt and provider/input changes separate so results remain attributable.
- [x] Record production-port verification and source run IDs in release docs.
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

- [x] Update Lambda runtime dependencies and Linux-compatible build assets for
  the new OpenAI/input-preparation path. Remove obsolete Bedrock permissions and
  bundles only after verifying they are unused. Validate packaged imports and the
  Pillow decoder in the target Lambda environment as described in runtime docs.
- [x] Define the dedicated Secrets Manager secret, narrowly scoped worker access
  and ARN-only runtime configuration. Arrange secure key population without
  embedding its value in source, templates, command output or handoff notes.
- [x] Define output SNS and D06b inspection SQS/subscription with 14-day retention,
  scoped delivery policies and operator inspection access.
- [x] Define D11b's operational alarm/email subscription to `ilancooke@gmail.com`
  and stage timing/usage observability. Do not implement application spend alerts.
- [x] Verify producer topic, source bucket, complete-snapshot contract and image
  compatibility; preserve producer ownership. Inspect existing stack/state before
  changing resource identities or applying any migration.
- [x] Check GitHub OIDC roles, successful main CI and protected production approval.
  Prepare any missing bootstrap/operator setup as concrete reviewed work.
- [x] Complete operator instructions for secret setup, alert confirmation,
  inspection, retry/redrive, new runs, pause and rollback.
- [x] Run offline checks, package build, Lambda asset build, CDK synthesis and
  release-manifest verification. Rebuild assets after source/dependency changes.
  Use the exact successful-CI artifact and its visible infrastructure diff.
  If packaging/dependency changes affect extraction behavior, update Milestone 5's
  parity evidence and perform the required verification before seeking approval.

Preparation status: exact successful-CI artifact checks and protected disabled
release passed in Deploy 40402075873. Setup, recovery and real direct-smoke evidence
are in RELEASE_EVIDENCE. Activation preparation has its own uncommitted source
change and must use new exact main CI/protected approval.

### 6.2 First deployment, with consumption disabled

- [x] Obtain the release's required GitHub production approval, then deploy the
  reviewed artifact with consumption disabled. Record the release/commit, artifact
  identity, actual stack outputs, alias/version, resource ARNs and consumption state.
- [x] Securely populate the new secret and verify runtime access/provider readiness.
  The user confirms the alarm email subscription; verify the alert path.
- [x] Perform a controlled real-filing worker/integration smoke check within the
  remaining API test allowance and inspect the persisted result/output receipt.
  This direct check does not by itself verify the SQS trigger or complete Milestone 6.

### 6.3 Activate and prove queue-triggered delivery

- [x] Inspect and record input backlog size/age and estimated catch-up time/usage.
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
- [x] Document normal updates: preserve consumption state, with no unconditional
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

Milestones 1–5 are complete. Append one durable record at each session boundary;
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


### Milestone 2 — complete — 2026-10-25

- Scope delivered: isolated `finbot_earnings.processing.fiscal` extraction boundary,
  with the direct OpenAI SDK, byte-exact v6 prompt/local fiscal schema, tested union
  transport schema, traceable HTML text/original-image port, finite whole-snapshot
  admission, strict native/fiscal response handling and serializable run receipts.
  No consumer/storage/event/CLI integration or later milestone work.
- Repository/version: `finbot-earnings`, branch `main`, starting clean HEAD
  `2fb3554000f2af88c5680ec2bb114e6e34d8c6af` (committed Milestone 1). Changes remain
  **uncommitted**: `pyproject.toml`, `README.md`, `ROADMAP.md`,
  `docs/EXTRACTOR.md` (new), `docs/CONTRACTS.md`, `docs/FUNCTIONAL_SCOPE.md`,
  `docs/V0_DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/AWS_RUNTIME.md`,
  `docs/OFFLINE_PROCESSING.md`, `docs/contracts/README.md`,
  `tests/test_fiscal_extractor.py`, `tests/fixtures/fiscal_html_parity.json`, and
  `src/finbot_earnings/processing/fiscal/{__init__,adapter,config,errors,html_text,output,prepare}.py`
  plus its four resources: `configuration.json`, `implementation.json`, `eps-v6.txt`,
  `earnings_eps_fiscal_v2.schema.json`. Sibling evals/filings were read-only and clean;
  no pre-existing user changes were overwritten. Generated build products stay ignored.
- Exit evidence: 66 new offline tests exercise the actual SDK/HTTP serialization,
  exact endpoint/settings/schema, public filing context, table text and all selected
  attachments, 34 original images, JPEG/PNG/GIF, immutable source hashes, malformed
  JSON/native/schema output, fiscal integer/annual rules, empty/partial outputs,
  unsupported mixed snapshots, invalid/animated images, all bound categories,
  unknown usage, source failures and transient/permanent provider failures. The
  old 171 tests pass unchanged. Six preparation fixtures come from the reference
  helper; normal tests do not import sibling code or require operational data.
- API: `make_client(api_key, http_client=None)` and
  `OpenAIFiscalExtractor(client).extract(filing, source, run_id="initial", attempt=1)`.
  The extractor revalidates FilingReady and returns a JSON-compatible receipt with
  the full manifest/config/digest, source identities/hashes, canonical request digest,
  exact bounded response bytes plus native/parsed response, token usage/unknown flag,
  timing, outcome, reasons and retry policy. No files are written. `extracted` means
  schema-valid only; business acceptance/empty completion is explicitly Milestone 3.
- Frozen configuration: `eps-openai-luna-v6-v1`, canonical SHA-256
  `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097`.
  Versions remain `eps-v6`, `earnings_eps.fiscal.v2`, `openai-fiscal-v2-union-v1`,
  `filing-html-text-images-v1`, `fiscal-eps-acceptance-v1`; adapter
  `openai-luna-fiscal-v1`. Prompt hash
  `54158e06ec22a876acb0272bc1674bdd5dbf0f5a489eb7d9c8c3e65fdaf40237`;
  local schema hash `658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94`;
  canonical transport hash `137dec3a52ac17713243b92ccbe5fe16184617ef1bbe09915b132095408e08bb`;
  preparation inventory hash `5cfc53e8d4522b42d1ff69340c3861691839ae9e399fc53b32da7f56c4a6bd38`;
  implementation inventory hash `5bbf49eee3d17a97a64904a7af3177727c92da378fdab10168b33e9c1c12de75`.
  `load_config()` checks module/resource hashes and dependency versions to fail
  closed on drift. The inventory retains exact reference helper hashes at evals
  commit `d105712812a3daaf0d958c0b9b180f41ca4703ce`; no shared library dependency.
- Dependencies: OpenAI `2.54.0`, httpx `0.28.1`, html5lib `1.1`, webencodings `0.6.1`,
  six `1.17.0`, Pillow `12.3.0`, jsonschema `4.26.0`, declared/pinned in project
  dependencies and configuration. html5lib/webencodings were installed into this
  repo's `.venv`; no other repo's environment was changed. Prompt/schema/config
  resources are included in the built wheel. Linux Lambda dependencies/build
  remain unchanged until Milestone 6, so this is not a deployable consumer switch.
- Numeric bounds (inclusive): 16 HTML, 64 images; 16 MiB per HTML, 64 MiB total
  source, 2 MiB text, 8 MiB/image, 48 MiB total images, 16,000,000 pixels/image,
  8,192 longest-side pixels, 96 MiB encoded request, 900,000 local estimated input
  tokens, 2 MiB native response, 64 KiB extracted text; reserve 240 KiB for future
  events. Estimate = UTF-8 text/instructions/schema bytes + 8,192 per image +
  16,384 overhead; this is a heuristic, not provider token-count verification.
  OpenAI's official image/model docs were read for payload/count/context limits;
  live account quotas/access remain Milestone 6 checks. EXTRACTOR documents every
  bound, whole-snapshot review, artifact/bound diagnostics and operator next steps.
- Reference input measurement: a read-only inline Python check loaded each saved
  `inputs/*/request.json` under L5 run `20261023T145725Z-9ff8c84b`, checked original
  SHA-256s, then called the port's `prepare` and `check_request` with v6 settings.
  **50/50 passed admission**, without inference, target labels or score computation.
  Maxima: 5 HTML, 34 images, 5,312,094 source bytes, 5,300,624 single-HTML bytes,
  521,300 text bytes, 456,017 single-image bytes, 1,440,075 pixels and 1,365 longest
  side; complete request 5,189,881 bytes and token estimate 546,842. HON
  `hon-0000773840-26-000143`: all 34 images, 4,081,818 source bytes, 190,985 text
  bytes, 2,118,295 request bytes, estimate 496,362. This verifies input support,
  not unseen-filing accuracy or the complete Milestone 5 production parity gate.
- Deliberate port differences: production admission/format/encoding/streaming bounds,
  safe typed outcomes and explicit receipts; no WEBP under approved D07b, no other
  provider/evaluation framework. Preserve evals text semantics (including CSS-hidden
  text retained by the reference helper), image-alt placeholders, complete
  canonical artifact ordering and original image bytes. Undecodable HTML is review;
  invalid native bytes remain inspectable as base64. A response over 2 MiB stops
  reading and records an explicit terminal bound failure/unknown usage; it does not
  retain a partial response as complete. SDK retries are **0**, versus evals' 1;
  timeout stays 120 seconds. Max three application attempts must be durably claimed
  and counted by Milestone 3; ordinals 1–3 are accepted and attempt 3 cannot retry.
  No automatic invalid/empty/refused/incomplete-response retry or repair loop.
- Checks on 2026-10-25, repo `.venv` Python 3.11.17:
  `.venv/bin/python -m compileall -q src tests infra scripts` passed;
  `.venv/bin/python -m pytest` passed **237 tests**, including **66 new**;
  `.venv/bin/python -m build --no-isolation --outdir /tmp/finbot-earnings-m2-dist`
  built wheel/sdist; a `.venv/bin/python -I` wheel-only import (wheel inserted at
  `sys.path[0]`, module `__file__` asserted inside that wheel) verified all four
  packaged resources and the frozen configuration digest independently of source;
  `.venv/bin/python -m pip check` passed;
  `.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'`
  passed two schemas, 16 response cases, six identity vectors, one event, three
  input examples and **86 local links/fragments across 12 Markdown files**;
  `git diff --check` passed.
  No live provider calls are included in any check.
- Documentation: README/checkpoint/progress/checkboxes updated; EXTRACTOR adds API,
  exact limits, pins, differences, usage/retry and persistence handoff. Scope,
  decisions/contracts/architecture/offline/runtime docs distinguish the isolated
  implementation from unchanged Nova consumer and pending release work.
- Compatibility/next engineering: existing v0 pipeline/interfaces/stores/demo,
  commands, legacy records and infra remain untouched. No invented classification/
  evidence/date fields. The full receipt (2-MiB body plus native/config/manifest)
  exceeds one DynamoDB item: Milestone 3 must implement bounded durable splitting
  or another explicit design, then enforce the event bound and fenced atomic
  outcome/publication commits. Reconcile S3 exception normalization and persisted
  attempt budgets with the new source API; do not assume the old store can accept it.
- Live actions: none. No AWS/GitHub mutation, deployment, credential access, provider
  calls, catalog rebuild or shared-data changes. API test ledger: prior USD 5,
  spent USD 0, no unknown usage introduced, **USD 5 remaining** cumulatively.
- External action needed now: none. Dedicated secret/credential population,
  account quotas, alarm-email confirmation, Linux packaging and protected release/
  activation remain Milestone 6.
- Next session: **Milestone 3 only**. Read this record, EXTRACTOR API/configuration
  and CONTRACTS, then implement fiscal acceptance, filing-specific storage/events,
  consumer/CLI/demo integration and offline recovery/fencing tests. Preserve the
  frozen extraction behavior and prior records. Stop before Milestone 4 cleanup.


### Milestone 3 — complete — 2026-10-25

- Scope delivered: `FiscalConsumer` now runs complete FilingReady snapshots through
  the frozen real OpenAI boundary, durable receipt storage, `fiscal-eps-acceptance-v1`
  and immutable `earnings.extracted` 1.0 publication. Nonempty/empty/review/failure
  outcomes remain distinct; no legacy prose validation or cross-filing merging.
  The SQS source runtime, focused CLI and offline demo use the new boundary.
  No Milestone 4 deletions, parity study or release work was performed.
- Repository/version: `finbot-earnings`, branch `main`, clean starting commit
  `c6efa5d` (`Implement the tested extraction configuration`). Changes remain
  **uncommitted** in `README.md`, `ROADMAP.md`, `pyproject.toml`,
  `docs/{ARCHITECTURE,AWS_RUNTIME,CONTRACTS,EXTRACTOR,FUNCTIONAL_SCOPE,OFFLINE_PROCESSING,V0_DECISIONS}.md`,
  `docs/contracts/README.md`, `src/finbot_earnings/processing/{demo,lambda_handler}.py`,
  new `processing/{fiscal_contract,fiscal_consumer,fiscal_repository,fiscal_stores,fiscal_runtime,operator}.py`,
  `tests/{test_filing_processing,test_lambda_handler}.py`, and new
  `tests/{test_fiscal_consumer,test_fiscal_runtime}.py`. `processing/` shorthand
  above is under `src/finbot_earnings/`. Filings/evals checkouts were read-only and
  clean. No user work was overwritten; build outputs remain ignored.
- Contract/acceptance: preserve exact decimals, currencies, fiscal identity and
  complete source/config/request/native-response provenance. `FiscalIdentity`
  matches the documented SHA-256 encoding and prefixes. Unique metric/currency/
  period keys and one fiscal period across arrays are required; whole-response
  business conflicts go to review. Empty arrays complete `no_eps_extracted`, with
  no event or inference retry. Invalid model envelopes/schema fail terminally;
  no repair loop or independent fact verification is claimed. Format/size policy
  remains whole-snapshot HTML/original JPEG/PNG/GIF, including mixed HTML/PDF
  review before inference. Events over 245,760 UTF-8 bytes go to explicit review.
- Versioning: record schema 2 and config/prompt/schema/preparation/acceptance/event
  versions/digest remain exactly as recorded in Milestone 2. Frozen extractor source,
  resources and dependency pins are unchanged; `load_config()` verifies them.
  Global immutable config-version/digest registration rejects changed content under
  one version even across different filings. Legacy records are never reinterpreted,
  overwritten, merged, migrated or automatically republished.
- Persistence: `SQLiteFiscalRepository` and `DynamoDBFiscalRepository` share logical
  transitions. SQLite table `fiscal_v2_items`; DynamoDB `EPS2#WORK#<work_id>/STATE`,
  `EPS2#CONFIG#<version>/DIGEST`, `EPS2#BLOB#<sha256>/CHUNK#0000...`,
  `EPS2#EVENT#<event_id>/PAYLOAD`, `EPS2#STATUS#<status>/<work_id>`. Raw JSON blobs
  split at 131,072 bytes before base64; 25,165,824-byte logical cap/192 chunks.
  Exact canonical byte digest/length/membership verified on read. Immutable chunks
  stage before the fenced pointer commit; interrupted writes leave unlinked chunks,
  not partial saved receipts. No automatic GC/TTL. State/event/intent/status changes
  commit together under SQLite transactions or DynamoDB version/token/expiry CAS
  transactions. Payload/reference history is immutable; publication ack/time and
  attempts remain separate. Strong status queries page 1–100 rows by work ID,
  no scans/GSI/infrastructure change. Per-item/transaction conservative JSON bounds
  are 380 KiB / 3,800,000 bytes. No company-period HEAD or revision.
- Retry/fencing: 360-second lease; reserve each of at most three application attempts
  durably before preparation/secret/provider access, including crashes. Missing
  receipts retain unknown usage; no exactly-once promise. Attempts with saved
  receipts retain call/usage flags and complete responses. Automatic transient
  retries use remaining ordinals; SDK retries stay zero and timeout 120 seconds.
  Three stage failures exhaust persistence/publication recovery. Explicit rearm
  resets stage counters only, preserving all provider reservations/checkpoints.
  Fixed provider configuration can be explicitly redriven with a remaining attempt;
  invalid output is not automatically re-inferred. Saved response/event recovery
  skips source/provider access; publication repeats identical bytes after lost ack.
- CLI: new installed `earnings-ops` / `python -m finbot_earnings.processing.operator`:
  `inspect WORK_OR_PROCESSING_REF`, `event EVENT_ID`,
  `list STATUS [--limit 1..100] [--cursor WORK_ID]`, `retry WORK_ID`,
  `reprocess WORK_ID --run-id UNUSED_ID`, `output [--queue-url URL] [--limit 1..10]`.
  `--sqlite PATH` precedes the subcommand; default is DynamoDB. Inspection resolves
  `/input` refs and shows full config/sources/response/reasons/usage/timings. Retry
  requires failed work and matching saved configuration; it can charge/publish.
  Fresh extraction requires an unused non-initial run ID, preserves the complete
  manifest and can charge/publish a new event. Output uses mocked/tested ReceiveMessage
  with zero visibility and no delete, preserving queue send time separately;
  repeated inspection increments receive count and is not archival receipt tracking.
- Entry points/environment: normal `lambda_handler.runtime()` builds fiscal source
  wiring; cached AWS clients have 3/10-second connect/read bounds and two total SDK
  attempts. Provider credential is fetched only for extraction using dedicated
  `EARNINGS_OPENAI_SECRET_ARN` / AWSCURRENT plain SecretString; no secret read on
  inspect/duplicate/saved-publication recovery. `EARNINGS_FISCAL_CONFIG_SHA256`
  must match the packaged digest. Existing table/bucket/input/output topic and queue
  ARN env vars remain required; `EARNINGS_OUTPUT_QUEUE_URL` is operator-only.
  S3 missing/access/transient exceptions are safely normalized. No `.env` loading
  in the fiscal path. Failed command diagnostics do not print SDK error bodies.
- Exit evidence: both stores pass actual mocked-HTTP SDK tests for accepted/empty/
  review/invalid results, equal EPS in distinct filings/snapshots/fresh runs,
  independent interleaved filing commits, durable attempt/crash budgets, saved
  receipt/publication recovery, stale claims (including expiry during blob staging),
  immutable receipts, config/input conflicts, bounded status pages and operator
  retry/reprocessing. A 1.5-MiB native response round-trips exact bytes in over
  20 chunks. Partial chunk upload never links a receipt. DynamoDB transaction
  cancellation proves no event/status/outcome partial commit. SQLite reopen proves
  duplicate persistence. Handler/Secrets Manager/S3/SQS use offline mocks/Stubber.
  Full emitted event validates against the documented schema; schema/identity
  examples remain checked. The demo uses the actual extractor/SDK over mocked HTTP,
  three HTML files, one accepted event/duplicate, one empty run and mixed-PDF review.
- Checks on 2026-10-25 with repo `.venv`, Python 3.11.17:
  `.venv/bin/python -m compileall -q src tests infra scripts` passed;
  `.venv/bin/python -m pytest` passed **298 tests** (61 more than Milestone 2);
  `.venv/bin/python -m build --no-isolation --outdir /tmp/finbot-earnings-m3-dist`
  built wheel/sdist; wheel-only import/entry-point/config verification passed;
  `.venv/bin/python -m pip check` passed;
  `.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'`
  passed two schemas, 16 responses, six identities, one event and three input
  examples plus local link checks; `git diff --check` passed.
  `.venv/bin/python -m finbot_earnings.processing.demo --output-dir /tmp/finbot-earnings-m3-verified-demo`
  passed: two mocked calls with three documents each, one event, acknowledged
  duplicate, empty `no_eps_extracted`, mixed-PDF `review_required`.
  These are software checks, not paid extraction-quality evidence or live delivery.
- Documentation: README/checkpoint/progress/checkboxes updated; OFFLINE_PROCESSING
  documents layout/attempts/CLI, AWS_RUNTIME distinguishes source wiring from pending
  deployment, and scope/contract/acceptance/architecture/extractor notes are reconciled.
- Remaining legacy/release boundaries: `earnings` and `earnings-eval`, top-level
  NVDA/acquisition/extractors/storage/config, local evaluator/starter corpus/docs,
  v0 processing pipeline/domain/validation/reconciliation/repositories/Nova adapter
  and `legacy_runtime()`/`operation=evaluate` remain for Milestone 4. Inspect helper
  consumers before deletion: fiscal runtime still uses S3Documents/SNSPublisher,
  shared contracts/errors and the handler. Existing CDK config/permissions/Linux
  dependency manifest/build still describe Nova and **cannot deploy the fiscal
  source runtime**; update/test them in Milestone 6 after cleanup/parity. Keep
  stateful IDs and old records. Source consumption remains disabled, actual state
  unverified. No production fixture mode or evaluation framework was introduced.
- Live actions: none. AWS MCP read-only documentation checked transaction limits,
  Secrets Manager GetSecretValue and SQS ReceiveMessage. No AWS resource/account or
  GitHub access/mutations, credentials, paid calls, shared-data writes or catalog
  changes. API ledger: prior USD 5, spent USD 0, no unknown usage introduced,
  **USD 5 remaining** cumulatively.
- External action needed now: none. Dedicated secret/population, IAM/quotas,
  inspection queue, alarm confirmation, Linux assets, actual cloud/GitHub checks
  and protected release/activation remain Milestone 6.
- Next session: **Milestone 4 only**. Read this record, README/pyproject and legacy
  build/module/test/doc consumers, then retire superseded POC/evaluation paths and
  unused dependencies/assets, preserving useful fiscal coverage and all historical
  shared data. Stop before Milestone 5 parity or Milestone 6 release work.


### Milestone 4 — complete — 2026-10-25

- Scope delivered: retired superseded acquisition/extraction, canonical processing
  and earnings-local evaluation code. The fiscal FilingReady consumer is the sole
  application path. No parity study, provider calls or release implementation.
- Repository/version: `finbot-earnings`, branch `main`, initially clean at
  `1cd63d2ee014820ea214f3e7ded675cec6078347` (committed Milestone 3). All changes remain
  **uncommitted**; no unrelated work was overwritten and no commit was requested.
- Deletions (79 tracked files): top-level source
  `src/finbot_earnings/{__main__,cli,clock,config,eligibility,identity,models,parsing,pipeline,storage}.py`
  and `companies.toml`; entire source `sources/`, `extractors/` and `evaluation/`
  subtrees; `processing/{domain,pipeline,repository,sqlite_store,dynamodb_store,validation,reconciliation,images}.py`;
  `.env.example`; `evaluations/starter/` (synthetic corpus only);
  `docs/LOCAL_EVALUATION.md`, `docs/GOLDEN_DATASET.md`;
  `tests/helpers.py`, `tests/test_{cli_environment,dynamodb_processing,eligibility_extraction,identity_storage,local_evaluation,pipeline_fixture,sources,supporting_images,filing_processing}.py`
  and four NVDA/SEC fixtures (`nvda_release.html`, `nvidia_rss.xml`, `sec_index.json`,
  `sec_submissions.json`). Source shorthand is under `src/finbot_earnings/`.
  Historical shared-data corpora/source artifacts/labels/runs were not touched.
- Modified/new paths: `README.md`, `ROADMAP.md`, `pyproject.toml`,
  `docs/{ARCHITECTURE,AWS_RUNTIME,CONTRACTS,EXTRACTOR,FUNCTIONAL_SCOPE,OFFLINE_PROCESSING,V0_DECISIONS}.md`,
  `docs/contracts/README.md`, `infra/cdk/settings.py`, `scripts/build_lambda.py`,
  `src/finbot_earnings/__init__.py`, `processing/{aws_adapters,errors,lambda_handler}.py`,
  `tests/processing_helpers.py`,
  `tests/test_{aws_adapters,filing_contract,fiscal_consumer,fiscal_extractor,fiscal_runtime,lambda_handler}.py`,
  and new `tests/test_fiscal_demo.py`. Ignored editable metadata/scripts and the
  setuptools generated application copy were refreshed locally; no generated data
  or build artifact is committed. Existing generated Lambda/release assets are
  unverified and must be rebuilt during Milestone 6 before synthesis/deployment.
- Exit evidence: no watcher, SEC/IR downloader, approximate-date grouping,
  latency-flash command, local benchmark/corpus runner or evaluation endpoint
  remains in current source or package artifacts. The handler accepts nonempty
  SQS batches; former evaluation requests fail before runtime/source/credential work.
  Production explicit run identities/reprocessing remain unchanged. Only
  `earnings-ops` is installed, with inspect/event/list/retry/reprocess/output.
  Reinstalling editable metadata removed old console scripts in this repo's venv.
- Helper/dependency decisions: retained exact S3Documents/SNSPublisher behavior,
  FilingReady parser/identity helpers and production-safe errors. Removed the Nova
  adapter/schema/prompt and its `InputReview` error. Removed `python-dotenv` and
  companies package-data declarations; OpenAI/parser/Pillow/schema pins remain
  required by the fiscal extractor. Every existing Lambda-manifest dependency is
  still needed by fiscal AWS/image handling, so no pin was removed there. Final
  Linux provider dependency closure is explicitly Milestone 6, not cleanup.
- Infrastructure bridge: CDK imported the old runtime `ExtractionConfig`. Moved
  its configuration-only validation/serialization unchanged to infrastructure as
  `LegacyExtractionSettings`, preserving current settings/synthesized properties
  without retaining a runtime domain module. No CDK deployment setting, logical
  resource ID, permissions, consumption state or workflow changed. Old Nova IAM/
  environment and the bridge still need the planned Milestone 6 replacement.
- Coverage preservation: the fiscal suite retains the real mocked SDK, 34 images,
  all input bounds, mixed HTML/PDF whole-snapshot review, schema/business/empty
  outcomes, duplicate/new-run identities, both stores, fencing/concurrency, durable
  attempt budgets, saved-response/publication recovery and CLI tests. Retained
  S3 decoding/bounds/stream closure and exact SNS payload/ack tests without Nova
  fixtures. Moved the useful fiscal demo test out of the deleted legacy pipeline
  suite. Added both-store synthetic historical-record preservation through normal
  processing/duplicate delivery, without depending on retired repository classes.
  Removed tests exercise obsolete behavior and are superseded by fiscal coverage.
- Frozen behavior: all `processing/fiscal/` source/resources are byte-unchanged
  from starting HEAD; `git diff --exit-code -- src/finbot_earnings/processing/fiscal`
  passes. Config remains `eps-openai-luna-v6-v1`, SHA-256
  `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097`.
  No contract, storage namespace, retry budget or extraction behavior change.
- Checks on 2026-10-25, repo `.venv` Python 3.11.17:
  `.venv/bin/python -m compileall -q src tests infra scripts` passed;
  `.venv/bin/python -m pytest` passed **176 tests**;
  `.venv/bin/python -m pip install --no-deps --no-build-isolation -e .` passed;
  `.venv/bin/python -m pip check` passed;
  `.venv/bin/earnings-ops --help` passed and metadata lists only the new command;
  `.venv/bin/python -m build --no-isolation --outdir /tmp/finbot-earnings-m4-dist`
  built wheel/sdist after clearing only the old setuptools generated application copy.
  An inline `.venv/bin/python -I` artifact check verified exact **24 source/resource
  files**, byte-for-byte wheel equality to source, matching sdist source inventory,
  **19 wheel-only module imports**, config/pin validation, no dotenv requirement,
  sole console entry point and removal of both old installed scripts.
  `.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'`
  passed two schemas, 16 responses, six identities, one event, three input examples
  and local documentation link checks. `git diff --check` passed.
  `.venv/bin/python -m finbot_earnings.processing.demo --output-dir /tmp/finbot-earnings-m4-verified-demo`
  passed: two mocked calls, three HTML documents each, one accepted EPS event,
  acknowledged duplicate, empty result and mixed-PDF review before inference.
  CDK synthesis assertions pass in the offline suite; no Lambda Linux build,
  provider/container verification or live deployment was claimed.
- Documentation: status/checkpoint/progress/checkboxes updated; README and runtime
  guidance now center on the fiscal consumer and link to `finbot-filing-evals` for
  experiments/corpus review/results. Removed obsolete golden/evaluation recipes.
  D07b support/limits, mixed HTML/PDF and member/bound inspection plus explicit
  fresh-run instructions remain documented. Prior milestone completion records
  are historical evidence, including references to now-retired paths.
- Live actions: none. No AWS/GitHub/resource/credential access, paid inference,
  shared-data writes, catalog rebuild or sibling edits. AWS SDK Python skill was
  consulted for retained mocked adapters; no new service/API assumptions required.
- API test ledger: prior USD 5, known spend USD 0, no unknown usage introduced,
  **USD 5 remaining** cumulatively. Production funding remains user-managed.
- External actions needed now: none. Actual cloud/GitHub state, secret population,
  IAM/quotas, inspection queue, email confirmation, Linux packaging and protected
  deployment/activation remain Milestone 6.
- Next session: **Milestone 5 only**. Read this record, the current extractor/config/
  validation/tests and listed v6 experiment/run references, then produce durable
  production-port parity evidence against saved run `20261023T145725Z-9ff8c84b`.
  Do not automatically repeat the paid 50-filing campaign or start release work.


### Milestone 5 — complete — 2026-10-25

- Scope delivered: production-port parity evidence in
  [PRODUCTION_PARITY.md](docs/PRODUCTION_PARITY.md), with immutable baseline/data/
  implementation identities, every intentional difference and its compatibility,
  exact reference fingerprints and a read-only offline replay check. No runtime,
  prompt/schema, dependency, packaging, infrastructure or workflow change; no M6 work.
- Repository/version: `finbot-earnings`, branch `main`, initially clean at
  `e4aac9b0e15d5e10da706faed87b2dab74cd9ef1` (committed Milestone 4).
  Changes remain **uncommitted** in `README.md`, `ROADMAP.md`,
  `docs/{EXTRACTOR,AWS_RUNTIME,PRODUCTION_PARITY}.md`,
  `docs/parity/{REFERENCE_EXPORT.md,v6-reference.json}` and
  `scripts/verify_production_parity.py`. No unrelated changes, sibling edits,
  shared operational writes or generated build assets. Evals was read-only/clean
  at `d105712812a3daaf0d958c0b9b180f41ca4703ce`.
- Baseline: saved L5 run `20261023T145725Z-9ff8c84b` under
  `$FINBOT_DATA_ROOT/filing-evals/runs/`, source bundle `earnings-eps-50-v1`,
  reviewed revision `1ba92bb772114407fe4000c9d6dd29f253df81c814db82cbc1cc4d9d922cd2c7`,
  projected fiscal revision `48b0b27aaae67b263b409a98e193dc65c7eeab21f8f717b1de816f5a42db275a`.
  Preserved `earnings_eps.fiscal.v2` / `eps_fiscal_exact.v2` report: **83/83 targets,
  50/50 exact**, 52 reported/31 adjusted, no extraction errors, historical cost
  USD 0.159437190 complete and 164.13145787734538 summed extractor seconds.
  This remains development-set evidence, not held-out/unseen accuracy or new spend.
- Exit evidence: both environments verified the complete **353-file** saved run
  SHA-256/size inventory (including reviewed data, sources, requests/responses and
  reports). Reference source modules matched the saved implementation hashes.
  Prompt and source schema bytes match; compiled transport, preparation and pins
  retain frozen identity. The evals adapter/real SDK captured independent request
  fingerprints over mocked HTTP. The production adapter/real SDK replay matched
  **50/50** complete requests with only the documented timestamp exception;
  **189/189** source members were read in canonical order, including HON's 34
  original images. All **83** saved observations, exact native bodies, normalized
  usage and business acceptance survived unchanged. No scoring or fresh predictions.
- Compatibility decisions: 37 saved contexts use `...Z` without fractional digits;
  production's FilingReady requires `...000000Z`. These denote identical instants,
  do not define issuer fiscal period and are treated as a nonmaterial context
  representation difference. Both raw and canonical-timestamp request digests
  are retained; reversing that field alone must reproduce the exact reference
  request. Do not claim byte-identical requests or tested model invariance for
  those 37 cases. Saved schema pretty-print whitespace is likewise immaterial;
  the actual instruction/schema strings match the captured request. Synthetic
  storage/readiness fields supply valid offline envelopes and never enter the
  request. This does not prove producer/cloud readiness.
- Other differences assessed: stricter production admission/MIME/encoding/native
  parsing and finite bounds reject whole unsupported/oversized snapshots; all
  baseline members/responses fit. SDK retries are zero versus reference one;
  durable three-attempt/fencing recovery remains tested. Bounded HTTP-body reading,
  explicit receipt/outcome/event storage, single-period acceptance and removal of
  evaluation-only features preserve valid baseline behavior. Python 3.14.8 evals
  and 3.11.17 earnings match with all seven dependency pins. No material behavior
  change or unresolved mismatch required a new evals experiment or paid parity
  check. Linux Python 3.13/import/decoder and provider access checks remain M6.
- Configuration remains `eps-openai-luna-v6-v1`, SHA-256
  `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097`;
  prompt `54158e06ec22a876acb0272bc1674bdd5dbf0f5a489eb7d9c8c3e65fdaf40237`,
  local schema `658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94`,
  canonical transport `137dec3a52ac17713243b92ccbe5fe16184617ef1bbe09915b132095408e08bb`,
  preparation inventory `5cfc53e8d4522b42d1ff69340c3861691839ae9e399fc53b32da7f56c4a6bd38`.
  Saved inventory hash `7c7d5df3a791fe96a9919ddb2ade91a9fb5a2638d023c74d5038a490325867e5`;
  reference fingerprint file hash
  `1a3b0c28c18c1db411259fd1ed0357d30e4273870b4cbc3cd656cb30eac0b289`.
  Complete source/resource/reference hashes and reproduction are linked in the evidence.
- Checks on 2026-10-25 using repository-local environments:
  evals `.venv/bin/python /tmp/finbot-m5-export-reference.py ../../data/filing-evals/runs/20261023T145725Z-9ff8c84b /tmp/finbot-m5-reference.json`
  exported **50** independent fingerprints with a socket ban; the exact script is
  preserved in `docs/parity/REFERENCE_EXPORT.md` and runs only in evals' own environment.
  Earnings `.venv/bin/python scripts/verify_production_parity.py --run ../../data/filing-evals/runs/20261023T145725Z-9ff8c84b`
  passed **50 cases / 189 files / 83 observations** over real SDK/mocked HTTP with
  a socket ban and synthetic key. An inline `.venv/bin/python` import of the audit
  changed the first expected request digest and integrity digest separately to
  64 zeroes in memory; both failed closed with the expected `ValueError` before
  accepting a replay. No saved artifact was altered.
  `.venv/bin/python -m compileall -q src tests infra scripts` passed;
  `.venv/bin/python -m pytest` passed **176 tests** (final run 7.94 seconds), including
  acceptance/empty/unsupported/retry/duplicate/publication recovery on both stores;
  `.venv/bin/python -m pip check` passed;
  `.venv/bin/python -c 'from pathlib import Path; exec(Path("docs/contracts/README.md").read_text().split("```python\n", 1)[1].split("```", 1)[0])'`
  passed schemas, examples, identities and 91 local links/fragments across 11
  existing Markdown documents. An inline `.venv/bin/python` check passed all six
  new-document links/fragments, exact export-recipe/fingerprint identity and
  byte-exact reference prompt/schema plus current/saved candidate-config equality;
  `git diff --exit-code -- src pyproject.toml requirements-lambda.txt infra .github` and
  `git diff --check` passed. No package build is needed for unchanged runtime/assets.
- Timing/usage: first successful local replay summed 11,145 ms preparation,
  448 ms mocked response handling and 11,593 ms total. These are local audit times,
  not fresh provider or queue latency. Maxima: 34 images, 521,300 text bytes,
  5,189,881 encoded request bytes and 546,849 estimated tokens. The latter is seven
  above the M2 record due to canonical timestamp spelling, below the frozen bound.
  Production stage provenance remains unchanged; real queue/invocation/readiness/
  publication/receipt and backlog delay remain M6 measurements. No discovery
  timestamp is fabricated from SEC filing time or synthetic readiness.
- Documentation: README/checkpoint/progress/M5 checkboxes updated; EXTRACTOR and
  AWS_RUNTIME link durable parity evidence. No deployment readiness is claimed.
- Live actions: none. No inference, credentials, AWS/GitHub access or mutation,
  secret setup, release/activation, shared-data edits or catalog rebuild. Official
  OpenAI model/structured-output documentation was checked as context, not account
  readiness or quality evidence. No new AWS SDK code was written.
- API test ledger: previous USD 5, known new spend USD 0, no new unknown usage,
  **USD 5 remaining** cumulatively. Historical run cost is not charged again.
- External actions needed now: none for M5. M6 must verify actual cloud/GitHub
  prerequisites, Linux assets, secure credential population/provider access,
  inspection queue/alarms/email confirmation and exact protected release approval.
- Next session: **Milestone 6 only**. Read this record, PRODUCTION_PARITY and M6
  inputs, then prepare fiscal dependencies/build/CDK configuration and inspect
  actual prerequisites. Follow reviewed initial-disabled release, retained-backlog
  assessment and controlled activation; prove enabled queue-triggered EPS receipt
  in inspection SQS. Stop here; no M6 implementation or deployment was begun.


### Milestone 6 — in progress — 2026-10-25

- Scope delivered: deployable fiscal release preparation and read-only prerequisite
  inspection. No deployment, AWS/GitHub mutation, secret read/population, paid model
  call, commit/push, producer change or shared-data/catalog write. Milestone 6 is
  **not complete**: protected releases and actual enabled queue-triggered EPS receipt
  remain outstanding. Stop at this external-setup boundary and resume the same milestone.
- Repository/version: `finbot-earnings`, `main`, initially clean at
  `abc33ca2fd6b120f044fc0ce02b985353a439be5`, which commits M5. Preserve earlier
  records as historical session evidence. Current work is **uncommitted** in
  `README.md`, `ROADMAP.md`, `docs/{ARCHITECTURE,AWS_RUNTIME,CONTRACTS,EXTRACTOR,FUNCTIONAL_SCOPE,OFFLINE_PROCESSING,PRODUCTION_PARITY}.md`,
  new `docs/RELEASE_RUNBOOK.md`, `requirements-lambda.txt`,
  `infra/cdk/{config.prod.json,settings.py,stack.py}`, new `infra/cdk/access_app.py`,
  `scripts/{build_lambda,release_manifest,verify_release}.py`, new
  `scripts/check_lambda_asset.py`, `.github/workflows/{ci,deploy}.yml`,
  `src/finbot_earnings/processing/lambda_handler.py` and
  `tests/test_{earnings_infra,release_tools,lambda_handler}.py`.
  Siblings remain clean/read-only: filings `c3c4839cfd79a3e331790a547fee2d59b806c2b3`,
  evals `d105712812a3daaf0d958c0b9b180f41ca4703ce`.
- Engineering choices: remove LegacyExtractionSettings/Nova environment and
  Bedrock grant; require frozen fiscal digest in strict CDK settings. Keep existing
  stateful construct IDs, output topic `ValidatedEarnings` / `-validated` physical
  name, production alias and explicit consumption setting (initial false). Add
  retained empty dedicated secret with exact-ARN worker GetSecretValue; no generated
  credential or secret template value. Use service-managed secret encryption;
  source S3 currently uses AES256. Add output raw-event inspection queue/subscription
  with 14-day retention and its own delivery DLQ, scoped topic/account send policies,
  approved alarm-email subscription and nine operational alarms. Partial batch
  failures get log metrics because Lambda Errors alone misses acknowledged handler
  responses containing failed records. Add safe invocation/queue/handler duration
  fields; retain detailed stage/usage provenance in storage and CLI.
- IAM: worker and unattached recovery policy include Query and DeleteItem in
  addition to existing table writes/conditions. Transactional old-status deletion
  needs DeleteItem; no non-existent TransactWriteItems IAM action is used. The
  unattached inspection policy permits GetItem/Query and non-deleting output peeks,
  without secret access. No source writes/Scan. AWS IAM Policy Autopilot 0.3.0
  analyzed `aws_adapters.py`, `fiscal_runtime.py`, `fiscal_stores.py`, `operator.py`
  with `--region us-east-1 --account 559007813222 --service-hints s3 sns sqs dynamodb secretsmanager --pretty`;
  its broad baseline was reviewed for the deployed topology; no policies uploaded.
  AWS MCP documentation verified SQS visibility guidance and DynamoDB transactional
  action behavior. Installed CDK/IAM/serverless guidance was consulted.
- Release access: separate `infra/cdk/access_app.py` assembly prepares earnings-only
  plan/deploy roles importing the existing OIDC provider. Verified immutable GitHub
  subject prefix is `repo:ilancooke@8453151/finbot-earnings@1350331204`, not the old
  mutable name-only subject. Plan trust ends `:ref:refs/heads/main`; deploy ends
  `:environment:production`. Deploy assumes existing bootstrap deploy/file roles;
  bootstrap CFN execution already has AdministratorAccess (recorded explicitly,
  not changed). Production preflight requires reviewers and exactly branch main.
  Protected apply still reuses the successful-CI assembly without rebuilding.
- Packaging/parity: fully pinned Python 3.13 Linux x86_64 binary dependency closure,
  including OpenAI/httpx/parser/schema/native libraries. All seven frozen fiscal
  pins, extractor source/resources and digest remain unchanged:
  `e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097`.
  Container `public.ecr.aws/lambda/python:3.13` resolved to
  `sha256:d8f9d8827e88acff4d606fc0a2c74cdf1e15286051f141e454e94756c9db9efe`.
  Offline asset-only imports/config, HTML parsing and JPEG/PNG/GIF decoding pass.
  The exact asset also replays **50 cases / 189 members / 83 observations / 353
  integrity files** with M5's 37 timestamp spelling exceptions unchanged. No
  inference/quality change requires paid reevaluation. Linux emulated mock timing:
  18,690 ms preparation, 718 ms response handling, 19,417 ms total, not live latency.
- Preview identities: asset SHA-256
  `ab614d29350eeae5ea2617f9bca3c680cde704908246353ba9fc0f8ab912a5dc`,
  61,804,440 uncompressed bytes including marker. Local application assembly
  SHA-256 `a0920a5f059ba6ca92f945d45f60f0616e2c2ca3e2c73bd01410c5451c5b01e2`.
  `build/release-manifest.json` explicitly has `source_dirty=true`, parent commit
  M5. These are **local review previews**, not a successful-CI release identity;
  source/assembly must be rebuilt by CI after an authorized commit/push.
  Generated `build/`, `cdk.out/`, packages and logs stay ignored or temporary.
- Checks on 2026-10-25, repo .venv Python 3.11.17 / target Python 3.13 Linux:
  `.venv/bin/python -m pytest` passes **180 tests** (final 8.17 seconds); compilation via
  `.venv/bin/python -m compileall -q src tests infra scripts` passes;
  `.venv/bin/python -m build --no-isolation --outdir /tmp/finbot-earnings-m6-dist`
  builds wheel/sdist; `.venv/bin/python -m pip check` passes.
  `.venv/bin/python scripts/build_lambda.py --verify-target` rebuilds and passes
  target imports/decoder checks. `JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii CDK_DISABLE_CLI_TELEMETRY=1 npm run synth`
  passes strict offline synthesis; the same environment with
  `node_modules/.bin/cdk synth --app '.venv/bin/python -m infra.cdk.access_app' --output build/release-access --strict --no-lookups`
  passes separate access synthesis. `.venv/bin/python -m scripts.release_manifest`
  writes the preview. Temporary directory linking that assembly/manifest passes
  all payload/asset/template/config/consumption checks, then correctly rejects dirty
  source for deployment. Clean fixture succeeds and tampered/wrong-commit/changed
  consumption/asset fixtures fail in release tests. Host parity command from M5
  passes; the exact offline Docker replay command is preserved in PRODUCTION_PARITY.
  The docs/contracts README's Python block verifies schemas/examples/identities
  and **100 local links/fragments across 12 Markdown files**; `git diff --check`
  passes. Final wheel bytes match all **24 current application source/resource
  files**. Frozen extractor directory has no diff.
- Corrected check failures: first local synthesis attempted the read-only default
  jsii cache; using `/tmp/finbot-earnings-jsii` passes. Initial container-check
  socket replacement prevented ssl import; banning connect instead passes. First
  Linux audit mount lacked its assumed parent depth; mounting at `/scripts/audit.py`
  passes. No AWS/provider failure experiment was run.
- Read-only live evidence: AWS principal `arn:aws:iam::559007813222:user/codex-readonly`
  verified the target account. Earnings DescribeStacks returns stack-not-found;
  no earnings table/queue/secret/release roles exist. Producer SNS exists with zero
  subscriptions; source S3 region/encryption verified. Real HON filing
  `0000773840-26-000143`, snapshot
  `5e2356665a6b6d326eb81852e4d53fca331430c67ddfdfeb53be502d9cf9193e`
  has a saved genuine FilingReady 1.0 and all **35** selected objects; HeadObject
  lengths/content types agree. No source byte download/inference was needed for
  that metadata check. The runbook records producer task-definition/image, known
  limitations and exact upstream notification key. No producer runtime pin change.
- GitHub inspection: production environment GET returns 404, repository variables
  empty; immutable OIDC customization verified. Existing main push CI
  [40267303486](https://github.com/ilancooke/finbot-earnings/actions/runs/40267303486)
  succeeds for M5 only. No GitHub dispatch, environment/variable change or release
  approval was requested against an unfinished/non-CI artifact.
- Documentation: README status/table/commands/map, ROADMAP checkpoint/progress/task
  boxes and runtime/parity/scope references updated. RELEASE_RUNBOOK covers secure
  console key population, alert confirmation/test, operator access, genuine full
  snapshot replay, smoke versus trigger proof, budget/usage reconciliation, backlog
  estimates, duplicate checks, checkpoint retry/redrive/new runs and pause/rollback.
  No production credential, configured ARN or enabled state is fabricated.
- API test ledger: prior USD 5, known new spend USD 0, no unknown usage introduced,
  **USD 5 remaining cumulatively**. AWS read-only inspection is separate from the
  API inference allowance. Ongoing production/backlog funding remains user-managed.
- External action/resume: AWS owner reviews and explicitly approves/applies the
  separate release-access assembly; repository owner creates required protected
  production reviewer/main restriction and role variables. Review/commit/push the
  implementation when authorized; use exact successful CI and reviewed diff for
  protected first disabled deployment. Then securely populate AWSCURRENT, verify
  provider/model limits/funding and runtime object/key access, confirm/test alarm
  email, run a budgeted genuine-filing smoke, measure retained backlog, prepare an
  enabled successful-CI release and obtain its protected approval. Prove actual
  SQS-triggered extraction on a fresh real snapshot and inspection receipt, then
  duplicate reuse and record all deployed IDs/timings/usage. Keep M6 **In progress**
  until those criteria pass. No subsequent milestone is started.


### Milestone 6 — in progress — 2026-10-26

- Scope delivered: user-approved simplification to use shared Lambda account
  capacity, with no function reservation and the existing SQS maximum concurrency
  two. Initial consumption remains false. The regression assertion now requires
  ReservedConcurrentExecutions to be absent, preventing accidental reservation zero.
  No runtime, extractor, dependency, payload/identity or provider-attempt change.
- Repository/version: initially clean `main` at
  `43b7aab673bed212b9283bcf6eae35b59ed384bd`. Uncommitted edits only in `README.md`,
  `ROADMAP.md`, `docs/AWS_RUNTIME.md`, `docs/RELEASE_RUNBOOK.md`,
  `infra/cdk/stack.py` and `tests/test_earnings_infra.py`. No sibling/shared-data
  edits, source package build, model call, quota request, cloud mutation, commit or
  push by the agent in this fix. Existing verified Lambda assets were used because
  application source/dependency bytes did not change; CI rebuilds the next release.
- Live progress reported by the user: release-access stack creation succeeded at
  `arn:aws:cloudformation:us-east-1:559007813222:stack/finbot-earnings-release-access/243ad4e0-d145-11f1-83ab-0affd46b34d1`;
  plan/deploy role ARNs and repository variables are configured. GitHub production
  requires `ilancooke` review (self-review allowed), custom main branch rule
  `64412050`. Source preparation was merged as `43b7aab...`; successful main CI
  [40330825407](https://github.com/ilancooke/finbot-earnings/actions/runs/40330825407)
  produced its exact artifact. User dispatched and approved
  [Deploy 40393601425](https://github.com/ilancooke/finbot-earnings/actions/runs/40393601425).
  Preparation passed; clean artifact/digest and disabled consumption matched the
  reviewed diff. Full release identities are preserved in RELEASE_RUNBOOK.
- Deployment failure: Worker creation returned HTTP 400 because its reservation of
  two decreased unreserved account concurrency below the required minimum of 10.
  The user supplied Lambda AccountLimit total/unreserved **10 / 10**, and stack
  state **ROLLBACK_COMPLETE**, termination protection **true**. Worker creation
  failed before any live extraction. Logs show retained table, five queues, secret
  and log group; topics/policies/subscriptions rolled back, with pending alarm email
  detached. This is a partial failed deployment, not successful release/activation.
- Engineering decision: on 2026-10-26 the user explicitly selected no reservation
  instead of seeking a quota increase. This is within D11d's operational settings.
  SQS caps queue-triggered executions at two; other Lambda workloads can contend
  for account capacity. Other invocation paths do not inherit the SQS source cap.
  No spend-cap or extraction-policy change. AWS MCP documentation confirms source
  maximum concurrency is independent of function reserved concurrency.
- Checks using repository .venv on 2026-10-26:
  `.venv/bin/python -m pytest` passes **180 tests** (9.25 seconds);
  `.venv/bin/python -m compileall -q src tests infra scripts` passes;
  `JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii CDK_DISABLE_CLI_TELEMETRY=1 node_modules/.bin/cdk synth --strict --no-lookups --output build/no-reservation-review`
  passes with no AWS calls. An inline JSON comparison against the previous local
  `cdk.out/finbot-earnings-prod.template.json` proves **exactly one changed resource**:
  Worker11F36D0F loses ReservedConcurrentExecutions=2, with every other property and
  resource identical. The source mapping still has MaximumConcurrency=2 and
  Enabled=false. `.venv/bin/python -m pip check`, the docs/contracts README's
  schema/example/identity/local-link checker and `git diff --check` pass.
  `git diff --exit-code -- src requirements-lambda.txt pyproject.toml` passes;
  frozen config/digest and prior Linux parity evidence remain applicable.
- Documentation: current README/checkpoint/progress and runtime/runbook updated,
  historical M6 record preserved. Initial 2026-10-25 observations are explicitly
  historical; current user-reported setup, failed release identity, quota/error,
  retained resources and pending recovery are durable. M6 remains **In progress**.
- API test ledger: previous USD 5, known new spend USD 0, no new unknown usage,
  **USD 5 remaining cumulatively**. No provider request was dispatched.
- Next action: user reviews/merges this source fix through a branch/PR and waits for
  new successful main CI. Continue step-by-step read-only inventory of retained
  logical/physical IDs, then prepare a concrete preservation/import recovery plan
  before any stack removal/import or protected redeployment. Do not retry the old
  artifact or delete retained operational state. After recovery, continue secret/
  provider/email checks, budgeted smoke/backlog assessment and protected enabled
  SQS-triggered EPS receipt proof. No later milestone or live recovery is complete.


### Milestone 6 — in progress — activation prepared — 2026-10-26

- Scope: recovered the failed first deployment through reviewed import of all
  eight retained resources; protected disabled release, secure key population,
  confirmed/tested email, real deployed HON smoke and actual inspection SQS receipt
  are verified. This session prepares consumption=true for protected activation;
  **M6 is not complete** until fresh enabled queue-triggered EPS and duplicate reuse
  are proven. No later milestone started.
- Source: initially clean main `829d1a98a36e36e68cac6b8f3939b0f29fc584f7`. Current
  uncommitted edits in `infra/cdk/config.prod.json`, `tests/test_earnings_infra.py`,
  `README.md`, `ROADMAP.md`, `docs/{AWS_RUNTIME,ARCHITECTURE,FUNCTIONAL_SCOPE,OFFLINE_PROCESSING,EXTRACTOR,RELEASE_RUNBOOK}.md`
  and new `docs/RELEASE_EVIDENCE.md`. User uses direct main commit/push. No provider
  credential, generated dataset, operational JSON or ignored build helper is staged.
- Actual live state: user-executed import change set contained eight Import actions,
  then IMPORT_COMPLETE with termination protection true. New recovered stack ARN,
  original survivor IDs and import change-set ARN are in RELEASE_EVIDENCE. Main CI
  40397320222 produced the exact artifact for user-approved Deploy 40402075873,
  which succeeded with source clean and consumption disabled. Asset SHA-256
  `e8e970ffa074829acd9b61e13610d01c9341d22728a049bbf14252ec66da7201`, assembly
  `18ca13a6a2e3d6c03e2f7414efe751b1a770016ec3ba564f80456a6772b16a9d`.
  Production alias version 1; actual queue mapping Disabled, batch 1, max 2,
  no function reservation. All AWS mutations were performed explicitly by the
  user from reviewed commands; AWS MCP was documentation/read-only inspection.
- Secure setup/alerts: secret name/ARN/AWSCURRENT version only recorded in evidence;
  hidden prompt sent the plain key directly to its dedicated secret. Runtime
  inference proves retrieval/access. Alarm email subscription confirmed and user
  received controlled topic test `283917a8-4c83-5958-b264-74f1853004a4`. This is
  SNS/email path evidence; no synthetic CloudWatch alarm transition was induced.
- Real smoke: unchanged genuine producer FilingReady for HON
  `0000773840-26-000143`, snapshot
  `5e2356665a6b6d326eb81852e4d53fca331430c67ddfdfeb53be502d9cf9193e`;
  all 35 original selected members/34 JPEGs read. Operator direct RequestResponse
  invocation returned 200/no FunctionError/version 1/empty batch failures. Accepted
  reported diluted EPS USD 2.08, FY2026 Q3, adjusted empty. One attempt/publication.
  Exact work/event IDs, durable outcome/native receipt/usage, SNS acknowledgment,
  output SQS ID/SentTimestamp and inspection time are in RELEASE_EVIDENCE. Repeated
  zero-visibility reads have the same SQS message ID; do not count them as new
  inference/publications. This is not yet actual SQS event-source execution proof.
- Timings: preparation 5,219 ms, extraction 6,524 ms, successful extractor total
  11,743 ms, first claim to publication acknowledgment 12.277659 seconds,
  last publication 109 ms. Readiness is a genuine four-day-old stored snapshot;
  its 371,235,021-ms ready-to-ack interval is explicit replay age, not normal queue
  delay. Missing discovery/initial receive times are not invented.
- Budget: prior USD 5; complete receipt 59,518 input tokens (59,515 30m cache write,
  3 ordinary) plus 105 output (47 reasoning included). GPT-6 Luna published pricing
  checked 2026-10-26 yields estimated **USD 0.007492175**, remaining estimated
  **USD 4.992507825**, no unknown attempts. User billing UI showed USD 0.01 decrease.
  The proposed USD 0.50 test buffer is released after reconciliation. No repeated
  paid campaign/failure experiments. Normal production funding remains user-managed.
- Readiness: input visible/in-flight/delayed counts 0/0/0; no observed backlog or
  catch-up work/cost, age inapplicable to empty queue. Recheck before activation.
  User reports model limits 2M TPM / 5,000 RPM / 50,000 IPM / 20M TPD as displayed.
  Measured HON-sized processing at two workers implies about 0.58M input TPM,
  below reported TPM, without guaranteeing every supported input or shared load.
- Verification: `.venv/bin/python -m pytest` passes **180 tests** (8.84 seconds);
  `.venv/bin/python -m compileall -q src tests infra scripts` passes;
  `JSII_RUNTIME_PACKAGE_CACHE=/tmp/finbot-earnings-jsii CDK_DISABLE_CLI_TELEMETRY=1 node_modules/.bin/cdk synth --strict --no-lookups --output build/activation-review`
  passes offline. Inline comparison with `build/no-reservation-review` finds only
  mapping Enabled false-to-true and ConsumptionEnabled output false-to-true.
  All logical IDs/other resources/settings are identical and no reservation appears.
  Explicit-pause test verifies disabled mapping while preserving stateful identities.
  `git diff --exit-code -- src requirements-lambda.txt pyproject.toml`, dependency
  consistency, docs/contracts schema/examples/identity/local-link checks and
  `git diff --check` pass. Runtime/assets are unchanged; new main CI rebuilds the
  release as usual. No new parity rerun or provider behavior change is needed.
- Documentation/handoff: current checkpoint/table/M6 boxes, README/runtime/runbook
  and scope references distinguish prepared source true from actual live Disabled.
  RELEASE_EVIDENCE is the durable curated deployment/smoke/usage record; ignored
  build/recovery helpers/data remain local operator aids.
- Next: user reviews/commits/pushes these activation changes directly to main,
  waits for new successful CI, reviews exact artifact/diff and backlog, then uses
  required GitHub production approval. Confirm actual Enabled state. Prefer a new
  real producer notification, or explicitly submit a different genuine complete
  stored snapshot with no existing work, for fresh EPS extraction/output receipt.
  Sending the already completed HON snapshot only proves duplicate reuse. Verify
  both, reconcile further test usage and final deployed state, update docs and only
  then mark M6 complete. No live activation has been performed by this source edit.


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
(fiscal extractor/consumer/contracts/stores, shared adapters and Lambda handler),
`infra/cdk/` (stack/settings/configuration), `scripts/` (Lambda build/release
verification) and `.github/workflows/`. Milestone 4 removed legacy acquisition,
extraction and evaluation code after replacement coverage passed.
Milestone 1 reconciled the scope/acceptance/contract/architecture documents and
labeled current offline/AWS behavior separately from target semantics. The approved
roadmap still takes precedence; Milestone 3 now implements the fiscal consumer in a new namespace; legacy
NVDA/Nova/canonical code was removed in Milestone 4. Deployment is pending.

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

The fiscal implementation enforces the following launch behavior. Legacy runtime
code is removed; production packaging/infrastructure remains Milestone 6 work.

- Supported source formats are HTML plus original JPEG/PNG/GIF supporting images.
  TXT, PDF and other unsupported selected formats go to review for launch.
- The input unit remains the complete selected FilingReady snapshot. One
  unsupported member causes the whole snapshot to go to review before inference,
  even if another HTML document might contain readable EPS. No EPS event is emitted.
- Oversized snapshots likewise go to review before inference. Documents are not
  truncated and selected attachments are not discarded to fit provider limits.
- The frozen finite document/image/request limits are documented in EXTRACTOR
  and README and accommodate the evaluated HON 34-image case. The obsolete
  128-KiB/five-document/20-image Nova bounds do not apply to the fiscal consumer.

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
use Nova 2 Lite; the obsolete earnings CDK configuration still names Nova Lite v1. Preserve the
saved experiments as historical evidence rather than treating them as validation
of the current earnings adapter. Budget fresh documents separately from cached
repeats.

## Existing foundations to retain or adapt

- [x] Complete filing-snapshot parsing and manifest identity checks.
- [x] Filing-level processing with injected document, model, storage and publication adapters.
- [x] Durable model responses, bounded retries, lease fencing and work deduplication.
- [x] SQLite reference storage and DynamoDB persistence with atomic event/outcome commits.
- [x] Replace canonical revisions/conflict review with D04's filing-specific
  results, retaining immutable history and recoverable saved-payload publication.
- [x] S3/SNS adapters, an SQS Lambda handler, CDK definitions and CI/release workflows.
- [x] Offline tests for processing, adapters, concurrency and publication recovery.

Milestone 4 removed the legacy NVDA watcher and earnings-local evaluation runner
from this core. Repository documentation records the earnings service as undeployed;
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

