from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from finbot_earnings.models import ProcessingState
from finbot_earnings.storage import ArtifactStore

from .helpers import ir_download


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ArtifactStore(Path(self.temp.name))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_same_artifact_is_idempotent_and_changed_ir_content_is_versioned(self):
        first, first_new = self.store.register(ir_download(b"first"))
        again, again_new = self.store.register(ir_download(b"first"))
        changed, changed_new = self.store.register(ir_download(b"corrected"))
        self.assertTrue(first_new)
        self.assertFalse(again_new)
        self.assertEqual(first.artifact_id, again.artifact_id)
        self.assertTrue(changed_new)
        self.assertNotEqual(first.artifact_id, changed.artifact_id)
        self.assertEqual(2, len(self.store.list_artifacts("NVDA")))
        self.assertEqual(b"first", Path(first.raw_path).read_bytes())

    def test_event_grouping_uses_three_day_window(self):
        first, _ = self.store.register(ir_download(b"first", url="https://example/a"))
        second_download = ir_download(b"second", url="https://example/b")
        second, _ = self.store.register(second_download)
        self.assertEqual(first.event_id, second.event_id)

    def test_invalid_state_transition_is_rejected(self):
        record, _ = self.store.register(ir_download())
        with self.assertRaisesRegex(ValueError, "invalid processing-state transition"):
            self.store.update_state(record.artifact_id, ProcessingState.EXTRACTED)

    def test_naive_timestamp_is_rejected(self):
        download = ir_download()
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            type(download.discovery)(**{**download.discovery.__dict__, "detected_at": datetime(2026, 1, 1)})


if __name__ == "__main__":
    unittest.main()

