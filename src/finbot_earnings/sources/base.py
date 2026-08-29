from __future__ import annotations

import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Mapping

from ..clock import utc_now
from ..models import DiscoveredArtifact, DownloadedArtifact


@dataclass(frozen=True)
class HTTPResponse:
    body: bytes
    status_code: int
    headers: dict[str, str]
    final_url: str


class HTTPFetcher:
    def __init__(self, user_agent: str, timeout_seconds: float = 15.0):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> HTTPResponse:
        request_headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        request_headers.update(headers or {})
        request = urllib.request.Request(url, headers=request_headers)
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return HTTPResponse(
                body=response.read(), status_code=response.status,
                headers=dict(response.headers.items()), final_url=response.url,
            )

    def download(self, discovery: DiscoveredArtifact) -> DownloadedArtifact:
        started_at = utc_now()
        response = self.get(discovery.url)
        completed_at = utc_now()
        return DownloadedArtifact(
            discovery=discovery, body=response.body, download_started_at=started_at,
            downloaded_at=completed_at, status_code=response.status_code,
            headers=response.headers, final_url=response.final_url,
        )


class ArtifactSource(ABC):
    name: str

    @abstractmethod
    def poll(self) -> list[DiscoveredArtifact]:
        raise NotImplementedError

