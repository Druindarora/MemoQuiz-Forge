"""Tests for adding questions."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memoquiz_forge.database import initialize_database
from memoquiz_forge.fingerprints import content_fingerprint, question_fingerprint
from memoquiz_forge.questions import ExactDuplicateError, add_question


class AddQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def fetch_question(self) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute("SELECT * FROM questions").fetchone()

    def test_adds_question_with_required_fields_only(self) -> None:
        added_question = add_question(
            self.database_path, question="What is SQLite?", answer="A database engine."
        )

        row = self.fetch_question()
        self.assertEqual(added_question.id, row["id"])
        self.assertEqual(row["status"], "draft")
        self.assertEqual(row["exported"], 0)
        self.assertIsNone(row["domain"])
        self.assertIsNone(row["concept"])
        self.assertIsNone(row["level"])
        self.assertEqual(json.loads(row["tags"]), [])
        self.assertIsNotNone(row["created_at"])
        self.assertEqual(row["created_at"], row["updated_at"])

    def test_adds_question_with_metadata(self) -> None:
        add_question(
            self.database_path,
            question="What is an index?",
            answer="A data structure that speeds up lookups.",
            domain="sql",
            concept="indexes",
            level="intermediate",
            tags=["database", "performance"],
        )

        row = self.fetch_question()
        self.assertEqual(row["domain"], "sql")
        self.assertEqual(row["concept"], "indexes")
        self.assertEqual(row["level"], "intermediate")
        self.assertEqual(json.loads(row["tags"]), ["database", "performance"])

    def test_question_mark_spacing_and_case_are_normalized(self) -> None:
        self.assertEqual(
            question_fingerprint("What is Git?"),
            question_fingerprint(" what is git ? "),
        )

    def test_apostrophes_and_accents_are_normalized(self) -> None:
        first_question = "  Qu’est-ce  que  l’été ?\r\n"
        second_question = "qu'est-ce que l'ete?"
        first_answer = "Une saison"
        second_answer = " une   saison "

        self.assertEqual(question_fingerprint(first_question), question_fingerprint(second_question))
        self.assertEqual(
            content_fingerprint(first_question, first_answer),
            content_fingerprint(second_question, second_answer),
        )

    def test_technical_symbols_remain_distinct(self) -> None:
        self.assertNotEqual(
            question_fingerprint("What is C?"), question_fingerprint("What is C#?")
        )
        self.assertNotEqual(question_fingerprint("="), question_fingerprint("!="))
        self.assertNotEqual(
            question_fingerprint("foo.bar"), question_fingerprint("foo bar")
        )
        self.assertNotEqual(
            content_fingerprint("Compare x <= y", "true"),
            content_fingerprint("Compare x < y", "true"),
        )

    def test_rejects_exact_duplicate(self) -> None:
        add_question(self.database_path, question="What is Git?", answer="A version control system")

        with self.assertRaisesRegex(ExactDuplicateError, "Exact duplicate"):
            add_question(
                self.database_path,
                question=" what is git? ",
                answer="A version control system",
            )

    def test_allows_question_conflict_with_different_answer(self) -> None:
        add_question(self.database_path, question="What is Git?", answer="A version control system.")

        added_question = add_question(
            self.database_path, question="what is git?", answer="A distributed VCS."
        )

        self.assertTrue(added_question.has_question_conflict)
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0], 2)

    def test_rejects_invalid_level(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid level"):
            add_question(
                self.database_path,
                question="What is Git?",
                answer="A version control system.",
                level="expert",
            )
