from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from finbot_earnings.eligibility import ArtifactEligibilityPolicy
from finbot_earnings.extractors.base import EarningsExtractor, TransientExtractionError
from finbot_earnings.extractors.openai import OpenAIEarningsExtractor
from finbot_earnings.models import ArtifactType, EarningsExtraction, ProcessingState
from finbot_earnings.pipeline import EarningsPipeline
from finbot_earnings.sources.base import HTTPFetcher
from finbot_earnings.storage import ArtifactStore

from .helpers import ir_download


PROVIDER_DATA = {
    "ticker": "NVDA", "fiscal_period_raw": "First quarter fiscal 2027",
    "facts": [{"canonical_name": "revenue", "reported_label": "Revenue", "value_raw": "$81.6 billion", "value_numeric": 81600000000, "unit": "USD", "period_raw": "Q1 FY27", "gaap_status": "GAAP", "source_locator": "summary"}],
    "guidance": [], "highlights": ["Record revenue"],
}


class FakeResponses:
    def __init__(self, data):
        self.data = data
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        usage = SimpleNamespace(model_dump=lambda mode=None: {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
        return SimpleNamespace(output_text=json.dumps(self.data), usage=usage)


class FlakyExtractor(EarningsExtractor):
    provider = "fake"

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def extract(self, artifact):
        self.calls += 1
        if self.calls <= self.failures:
            raise TransientExtractionError("retry me")
        return EarningsExtraction.from_provider_dict(
            PROVIDER_DATA, artifact=artifact, prompt_version="test-prompt",
            schema_version="test-schema", model="fake", provider="fake",
        )


class ExtractionTests(unittest.TestCase):
    def test_openai_adapter_uses_strict_schema_and_validates_result(self):
        responses = FakeResponses(PROVIDER_DATA)
        extractor = OpenAIEarningsExtractor("gpt-test", client=SimpleNamespace(responses=responses))
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            record, _ = store.register(ir_download())
            from finbot_earnings.parsing import HTMLArtifactParser
            parsed = HTMLArtifactParser().parse(record)
            result = extractor.extract(parsed)
            store.close()
        self.assertEqual(81600000000, result.facts[0].value_numeric)
        self.assertEqual(record.artifact_id, result.facts[0].source_artifact_id)
        self.assertTrue(responses.kwargs["text"]["format"]["strict"])
        self.assertFalse(responses.kwargs["store"])

    def test_transient_extraction_is_bounded_and_then_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            extractor = FlakyExtractor(2)
            pipeline = EarningsPipeline(
                store, HTTPFetcher("test tests@example.com"), extractor,
                max_extraction_attempts=3, retry_delay_seconds=0,
            )
            self.assertTrue(pipeline.process_downloaded(ir_download()))
            record = store.list_artifacts("NVDA")[0]
            self.assertEqual(ProcessingState.EXTRACTED, record.state)
            self.assertEqual(2, record.retry_count)
            self.assertEqual(3, extractor.calls)
            self.assertFalse(pipeline.process_downloaded(ir_download()))
            self.assertEqual(3, extractor.calls)
            store.close()

    def test_persisted_artifact_resumes_without_redownload_or_duplicate_completed_call(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            downloaded = ir_download()
            persisted, _ = store.register(downloaded)
            self.assertEqual(ProcessingState.PERSISTED, persisted.state)
            extractor = FlakyExtractor(0)
            pipeline = EarningsPipeline(store, HTTPFetcher("test tests@example.com"), extractor, retry_delay_seconds=0)
            self.assertFalse(pipeline.process_downloaded(downloaded))
            self.assertEqual(1, extractor.calls)
            self.assertEqual(ProcessingState.EXTRACTED, store.get_artifact(persisted.artifact_id).state)
            self.assertFalse(pipeline.process_downloaded(downloaded))
            self.assertEqual(1, extractor.calls)
            store.close()

    def test_8k_requires_item_202(self):
        policy = ArtifactEligibilityPolicy()
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            record, _ = store.register(ir_download())
            record.artifact_type = ArtifactType.SEC_8K
            record.metadata = {"items": "1.01"}
            self.assertFalse(policy.decide(record).analyze)
            record.metadata = {"items": "2.02,9.01"}
            self.assertTrue(policy.decide(record).analyze)
            store.close()


if __name__ == "__main__":
    unittest.main()
