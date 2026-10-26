"""Immutable configuration and resource/code identity, independent of evals."""

from copy import deepcopy
from hashlib import sha256
from importlib import metadata
from importlib.resources import files
import json

from ..contracts import json_text

PACKAGE = "finbot_earnings.processing.fiscal"
SDK_VERSIONS = {"openai": "2.54.0", "httpx": "0.28.1", "html5lib": "1.1",
                "webencodings": "0.6.1", "six": "1.17.0", "Pillow": "12.3.0", "jsonschema": "4.26.0"}


def digest(value):
    return sha256(json_text(value).encode("utf-8")).hexdigest()


def resource(name):
    return files(PACKAGE).joinpath("resources", name).read_bytes()


def local_schema():
    return json.loads(resource("earnings_eps_fiscal_v2.schema.json"))


def transport_schema():
    """Byte-behavior equivalent to evals direct.output_schema(..., 'openai')."""
    result = deepcopy(local_schema())
    result.pop("$schema")
    original = result["$defs"]["observation"]
    original.pop("allOf")
    variants = []
    for period in ("quarterly", "annual"):
        variant = deepcopy(original)
        variant["properties"]["period_type"] = {"type": "string", "enum": [period]}
        variant["properties"]["fiscal_quarter"] = (
            {"type": "integer", "enum": [1, 2, 3, 4]} if period == "quarterly" else {"type": "null"})
        variants.append(variant)
    result["$defs"]["observation"] = {"anyOf": variants}
    return result


def configuration():
    """Build only when freezing a new version; callers use load_config()."""
    inventory = json.loads(resource("implementation.json"))
    preparation = {name: inventory["files"][name] for name in ("html_text.py", "prepare.py")}
    return dict(
        version="eps-openai-luna-v6-v1", provider="openai", model="gpt-6-luna",
        endpoint="https://api.openai.com/v1", prompt_version="eps-v6",
        prompt_sha256=sha256(resource("eps-v6.txt")).hexdigest(),
        response_schema_version="earnings_eps.fiscal.v2",
        response_schema_sha256=sha256(resource("earnings_eps_fiscal_v2.schema.json")).hexdigest(),
        transport_schema_version="openai-fiscal-v2-union-v1", transport_schema_sha256=digest(transport_schema()),
        preparation_version="filing-html-text-images-v1", preparation_sha256=digest(preparation),
        adapter_version="openai-luna-fiscal-v1", implementation_sha256=digest(inventory), sdk_versions=SDK_VERSIONS,
        acceptance_policy="fiscal-eps-acceptance-v1",
        request_settings=dict(max_output_tokens=4096, reasoning_effort="medium", image_detail="high",
                              store=False, truncation="disabled", service_tier="default",
                              prompt_cache_options=dict(mode="implicit", ttl="30m"),
                              timeout_seconds=120, sdk_max_retries=0),
        input_limits=dict(html_formats=["htm", "html", "xhtml"], image_formats=["jpeg", "png", "gif"],
                          max_documents=16, max_images=64, max_document_bytes=16 * 1024 * 1024,
                          max_source_bytes=64 * 1024 * 1024, max_text_bytes=2 * 1024 * 1024,
                          max_image_bytes=8 * 1024 * 1024, max_image_total_bytes=48 * 1024 * 1024,
                          max_image_pixels=16_000_000, max_image_dimension=8192,
                          max_encoded_request_bytes=96 * 1024 * 1024,
                          max_input_token_estimate=900_000, image_token_allowance=8192,
                          token_overhead_allowance=16384),
        persistence_limits=dict(max_response_bytes=2 * 1024 * 1024, max_extraction_bytes=64 * 1024,
                                max_event_bytes=240 * 1024),
    )


def load_config():
    """Fail closed on code/resource/dependency drift under the same version."""
    inventory = json.loads(resource("implementation.json"))
    for name, expected in inventory["files"].items():
        if sha256(files(PACKAGE).joinpath(name).read_bytes()).hexdigest() != expected:
            raise ValueError("fiscal implementation identity mismatch")
    for name, expected in SDK_VERSIONS.items():
        if metadata.version(name) != expected:
            raise ValueError("fiscal dependency version mismatch: " + name)
    frozen = json.loads(resource("configuration.json"))
    if frozen != configuration():
        raise ValueError("fiscal configuration identity mismatch")
    return frozen
