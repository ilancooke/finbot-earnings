"""Exact EPS scoring, independent of the conservative evidence validator."""

from collections import Counter


def fact_key(fact):
    return (fact["metric"], fact["period"]["kind"], fact["period"]["end_date"],
            fact["currency"], fact["value"].lstrip("+"))


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def counts(expected, actual):
    expected, actual = Counter(map(fact_key, expected)), Counter(map(fact_key, actual))
    matched = sum((expected & actual).values())
    return dict(true_positive=matched, false_positive=sum(actual.values()) - matched,
                false_negative=sum(expected.values()) - matched)


def metrics(counts):
    tp, fp, fn = (counts[name] for name in ("true_positive", "false_positive", "false_negative"))
    return {**counts, "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn)}


def score(expected, response, predicted, accepted, *, schema_valid):
    raw = counts(expected["facts"], predicted)
    classification_correct = schema_valid and response["classification"] == expected["classification"]
    return dict(schema_valid=schema_valid, classification_correct=classification_correct,
        exact_extraction=classification_correct and not raw["false_positive"] and not raw["false_negative"],
        extraction=metrics(raw), accepted=metrics(counts(expected["facts"], accepted)))


def summarize(results):
    total = len(results)
    summary = dict(cases=total, schema_valid=sum(row["scores"]["schema_valid"] for row in results),
        classification_accuracy=ratio(sum(row["scores"]["classification_correct"] for row in results), total),
        exact_extraction_accuracy=ratio(sum(row["scores"]["exact_extraction"] for row in results), total),
        technical_failures=sum(not row["acknowledged"] for row in results),
        outcomes=dict(Counter(row["outcome"] for row in results)))
    for group in ("extraction", "accepted"):
        summary[group] = metrics({name: sum(row["scores"][group][name] for row in results)
            for name in ("true_positive", "false_positive", "false_negative")})
    return summary
