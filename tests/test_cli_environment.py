from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finbot_earnings.cli import load_environment


class EnvironmentLoadingTests(unittest.TestCase):
    def test_loads_dotenv_from_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text("EARNINGS_TEST_DOTENV=loaded\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False), patch("os.getcwd", return_value=directory):
                os.environ.pop("EARNINGS_TEST_DOTENV", None)
                loaded = load_environment()
                self.assertEqual(Path(directory, ".env"), loaded)
                self.assertEqual("loaded", os.environ["EARNINGS_TEST_DOTENV"])
                os.environ.pop("EARNINGS_TEST_DOTENV", None)

    def test_dotenv_takes_precedence_over_exported_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".env").write_text("EARNINGS_TEST_DOTENV=from-file\n", encoding="utf-8")
            with patch.dict(os.environ, {"EARNINGS_TEST_DOTENV": "exported"}, clear=False), patch("os.getcwd", return_value=directory):
                load_environment()
                self.assertEqual("from-file", os.environ["EARNINGS_TEST_DOTENV"])


if __name__ == "__main__":
    unittest.main()
