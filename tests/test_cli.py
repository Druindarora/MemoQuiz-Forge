"""Tests for the command-line interface."""

import os
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from memoquiz_forge.cli import main
from memoquiz_forge.database import connect


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


class ImportCommandTests(unittest.TestCase):
    def test_import_stdin_validated_creates_a_validated_question(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                payload = (
                    '[{"question":"What is SQL?","answer":"A query language.",'
                    '"domain":"sql","concept":"basics","level":"basic","tags":[]}]'
                )
                with (
                    patch("sys.argv", ["memoquiz-forge", "import", "--stdin", "--validated"]),
                    patch("sys.stdin", StringIO(payload)),
                    redirect_stdout(output),
                ):
                    main()
                with closing(connect(Path("data") / "memoquiz-forge.db")) as connection:
                    status = connection.execute("SELECT status FROM questions").fetchone()[0]
            finally:
                os.chdir(previous_directory)

            self.assertEqual(status, "validated")
            self.assertIn("- 1 imported", output.getvalue())


class ReadingCommandsTests(unittest.TestCase):
    def test_list_empty_database_displays_clear_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                with patch("sys.argv", ["memoquiz-forge", "list"]), redirect_stdout(output):
                    main()
            finally:
                os.chdir(previous_directory)

            self.assertEqual(output.getvalue(), "No questions found.\n")

    def test_show_displays_details_and_missing_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                with patch(
                    "sys.argv",
                    [
                        "memoquiz-forge",
                        "add",
                        "--question",
                        "What is SQL?",
                        "--answer",
                        "A query language.",
                        "--domain",
                        "sql",
                        "--tag",
                        "database",
                    ],
                ):
                    main()
                with patch("sys.argv", ["memoquiz-forge", "show", "1"]), redirect_stdout(output):
                    main()
                with patch("sys.argv", ["memoquiz-forge", "show", "42"]):
                    with self.assertRaisesRegex(SystemExit, "Question not found: #42"):
                        main()
            finally:
                os.chdir(previous_directory)

            self.assertIn("answer: A query language.", output.getvalue())
            self.assertIn("domain: sql", output.getvalue())
            self.assertIn("tags: database", output.getvalue())


class EditCommandTests(unittest.TestCase):
    def test_edit_missing_id_exits_with_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                with patch(
                    "sys.argv", ["memoquiz-forge", "edit", "42", "--domain", "sql"]
                ):
                    with self.assertRaisesRegex(
                        SystemExit, "Unable to edit question: Question not found: #42"
                    ):
                        main()
            finally:
                os.chdir(previous_directory)


class BulkValidationCommandTests(unittest.TestCase):
    def test_validate_all_displays_summary_and_incomplete_questions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                with patch(
                    "sys.argv",
                    [
                        "memoquiz-forge",
                        "add",
                        "--question",
                        "Complete question",
                        "--answer",
                        "Answer",
                        "--domain",
                        "sql",
                        "--concept",
                        "basics",
                        "--level",
                        "basic",
                    ],
                ):
                    main()
                with patch(
                    "sys.argv",
                    [
                        "memoquiz-forge",
                        "add",
                        "--question",
                        "Incomplete question",
                        "--answer",
                        "Answer",
                    ],
                ):
                    main()
                with patch("sys.argv", ["memoquiz-forge", "validate-all"]), redirect_stdout(
                    output
                ):
                    main()
            finally:
                os.chdir(previous_directory)

            self.assertIn("Bulk validation complete:", output.getvalue())
            self.assertIn("- 1 validated", output.getvalue())
            self.assertIn("- 1 incomplete skipped", output.getvalue())
            self.assertIn("- #2: missing domain, concept, level.", output.getvalue())

    def test_validate_all_reports_when_no_drafts_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = StringIO()
            previous_directory = Path.cwd()
            try:
                os.chdir(temporary_directory)
                with patch("sys.argv", ["memoquiz-forge", "init"]):
                    main()
                with patch("sys.argv", ["memoquiz-forge", "validate-all"]), redirect_stdout(
                    output
                ):
                    main()
            finally:
                os.chdir(previous_directory)

            self.assertEqual(output.getvalue(), "No draft questions found.\n")
