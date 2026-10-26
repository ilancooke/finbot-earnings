"""Complete-snapshot preflight and evals-compatible text/original-image sequence."""

from base64 import b64encode
from hashlib import sha256
from io import BytesIO
import json
import warnings

from PIL import Image

from ..errors import TechnicalFailure
from .errors import ExtractionProblem, problem
from .html_text import plain_text_preview

IMAGE_EXTENSIONS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif"}
HTML_MIMES = {"text/html", "application/xhtml+xml"}


def member_format(ref):
    suffix = ref.filename.rsplit(".", 1)[-1].lower()
    mime = (ref.content_type or "").split(";", 1)[0].strip().lower()
    unspecified = mime in {"", "application/octet-stream"}
    if suffix in {"htm", "html", "xhtml"} and (unspecified or mime in HTML_MIMES):
        return "html"
    kind = IMAGE_EXTENSIONS.get(suffix)
    if kind and (unspecified or mime == "image/" + kind):
        return kind
    return None


def bound_reason(name, actual, limits, *, ref=None, members=()):
    if actual <= limits[name]:
        return None
    details = (dict(artifact_id=ref.artifact_id, filename=ref.filename) if ref else
               dict(artifact_ids=[r.artifact_id for r in members]))
    return dict(code="snapshot_bound_exceeded", stage="input", bound=name,
                actual=actual, limit=limits[name], **details)


def check_bound(name, actual, limits, *, ref=None, members=()):
    reason = bound_reason(name, actual, limits, ref=ref, members=members)
    if reason:
        raise ExtractionProblem("review_required", [reason])


def preflight(filing, limits):
    """Check the complete manifest before any I/O; unsupported selection wins."""
    unsupported = [dict(code="unsupported_selected_format", stage="input",
                        artifact_id=r.artifact_id, filename=r.filename)
                   for r in filing.artifacts if member_format(r) is None]
    if unsupported:
        raise ExtractionProblem("review_required", unsupported)
    html = [r for r in filing.artifacts if member_format(r) == "html"]
    images = [r for r in filing.artifacts if member_format(r) != "html"]
    reasons = []
    for name, actual, members in (
        ("max_documents", len(html), html), ("max_images", len(images), images),
        ("max_source_bytes", sum(r.size_bytes for r in filing.artifacts), filing.artifacts),
        ("max_image_total_bytes", sum(r.size_bytes for r in images), images),
    ):
        reason = bound_reason(name, actual, limits, members=members)
        if reason:
            reasons.append(reason)
    for ref in filing.artifacts:
        name = "max_document_bytes" if member_format(ref) == "html" else "max_image_bytes"
        reason = bound_reason(name, ref.size_bytes, limits, ref=ref)
        if reason:
            reasons.append(reason)
    if reasons:
        raise ExtractionProblem("review_required", reasons)


def verify_image(raw, kind, ref, limits):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format.lower() != kind or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("unsupported encoding or frames")
                check_bound("max_image_pixels", image.width * image.height, limits, ref=ref)
                check_bound("max_image_dimension", max(image.size), limits, ref=ref)
                image.verify()
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise problem("invalid_selected_image", "input", outcome="review_required",
                      artifact_id=ref.artifact_id, filename=ref.filename) from None


def prepare(filing, source, config):
    limits = config["input_limits"]
    preflight(filing, limits)
    # Exact evals public-context key order and attachment ordering. Full manifest
    # retained in the receipt, including source URIs/primary identity. No labels.
    context = {key: getattr(filing, key) for key in
               ("filing_id", "ticker", "company_name", "form_type", "filed_at", "cik")}
    blocks = [dict(type="input_text", text="Filing context: " + json.dumps(context, ensure_ascii=False))]
    inventory, text_bytes, image_count = [], 0, 0
    for ref in filing.artifacts:
        kind = member_format(ref)
        maximum = limits["max_document_bytes" if kind == "html" else "max_image_bytes"]
        try:
            raw = source.read(ref, max_bytes=maximum)
        except TechnicalFailure as exc:
            code = ("source_size_mismatch" if exc.code in {"stored_object_size_mismatch", "stored_object_exceeds_limit"}
                    else "source_object_missing" if exc.code == "source_object_missing" else "source_read_failed")
            raise problem(code, "input", retryable=exc.retryable,
                          artifact_id=ref.artifact_id, filename=ref.filename) from None
        except FileNotFoundError:
            raise problem("source_object_missing", "input", retryable=True,
                          artifact_id=ref.artifact_id, filename=ref.filename) from None
        except (OSError, TimeoutError):
            raise problem("source_read_failed", "input", retryable=True,
                          artifact_id=ref.artifact_id, filename=ref.filename) from None
        if not isinstance(raw, bytes) or len(raw) != ref.size_bytes:
            raise problem("source_size_mismatch", "input", retryable=True,
                          artifact_id=ref.artifact_id, filename=ref.filename)
        inventory.append(dict(artifact_id=ref.artifact_id, filename=ref.filename,
                              size_bytes=len(raw), sha256=sha256(raw).hexdigest()))
        blocks.append(dict(type="input_text", text="Source attachment: " + ref.filename))
        if kind == "html":
            try:
                text = plain_text_preview(raw) or "[No readable text in this attachment]"
            except (UnicodeError, ValueError, LookupError, RecursionError):
                raise problem("unsupported_document_encoding", "preparation", outcome="review_required",
                              artifact_id=ref.artifact_id, filename=ref.filename) from None
            text_bytes += len(text.encode("utf-8"))
            check_bound("max_text_bytes", text_bytes, limits, members=filing.artifacts)
            blocks.append(dict(type="input_text", text=text))
        else:
            verify_image(raw, kind, ref, limits)
            image_count += 1
            blocks.append(dict(type="input_image", detail="high",
                               image_url=f"data:image/{kind};base64," + b64encode(raw).decode("ascii")))
    return blocks, inventory, text_bytes, image_count


def check_request(parameters, filing, config, image_count):
    limits = config["input_limits"]
    # httpx uses this exact compact JSON encoding (also asserted at SDK transport).
    encoded = json.dumps(parameters, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    check_bound("max_encoded_request_bytes", len(encoded), limits, members=filing.artifacts)
    # Deliberately conservative local admission estimate, not a provider token
    # count. One token per UTF-8 text byte plus image/transport allowances.
    text = parameters["instructions"] + json.dumps(parameters["text"], ensure_ascii=False)
    text += "".join(b.get("text", "") for b in parameters["input"][0]["content"])
    estimate = len(text.encode("utf-8")) + image_count * limits["image_token_allowance"] + limits["token_overhead_allowance"]
    check_bound("max_input_token_estimate", estimate, limits, members=filing.artifacts)
    return dict(encoded_request_bytes=len(encoded), input_token_estimate=estimate)
