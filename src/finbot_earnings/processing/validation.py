"""Conservative explicit-prose evidence checks, independent of the model.

Tables, inferred periods/currencies and implicit accounting labels require review.
Raw documents are still supplied intact to the model; these views only verify evidence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
import re

from .domain import Document, Fact, response_facts


def normalized(value):
    return " ".join(value.split()).casefold()


@dataclass(frozen=True)
class Block:
    text: str
    heading: bool = False
    table: bool = False


class _HTMLView(HTMLParser):
    boundaries = {"title", "h1", "h2", "h3", "h4", "p", "div", "section", "li", "tr", "table", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.parts, self.blocks = [], [], []
        self.kind = (False, False)

    def flush(self):
        text = " ".join("".join(self.parts).split())
        if text:
            self.blocks.append(Block(text, *self.kind))
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.boundaries:
            self.flush()
        attributes = dict(attrs)
        hidden = (tag in {"script", "style", "noscript"} or "hidden" in attributes
                  or attributes.get("aria-hidden") == "true"
                  or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attributes.get("style", ""), re.I))
        if tag not in {"br", "meta", "link", "img", "hr", "input", "wbr"}:
            self.stack.append((tag, bool(hidden)))

    def handle_endtag(self, tag):
        if tag in self.boundaries:
            self.flush()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, text):
        if any(hidden for _, hidden in self.stack):
            return
        kind = (any(tag in {"title", "h1", "h2", "h3", "h4"} for tag, _ in self.stack),
                any(tag == "table" for tag, _ in self.stack))
        if self.parts and kind != self.kind:
            self.flush()
        self.kind = kind
        self.parts.append(text)


def document_blocks(document: Document):
    text = document.body.decode("utf-8-sig", errors="strict")
    if document.reference.filename.lower().endswith((".htm", ".html")):
        parser = _HTMLView()
        parser.feed(text)
        parser.close()
        parser.flush()
        return tuple(parser.blocks)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return tuple(Block(line, heading=index < 2) for index, line in enumerate(lines))


_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
_DATE = r"(?:\d{4}-\d{2}-\d{2}|(?:" + "|".join(_MONTHS) + r")\s+\d{1,2},?\s+\d{4})"
_PERIOD = re.compile(r"(?<!\w)(?:for\s+the\s+)?(?:fiscal\s+)?(?P<kind>three months|quarter|six months|half[- ]year|twelve months|year)\s+ended\s+(?P<end>" + _DATE + r")(?!\w)", re.I)


def periods(text):
    result = []
    for match in _PERIOD.finditer(text):
        kind = normalized(match["kind"])
        kind = "quarter" if kind in {"quarter", "three months"} else "annual" if kind in {"year", "twelve months"} else "half_year"
        raw = normalized(match["end"])
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                end = date.fromisoformat(raw)
            else:
                month, day, year = raw.replace(",", "").split()
                end = date(int(year), _MONTHS.index(month) + 1, int(day))
            result.append((kind, end.isoformat()))
        except ValueError:
            continue
    return result


_CURRENCIES = {"us$": "USD", "usd": "USD", "eur": "EUR", "€": "EUR", "gbp": "GBP", "£": "GBP",
               "cad": "CAD", "c$": "CAD", "aud": "AUD", "a$": "AUD", "jpy": "JPY", "chf": "CHF",
               "cny": "CNY", "inr": "INR"}
_OBSERVATION = re.compile(
    r"(?<![\w-])(?P<basis>non-gaap|adjusted|gaap)\s+diluted\s+(?P<measure>earnings|loss)(?:\s+per\s+share)"
    r"\s*(?:was|were|of|:|=)\s*(?P<currency>US\$|C\$|A\$|USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|INR|€|£)\s*"
    r"(?P<number>\(?[+\-−]?(?:0|[1-9]\d*)(?:\.\d+)?\)?)(?![\w%]|[.,']\d)", re.I)


def observations(text):
    result = []
    for match in _OBSERVATION.finditer(text):
        raw = match["number"].replace("−", "-")
        if raw.startswith("(") != raw.endswith(")"):
            continue
        negative = raw.startswith("(") or normalized(match["measure"]) == "loss" or raw.startswith("-")
        number = raw.strip("()").lstrip("+-")
        value = ("-" if negative else "") + number
        metric = "gaap_diluted_eps" if normalized(match["basis"]) == "gaap" else "adjusted_diluted_eps"
        result.append((metric, value, _CURRENCIES[normalized(match["currency"])]))
    return result


def owned_document(blocks, company_name):
    prefix = normalized(company_name)
    return any(block.heading and not block.table
               and re.match(re.escape(prefix) + r"(?:\W|$)", normalized(block.text))
               and re.search(r"\b(?:earnings|results|report|financial)\b", normalized(block.text))
               for block in blocks)


@dataclass(frozen=True)
class ValidationResult:
    outcome: str
    findings: tuple[dict, ...]
    accepted: tuple[dict, ...] = ()


def validate(filing, documents, response, config):
    facts = response_facts(response, config)
    classification = response["classification"]
    if classification != "reports_earnings":
        if classification == "does_not_report_earnings" and not facts:
            return ValidationResult("no_relevant_earnings", ())
        return ValidationResult("review_required", ({"code": "uncertain_or_inconsistent_classification"},))
    pdf_ids = {document.reference.artifact_id for document in documents
               if document.reference.filename.lower().endswith(".pdf")}
    views = {document.reference.artifact_id: document_blocks(document) for document in documents
             if document.reference.artifact_id not in pdf_ids}
    declared = defaultdict(set)
    for blocks in views.values():
        if owned_document(blocks, filing.company_name):
            for block in blocks:
                if block.heading and not block.table:
                    for kind, end in periods(block.text):
                        declared[kind].add(end)
    findings, accepted, conflicts = [], [], set()
    candidates = defaultdict(set)
    for fact in facts:
        candidates[(fact.period_key, fact.metric)].add((Decimal(fact.value), fact.currency))
    for (period_key, _), values in candidates.items():
        if len(values) > 1:
            conflicts.add(period_key)
    for fact in facts:
        code = ("pdf_evidence_requires_review" if fact.source_artifact_id in pdf_ids
                else _fact_error(fact, filing, views, declared))
        if fact.period_key in conflicts:
            code = "material_fact_conflict"
        if code:
            findings.append(dict(code=code, source_artifact_id=fact.source_artifact_id,
                                 metric=fact.metric, period=fact.period_key))
        else:
            accepted.append(fact.to_dict())
    # Exact repeated observations do not become duplicate canonical metrics.
    unique = {}
    for fact in accepted:
        key = (fact["period"]["kind"], fact["period"]["end_date"], fact["metric"])
        unique.setdefault(key, fact)
    if not unique and not findings:
        findings.append({"code": "no_supported_core_metric"})
    return ValidationResult("validated" if unique else "review_required", tuple(findings), tuple(unique.values()))


def _fact_error(fact, filing, views, declared):
    blocks = views.get(fact.source_artifact_id)
    if blocks is None:
        return "source_not_in_manifest"
    if not owned_document(blocks, filing.company_name):
        return "company_identity_unresolved"
    if declared[fact.period_kind] != {fact.period_end} or fact.period_end > filing.filed_at[:10]:
        return "current_reporting_period_unresolved"
    label_periods = periods(fact.period_label)
    if label_periods != [(fact.period_kind, fact.period_end)]:
        return "period_label_mismatch"
    evidence = normalized(fact.evidence)
    # This initial policy requires the whole short prose block. A selectively
    # clipped quotation must not hide a unit, forecast qualifier or negation.
    matches = [block for block in blocks if not block.table and len(block.text) <= 2000
               and evidence == normalized(block.text)]
    if not matches:
        return "evidence_not_in_supported_prose"
    if normalized(fact.period_label) not in evidence or periods(fact.evidence) != [(fact.period_kind, fact.period_end)]:
        return "period_not_bound_to_metric"
    if re.search(r"\b(?:guidance|outlook|expect\w*|forecast\w*|project\w*|target\w*|not|would|could|may|will)\b", evidence):
        return "reported_result_unresolved"
    if re.search(r"\b(?:cents?|pence|thousands?|millions?|billions?|percent|ads|basic)\b|%", evidence):
        return "units_or_share_basis_unresolved"
    observed = [value for value in observations(fact.evidence) if value[0] == fact.metric]
    if len(observed) != 1:
        return "metric_value_binding_unresolved"
    _, value, currency = observed[0]
    if currency != fact.currency:
        return "currency_mismatch"
    if value != fact.value.lstrip("+"):
        return "value_sign_or_precision_mismatch"
    return None
