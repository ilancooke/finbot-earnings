"""Traceable port of evals review.viewer's text-only helpers at d1057128.

Keep these semantics stable, including image-alt placeholders and table cells.
This is neither a browser nor an evidence validator; no resource is fetched.
"""

import html5lib

_DROP_CONTENT = frozenset({
    "head", "script", "style", "iframe", "object", "embed", "template",
    "svg", "math", "ix:header", "ix:hidden",
})


def _document_body(raw: bytes):
    parser = html5lib.HTMLParser(namespaceHTMLElements=False)
    root = parser.parse(raw, default_encoding="utf-8")
    # Added admission safeguard: preserve evals' detected encoding, but reject
    # undecodable bytes rather than allowing silent replacement characters.
    parser.tokenizer.stream.charEncoding[0].codec_info.decode(raw, "strict")

    def clean(parent):
        for child in list(parent):
            tag = child.tag.rsplit("}", 1)[-1] if isinstance(child.tag, str) else ""
            if tag in _DROP_CONTENT or not isinstance(child.tag, str):
                index = list(parent).index(child)
                if index:
                    previous = parent[index - 1]
                    previous.tail = (previous.tail or "") + (child.tail or "")
                else:
                    parent.text = (parent.text or "") + (child.tail or "")
                parent.remove(child)
            elif tag == "img":
                alt = child.attrib.get("alt", "").strip()
                child.attrib.clear()
                child.tag = "span"
                child.attrib["data-missing-image"] = "true"
                child.text = f" [Image: {alt}] " if alt else ""
            else:
                clean(child)

    clean(root)
    return root.find("body")


def plain_text_preview(raw: bytes) -> str:
    body = _document_body(raw)
    parts: list[str] = []
    blocks = {"p", "div", "tr", "br", "hr", "section", "li", "pre", "h1", "h2", "h3", "h4"}

    def walk(element):
        start = len(parts)
        if element.tag in blocks:
            parts.append("\n")
        if element.text:
            parts.append(element.text)
        for child in element:
            walk(child)
            if child.tail:
                parts.append(child.tail)
        if element.tag in {"td", "th"}:
            if any(part.strip() for part in parts[start:]):
                parts.append(" | ")
        elif element.tag in blocks:
            parts.append("\n")

    walk(body)
    return "\n".join(" ".join(line.split()) for line in "".join(parts).splitlines() if line.strip())
