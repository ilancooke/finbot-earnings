from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from finbot_earnings.cli import _fixture_runtime


class FixtureVerticalSliceTests(unittest.TestCase):
    def test_default_first_poll_baselines_without_artifacts_or_extraction(self):
        fixtures = Path(__file__).parent / "fixtures"
        with tempfile.TemporaryDirectory() as directory:
            store, pipeline, sources, extractor = _fixture_runtime(Path(directory), fixtures)
            try:
                for source in sources:
                    self.assertEqual(0, pipeline.poll_source(source, "NVDA"))
                self.assertEqual([], store.list_artifacts("NVDA"))
                self.assertEqual(0, extractor.calls)
            finally:
                store.close()

    def test_ir_and_sec_progressive_event_run_once(self):
        fixtures = Path(__file__).parent / "fixtures"
        with tempfile.TemporaryDirectory() as directory:
            store, pipeline, sources, extractor = _fixture_runtime(Path(directory), fixtures)
            try:
                for source in sources:
                    pipeline.poll_source(source, "NVDA", baseline_if_new=False)
                    pipeline.poll_source(source, "NVDA", baseline_if_new=False)
                records = store.list_artifacts("NVDA")
                self.assertEqual(4, len(records))
                self.assertEqual(4, extractor.calls)
                self.assertEqual(1, len({record.event_id for record in records}))
                timeline = store.timeline("NVDA")
                self.assertEqual(4, len(timeline["artifacts"]))
                self.assertTrue(all(item["structured_data_ready_at"] for item in timeline["artifacts"]))
                self.assertTrue(all(item["parse_started_at"] for item in timeline["artifacts"]))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
