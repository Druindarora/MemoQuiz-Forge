"""Tests for editing questions."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge.fingerprints import content_fingerprint, question_fingerprint
from memoquiz_forge.questions import (
    ExactDuplicateError,
    QuestionNotFoundError,
    add_question,
    edit_question,
    get_question,
)


class EditQuestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "forge.db"
        initialize_database(self.database_path)
        self.question_id = add_question(
            self.database_path,
            question="What is Git?",
            answer="A version control system.",
            domain="git",
            concept="basics",
            level="basic",
            tags=["vcs", "tools"],
        ).id

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_edits_one_field_and_preserves_others(self) -> None:
        result = edit_question(self.database_path, self.question_id, domain="architecture")

        question = get_question(self.database_path, self.question_id)
        assert question is not None
        self.assertTrue(result.modified)
        self.assertEqual(question.domain, "architecture")
        self.assertEqual(question.concept, "basics")
        self.assertEqual(question.answer, "A version control system.")
        self.assertEqual(question.tags, ["vcs", "tools"])

    def test_edits_multiple_fields_and_replaces_tags(self) -> None:
        edit_question(
            self.database_path,
            self.question_id,
            concept="merge-rebase",
            level="intermediate",
            tags=["branching", "history"],
        )

        question = get_question(self.database_path, self.question_id)
        assert question is not None
        self.assertEqual(question.concept, "merge-rebase")
        self.assertEqual(question.level, "intermediate")
        self.assertEqual(question.tags, ["branching", "history"])

    def test_updates_timestamp_when_a_change_is_made(self) -> None:
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET updated_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
                (self.question_id,),
            )

        edit_question(self.database_path, self.question_id, domain="architecture")

        question = get_question(self.database_path, self.question_id)
        assert question is not None
        self.assertNotEqual(question.updated_at, "2000-01-01T00:00:00.000Z")

    def test_recalculates_fingerprints_when_content_changes(self) -> None:
        edit_question(
            self.database_path,
            self.question_id,
            question="What is a Git repository?",
            answer="A project history database.",
        )

        question = get_question(self.database_path, self.question_id)
        assert question is not None
        with closing(connect(self.database_path)) as connection:
            fingerprints = connection.execute(
                "SELECT question_fingerprint, content_fingerprint FROM questions WHERE id = ?",
                (self.question_id,),
            ).fetchone()
        self.assertEqual(fingerprints[0], question_fingerprint("What is a Git repository?"))
        self.assertEqual(
            fingerprints[1],
            content_fingerprint("What is a Git repository?", "A project history database."),
        )

    def test_rejects_empty_question_or_answer(self) -> None:
        with self.assertRaisesRegex(ValueError, "Question must not be empty"):
            edit_question(self.database_path, self.question_id, question="  ")
        with self.assertRaisesRegex(ValueError, "Answer must not be empty"):
            edit_question(self.database_path, self.question_id, answer="")

    def test_rejects_exact_duplicate_without_partial_update(self) -> None:
        add_question(
            self.database_path,
            question="What is SQL?",
            answer="A query language.",
            domain="sql",
        )

        with self.assertRaisesRegex(ExactDuplicateError, "Exact duplicate"):
            edit_question(
                self.database_path,
                self.question_id,
                question="What is SQL?",
                answer="A query language.",
                domain="changed",
            )

        question = get_question(self.database_path, self.question_id)
        assert question is not None
        self.assertEqual(question.question, "What is Git?")
        self.assertEqual(question.domain, "git")

    def test_allows_question_conflict_with_different_answer(self) -> None:
        add_question(self.database_path, question="What is SQL?", answer="A query language.")

        result = edit_question(
            self.database_path,
            self.question_id,
            question="what is sql?",
            answer="A language for relational databases.",
        )

        self.assertTrue(result.has_question_conflict)

    def test_rejects_unknown_id_and_invalid_level(self) -> None:
        with self.assertRaisesRegex(QuestionNotFoundError, "Question not found: #42"):
            edit_question(self.database_path, 42, domain="sql")
        with self.assertRaisesRegex(ValueError, "Invalid level"):
            edit_question(self.database_path, self.question_id, level="expert")
