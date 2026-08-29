from __future__ import annotations

import html
import json
import re
from abc import ABC, abstractmethod
from html.parser import HTMLParser
from pathlib import Path

from .clock import utc_now
from .models import ArtifactRecord, ArtifactType, ParsedArtifact

PARSER_VERSION = "html-v1"


class ArtifactParser(ABC):
    @abstractmethod
    def parse(self, artifact: ArtifactRecord) -> ParsedArtifact:
        raise NotImplementedError


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._ignored = 0
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
                self.parts.append("\n[TABLE]\n")
                self.parts.extend(" | ".join(row) + "\n" for row in self._table)
                self.parts.append("[/TABLE]\n")
            self._table = None

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        text = _clean(data)
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title or ''} {text}".strip()
        if self._cell is not None:
            self._cell.append(text)
        elif self._table is None:
            self.parts.append(text + " ")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


class HTMLArtifactParser(ArtifactParser):
    version = PARSER_VERSION

    def parse(self, artifact: ArtifactRecord) -> ParsedArtifact:
        raw = Path(artifact.raw_path).read_bytes()
        encoding = "utf-8"
        text = raw.decode(encoding, errors="replace")
        if artifact.raw_path.endswith(".json"):
            data = json.loads(text)
            readable = json.dumps(data, indent=2, sort_keys=True)
            title = artifact.metadata.get("title")
            tables: list[list[list[str]]] = []
        else:
            parser = _ReadableHTMLParser()
            parser.feed(text)
            readable = re.sub(r"[ \t]+\n", "\n", "".join(parser.parts))
            readable = re.sub(r"\n{3,}", "\n\n", readable).strip()
            title = artifact.metadata.get("title") or parser.title
            tables = parser.tables
        return ParsedArtifact(
            artifact_id=artifact.artifact_id, ticker=artifact.ticker,
            artifact_type=artifact.artifact_type, source_url=artifact.source_url,
            title=title, text=readable, tables=tables,
            parser_version=self.version, parsed_at=utc_now(),
        )

