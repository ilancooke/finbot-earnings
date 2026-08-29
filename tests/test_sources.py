from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from finbot_earnings.models import ArtifactType
from finbot_earnings.sources.nvidia_ir import NVIDIA_PRESS_RELEASE_RSS, NvidiaIRSource
from finbot_earnings.sources.sec import SECSource, classify_form, exhibit_type, recent_filings

from .helpers import MapFetcher

FIXTURES = Path(__file__).parent / "fixtures"


class SourceTests(unittest.TestCase):
    def test_sec_classification_and_earnings_exhibits(self):
        submissions = (FIXTURES / "sec_submissions.json").read_bytes()
        index = (FIXTURES / "sec_index.json").read_bytes()
        base = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000099"
        fetcher = MapFetcher({
            "https://data.sec.gov/submissions/CIK0001045810.json": (submissions, "application/json"),
            f"{base}/index.json": (index, "application/json"),
        })
        source = SECSource("NVDA", "1045810", fetcher)
        discoveries = source.poll()
        self.assertEqual(
            [ArtifactType.SEC_8K, ArtifactType.EXHIBIT_99_1, ArtifactType.CFO_COMMENTARY],
            [item.artifact_type for item in discoveries],
        )
        self.assertTrue(all(item.accession_number == "0001045810-26-000099" for item in discoveries))
        self.assertEqual("2.02,9.01", discoveries[0].metadata["items"])
        self.assertEqual(datetime(2026, 8, 26, 20, 51, 22, tzinfo=timezone.utc), discoveries[0].published_at)
        source.poll()
        self.assertEqual(1, fetcher.calls.count(f"{base}/index.json"))

    def test_sec_acceptance_time_is_interpreted_as_eastern_across_dst(self):
        self.assertEqual(
            datetime(2026, 8, 26, 20, 21, 19, tzinfo=timezone.utc),
            SECSource._acceptance_time("2026-08-26T16:21:19.000Z"),
        )
        self.assertEqual(
            datetime(2026, 1, 26, 21, 21, 19, tzinfo=timezone.utc),
            SECSource._acceptance_time("2026-01-26T16:21:19.000Z"),
        )

    def test_ir_feed_only_returns_financial_results(self):
        rss = (FIXTURES / "nvidia_rss.xml").read_bytes()
        source = NvidiaIRSource(MapFetcher({NVIDIA_PRESS_RELEASE_RSS: (rss, "application/xml")}))
        discoveries = source.poll()
        self.assertEqual(1, len(discoveries))
        self.assertEqual(ArtifactType.IR_EARNINGS_RELEASE, discoveries[0].artifact_type)
        self.assertIsNotNone(discoveries[0].published_at)

    def test_helpers_ignore_unrelated_forms_and_names(self):
        self.assertIsNone(classify_form("4"))
        self.assertEqual(ArtifactType.SEC_10Q, classify_form("10-Q"))
        self.assertEqual(ArtifactType.EXHIBIT_99_1, exhibit_type("EX-99.1.htm"))
        self.assertEqual(ArtifactType.EXHIBIT_99_1, exhibit_type("q1fy27pr.htm"))
        self.assertEqual(ArtifactType.CFO_COMMENTARY, exhibit_type("q1fy27cfocommentary.htm"))
        self.assertIsNone(exhibit_type("cover.htm"))


if __name__ == "__main__":
    unittest.main()
