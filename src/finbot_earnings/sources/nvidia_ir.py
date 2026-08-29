from __future__ import annotations

import email.utils
import re
import xml.etree.ElementTree as ET

from ..clock import ensure_utc, utc_now
from ..models import ArtifactType, DiscoveredArtifact, SourceProvider
from .base import ArtifactSource, HTTPFetcher

NVIDIA_PRESS_RELEASE_RSS = "https://nvidianews.nvidia.com/cats/press_release.xml"
_EARNINGS_TITLE = re.compile(r"nvidia\s+announces\s+financial\s+results", re.IGNORECASE)


class NvidiaIRSource(ArtifactSource):
    name = "nvidia_ir"

    def __init__(self, fetcher: HTTPFetcher, rss_url: str = NVIDIA_PRESS_RELEASE_RSS):
        self.fetcher = fetcher
        self.rss_url = rss_url

    def poll(self) -> list[DiscoveredArtifact]:
        response = self.fetcher.get(self.rss_url, {"Accept": "application/rss+xml, application/xml, text/xml"})
        root = ET.fromstring(response.body)
        detected_at = utc_now()
        discoveries: list[DiscoveredArtifact] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not link or not _EARNINGS_TITLE.search(title):
                continue
            guid = (item.findtext("guid") or "").strip() or None
            published = self._published(item.findtext("pubDate"))
            discoveries.append(DiscoveredArtifact(
                ticker="NVDA", provider=SourceProvider.NVIDIA_IR,
                artifact_type=ArtifactType.IR_EARNINGS_RELEASE, url=link,
                detected_at=detected_at, published_at=published, title=title,
                external_id=guid, filename=link.rstrip("/").rsplit("/", 1)[-1] or "release.html",
                metadata={"feed_url": self.rss_url},
            ))
        return discoveries

    @staticmethod
    def _published(value: str | None):
        if not value:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(value)
            return ensure_utc(parsed)
        except (TypeError, ValueError):
            return None

