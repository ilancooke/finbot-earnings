# Isolated fiscal EPS extractor — Milestone 2

Implemented 2026-10-25 in `finbot_earnings.processing.fiscal`. Milestone 3
now integrates this frozen boundary through `FiscalConsumer`, version-2 stores,
the demo and `earnings-ops`. Retained legacy modules use their old contract. It does
not publish events, claim work, load `.env`, fetch web resources or write files.

## API and receipt

`load_config()` returns a fresh copy of the frozen `eps-openai-luna-v6-v1`
configuration. It checks packaged implementation hashes, prompt/schema hashes,
compiled transport schema and installed dependency versions before use. Resources
live in `src/finbot_earnings/processing/fiscal/resources/` and ship in the wheel.
Changing behavior requires a new configuration version and digest; do not rewrite
the initial version after it has identified persisted work.

`make_client(api_key, http_client=None)` requires explicit credential injection.
`OpenAIFiscalExtractor(client).extract(filing, source, run_id="initial", attempt=1)`
takes a validated `FilingReady` and a bounded `DocumentSource.read(ref, max_bytes=...)`
implementation. It validates the complete manifest, loads every selected member,
and sends one Responses request. Source reads must enforce their bound themselves;
the extractor independently checks each returned size against the manifest.

The JSON-compatible receipt contains:

- The full input manifest, run ID and attempt ordinal; complete extraction config
  and canonical SHA-256; operational retry policy separately.
- Ordered document identities, byte counts and SHA-256 digests; canonical prepared
  request digest, encoded size, text bytes, image count and token admission estimate.
- Exact native HTTP response bytes as `response_body_base64`, decoded `response`,
  schema-valid `extraction`, normalized usage plus original provider usage, and
  `usage_unknown`. Missing/invalid usage and failed requests never imply free usage.
- UTC extraction start/completion and integer preparation/extraction/total
  milliseconds; `provider_called`, outcome, safe reasons and retryability.

`extracted` means **schema-valid output only**, including empty arrays. The adapter
does not call that result accepted or non-earnings. `FiscalConsumer` persists the
receipt, applies single-period/unique-observation business rules, produces
`accepted`/`no_eps_extracted` and commits events/publication intent. Never adapt this
object by fabricating v0 classification, evidence or calendar dates.

Input review returns `review_required` with no provider call. Refusal/incomplete
output also returns review without inference retry. Invalid envelopes, JSON,
duplicate JSON keys, nonfinite numbers, types or fiscal schema return terminal
`processing_failed / invalid_model_response`, retaining the original response.
Oversized native responses are stopped while streaming: no prefix is retained as
a complete response; the bound/observed byte count and unknown usage are explicit.
Responses within the bound, including invalid/non-UTF-8 bodies, retain exact bytes.

Diagnostics never copy SDK error messages/bodies, headers or credentials. Technical
source failures use safe artifact-specific codes. Provider timeouts, connectivity,
408/409/429 and 5xx are transient; access/request/billing/quota-configuration
failures are terminal. `insufficient_quota` is terminal even with HTTP 429.

## Frozen bounds and unsupported inputs

These are application admission limits, intentionally below the provider maxima.
Any selected PDF/TXT/WEBP/other unsupported member, conflicting filename/MIME, bad
raster, animated image or exceeded bound rejects the **whole snapshot**. Unsupported
formats are collected before source reads. No truncation, image transformation,
attachment omission, subset extraction or multi-call split. JPEG/PNG/GIF bytes
remain original. HTML5 parsing respects BOM/declared encodings; undecodable bytes
go to `unsupported_document_encoding` review instead of silent replacement.

| Configuration bound | Inclusive limit |
| --- | --- |
| Standalone HTML documents | 16 (`.htm`, `.html`, `.xhtml`) |
| Original JPEG/PNG/non-animated GIF images | 64 |
| Single HTML source | 16 MiB (16,777,216 bytes) |
| Total selected source bytes | 64 MiB (67,108,864 bytes) |
| Total prepared HTML text | 2 MiB (2,097,152 UTF-8 bytes) |
| Single image / total image bytes | 8 MiB / 48 MiB (8,388,608 / 50,331,648 bytes) |
| Single image pixels / longest dimension | 16,000,000 / 8,192 pixels |
| Complete encoded Responses JSON body | 96 MiB (100,663,296 bytes) |
| Input token admission estimate | 900,000 |
| Native response body | 2 MiB (2,097,152 bytes), streaming read bound |
| Extracted JSON text | 64 KiB (65,536 UTF-8 bytes) |
| Future output event reservation | 240 KiB (245,760 bytes); enforced by FiscalConsumer |

The token estimate is one token per UTF-8 byte of prepared text, instructions and
transport schema, plus 8,192 per image and 16,384 overhead. It is a conservative
local admission heuristic, **not a tokenizer or guaranteed provider token count**.
The provider also enforces its own context limits; a rejection is preserved as a
terminal configuration/input failure, without another inference call or truncation.

Official [image input requirements](https://developers.openai.com/api/docs/guides/images-vision)
checked 2026-10-25 document 1,500 images and 512 MB payloads; the
[Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna)
documents a 1,050,000-token context. Account-specific quotas/access and live
provider acceptance remain release checks, not claims established by mock tests.

Every input-bound reason includes `snapshot_bound_exceeded`, named `bound`,
`actual`, `limit` and artifact ID/filename or contributing artifact IDs. Inspect the
whole snapshot and fix the issue before deliberately requesting a new run; do not
drop a selected PDF or oversized image. Operator CLI syntax is in OFFLINE_PROCESSING.

## Reference behavior and deliberate port differences

Source: evals commit `d105712812a3daaf0d958c0b9b180f41ca4703ce`, saved v6 run
`20261023T145725Z-9ff8c84b`. `implementation.json` records byte hashes of reference
`direct.py`, `bedrock.py`, `contracts.py`, `review/viewer.py` and every port module.
Prompt and local schema are byte-exact copies, with hashes recorded in CONTRACTS.
Transport compilation preserves the tested quarterly/annual union. HTML text keeps
the reference table separators, inline text, removed subtrees and image-alt
placeholders. Images follow the complete manifest's canonical artifact-ID order;
no natural filename sort or primary-document-first reorder is introduced.

The request retains model `gpt-6-luna`, v6 instructions plus local schema,
strict `earnings_eps` transport format, medium reasoning, 4,096 output tokens,
high-detail original images, `store=false`, `truncation=disabled`, default service
tier and implicit 30-minute prompt cache. Six synthetic preparation fixtures were
generated with the referenced evals helper and frozen in
`tests/fixtures/fiscal_html_parity.json`; normal tests never import a sibling repo.

Deliberate production safeguards: finite per-member/aggregate/request/text/token
bounds, strict byte decoding, MIME/extension consistency, bounded response streaming,
structured safe outcomes and receipts. Launch excludes WEBP under D07b even though
the reference helper supports it. No Anthropic/Bedrock branch, evaluator, pricing
engine, label UI or sibling dependency was ported.

SDK retries change from evals' one retry to **zero**. Each adapter invocation is
exactly one provider attempt. The application is responsible for durably claiming
and counting at most three attempts for transient failures; attempt 3 returns
`retryable=false`, and ordinals outside 1–3 are rejected. The adapter has no retry
loop and cannot enforce a durable budget without the version-2 store. A timeout can
have unknown charges; a crash before receipt persistence can require another call.
The client timeout remains 120 seconds. Worker/queue/lease timing must be reconciled
with this in Milestones 3/6.

Pins in `pyproject.toml` and the config: OpenAI 2.54.0, httpx 0.28.1, html5lib 1.1,
webencodings 0.6.1, six 1.17.0, Pillow 12.3.0 and jsonschema 4.26.0.
The Nova Lambda dependency manifest/build remains unchanged; production Linux
packaging is Milestone 6. The 2-MiB response plus byte-exact body/manifest/config
**will not fit one DynamoDB item**. Milestone 3 implements bounded immutable chunk splitting and atomic pointer/
outcome/event commits in the new stores; see OFFLINE_PROCESSING. It enforces the
240-KiB event reservation before publication. Do not use the old small-item store.

## Offline verification

From the earnings repository:

```bash
.venv/bin/python -m pytest tests/test_fiscal_extractor.py
.venv/bin/python -m compileall -q src tests infra scripts
.venv/bin/python -m pytest
.venv/bin/python -m build --no-isolation --outdir /tmp/finbot-earnings-m2-dist
.venv/bin/python -m pip check
git diff --check
```

The real SDK runs over `httpx.MockTransport`, with network forbidden by the suite.
Coverage includes exact settings, 34 original images, table/multi-attachment text,
all supported image encodings, unsupported mixtures, every bound category,
malformed/native/schema output, refused/incomplete output, usage and transient/
permanent failure handling. This is software verification, not a paid quality run.

Read-only inspection of the saved 50 input packages found maxima of five HTML
documents, 34 images, 5,312,094 source bytes, 5,300,624 bytes in one HTML file,
521,300 prepared text bytes, 456,017 bytes in one image, 1,440,075 image pixels and
1,365 pixels on the longest side. All 50 were prepared by this port and passed
the frozen input bounds; original file hashes were checked. See ROADMAP's
Milestone 2 completion record for request/token maxima and HON details. No labels,
predictions, scores or shared files were changed; Milestone 5's broader production
parity/recovery gate remains outstanding.
