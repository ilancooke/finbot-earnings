"""Shared company-period reconciliation, independent of the storage engine."""

from collections import defaultdict

from .contracts import json_text, utc_text
from .domain import economic_value
from .errors import TechnicalFailure


def plan_completion(job, validation, current_event, now):
    """Return completion and (event_id, prior_revision, new_payload_or_none).

    The caller must atomically verify each prior revision while committing the
    result. Even economic duplicates require that revision check.
    """
    findings, accepted = list(validation.findings), list(validation.accepted)
    publications, changes, conflicts = [], [], set()
    if job["identity"]["run_mode"] == "production":
        grouped = defaultdict(list)
        for fact in accepted:
            grouped[(fact["period"]["kind"], fact["period"]["end_date"])].append(fact)
        for (kind, end), facts in sorted(grouped.items()):
            event_id = f'{job["input"]["cik"]}:{kind}:{end}'
            current = current_event(event_id)
            existing = {} if current is None else {fact["metric"]: fact for fact in current["facts"]}
            prior_revision = None if current is None else current["revision"]
            if any(fact["metric"] in existing and economic_value(fact) != economic_value(existing[fact["metric"]]) for fact in facts):
                findings.append(dict(code="canonical_fact_conflict", event_id=event_id))
                conflicts.add((kind, end))
                changes.append((event_id, prior_revision, None))
                continue
            additions = [fact for fact in facts if fact["metric"] not in existing]
            payload = None
            if current is not None and not additions:
                revision = current["revision"]
            else:
                revision = 1 if current is None else current["revision"] + 1
                for fact in additions:
                    existing[fact["metric"]] = fact
                source = {name: job["input"][name] for name in (
                    "filing_id", "snapshot_id", "form_type", "filed_at", "primary_artifact_id", "artifacts")}
                sources = [] if current is None else list(current["source_snapshots"])
                if source not in sources:
                    sources.append(source)
                payload = dict(event_type="earnings.validated", schema_version="1.0", event_id=event_id,
                    revision=revision, cik=job["input"]["cik"], ticker=job["input"]["ticker"],
                    company_name=job["input"]["company_name"], period=dict(kind=kind, end_date=end),
                    facts=[existing[metric] for metric in sorted(existing)], source_snapshots=sources,
                    validated_at=utc_text(now), validation_policy=job["config"]["validation_policy"])
                if len(json_text(payload).encode("utf-8")) > 256 * 1024:
                    raise TechnicalFailure("publication_exceeds_limit", retryable=False)
            publications.append([event_id, revision])
            changes.append((event_id, prior_revision, payload))
    accepted = [fact for fact in accepted if (fact["period"]["kind"], fact["period"]["end_date"]) not in conflicts]
    outcome = "review_required" if validation.outcome == "validated" and not accepted else validation.outcome
    completion = dict(outcome=outcome, findings=findings, accepted_facts=accepted,
                      publications=publications, completed_at=utc_text(now))
    return completion, changes
