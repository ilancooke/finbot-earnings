from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from finbot_earnings.models import ArtifactType, DiscoveredArtifact, DownloadedArtifact, SourceProvider
from finbot_earnings.sources.base import HTTPFetcher, HTTPResponse

NOW = datetime(2026, 8, 26, 16, 55, tzinfo=timezone.utc)


def ir_download(body: bytes = b"<html><body>Revenue $10 billion</body></html>", *, url: str = "https://investor.example/release") -> DownloadedArtifact:
    discovery = DiscoveredArtifact(
        ticker="NVDA", provider=SourceProvider.NVIDIA_IR,
        artifact_type=ArtifactType.IR_EARNINGS_RELEASE, url=url,
        detected_at=NOW, published_at=NOW, title="NVIDIA Announces Financial Results",
        external_id="release-1", filename="release.html",
    )
    return DownloadedArtifact(discovery, body, NOW, NOW, 200, {"Content-Type": "text/html"}, url)


class MapFetcher(HTTPFetcher):
    def __init__(self, responses: dict[str, tuple[bytes, str]]):
        super().__init__("finbot-earnings tests@example.com")
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, headers=None) -> HTTPResponse:
        self.calls.append(url)
        body, content_type = self.responses[url]
        return HTTPResponse(body, 200, {"Content-Type": content_type}, url)

