from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import DiscoveredArtifact, SourceProvider


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith("utm_")))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def artifact_identity(discovery: DiscoveredArtifact, content_hash: str) -> str:
    if discovery.provider == SourceProvider.SEC and discovery.cik and discovery.accession_number:
        filename = discovery.filename or discovery.url.rsplit("/", 1)[-1]
        return f"sec:{discovery.cik.zfill(10)}:{discovery.accession_number}:{filename.lower()}"
    return f"ir:{canonical_url(discovery.url)}:{content_hash}"


def artifact_id(identity_key: str) -> str:
    return hashlib.sha256(identity_key.encode("utf-8")).hexdigest()[:24]

