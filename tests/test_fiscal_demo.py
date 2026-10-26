import json

import pytest


def test_offline_demo_creates_reviewable_outputs(tmp_path):
    from finbot_earnings.processing.demo import run
    output = tmp_path / "demo"
    summary = run(output)
    assert summary["model_calls"] == 2 and summary["documents_per_call"] == [3, 3]
    assert summary["published_events"] == 1 and summary["duplicate_acknowledged"]
    assert json.loads((output / "published-events.jsonl").read_text())["event_type"] == "earnings.extracted"
    assert json.loads((output / "processing-record.json").read_text())["completion"]["outcome"] == "accepted"
    with pytest.raises(FileExistsError):
        run(output)

