"""Tests for the command-line interface."""

import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from memoquiz_forge.cli import main


class InitCommandTests(unittest.TestCase):
    def test_init_creates_default_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]), redirect_stdout(output):
                    main()
            finally:
                os.chdir(previous_directory)

            self.assertTrue(
                (Path(temporary_directory) / "data" / "memoquiz-forge.db").is_file()
            )
            self.assertIn("Database initialized: data/memoquiz-forge.db", output.getvalue())


class AddCommandTests(unittest.TestCase):
    def test_add_reports_question_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]), redirect_stdout(output):
                    main()
                with patch(
                    "sys.argv",
                    [
                        "memoquiz-forge",
                        "add",
                        "--question",
                        "What is Git?",
                        "--answer",
                        "A version control system.",
                    ],
                ), redirect_stdout(output):
                    main()
                with patch(
                    "sys.argv",
                    [
                        "memoquiz-forge",
                        "add",
                        "--question",
                        "what is git?",
                        "--answer",
                        "A distributed VCS.",
                    ],
                ), redirect_stdout(output):
                    main()
            finally:
                os.chdir(previous_directory)

            self.assertIn("Question added as draft: #2", output.getvalue())
            self.assertIn("Warning: a question with similar text already exists.", output.getvalue())
