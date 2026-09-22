"""Tests for validating and rejecting questions."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge.questions import (
    QuestionNotFoundError,
    QuestionValidationError,
    add_question,
    get_question,
    reject_question,
    validate_question,
)


class QuestionStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_complete_question(self) -> int:
        return add_question(
            self.database_path,
            question="What is SQL?",
            answer="A query language.",
            domain="sql",
            concept="basics",
            level="basic",
            tags=["database"],
        ).id

    def set_status(self, question_id: int, status: str) -> None:
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET status = ? WHERE id = ?", (status, question_id)
            )

    def set_updated_at(self, question_id: int) -> None:
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET updated_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
                (question_id,),
            )

    def test_validates_complete_draft(self) -> None:
        question_id = self.add_complete_question()

        result = validate_question(self.database_path, question_id)

        self.assertTrue(result.changed)
        self.assertEqual(get_question(self.database_path, question_id).status, "validated")

    def test_validates_complete_rejected_question(self) -> None:
        question_id = self.add_complete_question()
        self.set_status(question_id, "rejected")

        validate_question(self.database_path, question_id)

        self.assertEqual(get_question(self.database_path, question_id).status, "validated")

    def test_validated_question_needs_no_change(self) -> None:
        question_id = self.add_complete_question()
        self.set_status(question_id, "validated")
        self.set_updated_at(question_id)

        result = validate_question(self.database_path, question_id)

        self.assertFalse(result.changed)
        self.assertEqual(
            get_question(self.database_path, question_id).updated_at, "2000-01-01T00:00:00.000Z"
        )

    def test_validation_reports_each_missing_metadata_field(self) -> None:
        question_id = add_question(
            self.database_path, question="What is SQL?", answer="A query language."
        ).id

        with self.assertRaisesRegex(
            QuestionValidationError, r"missing domain, concept, level\."
        ):
            validate_question(self.database_path, question_id)

    def test_validation_reports_missing_domain_concept_or_level(self) -> None:
        for metadata_name in ("domain", "concept", "level"):
            with self.subTest(metadata_name=metadata_name):
                values = {"domain": "sql", "concept": "basics", "level": "basic"}
                values[metadata_name] = None
                question_id = add_question(
                    self.database_path,
                    question=f"Question {metadata_name}",
                    answer="Answer",
                    domain=values["domain"],
                    concept=values["concept"],
                    level=values["level"],
                ).id
                with self.assertRaisesRegex(
                    QuestionValidationError, f"missing {metadata_name}"
                ):
                    validate_question(self.database_path, question_id)

    def test_validate_updates_timestamp_only_when_status_changes(self) -> None:
        question_id = self.add_complete_question()
        self.set_updated_at(question_id)

        validate_question(self.database_path, question_id)

        self.assertNotEqual(
            get_question(self.database_path, question_id).updated_at, "2000-01-01T00:00:00.000Z"
        )

    def test_validate_rejects_unknown_id(self) -> None:
        with self.assertRaisesRegex(QuestionNotFoundError, "Question not found: #42"):
            validate_question(self.database_path, 42)

    def test_rejects_draft_and_preserves_content(self) -> None:
        question_id = self.add_complete_question()
        before = get_question(self.database_path, question_id)

        result = reject_question(self.database_path, question_id)

        after = get_question(self.database_path, question_id)
        self.assertTrue(result.changed)
        self.assertEqual(after.status, "rejected")
        self.assertEqual(after.question, before.question)
        self.assertEqual(after.answer, before.answer)
        self.assertEqual(after.domain, before.domain)
        self.assertEqual(after.tags, before.tags)

    def test_rejects_validated_question(self) -> None:
        question_id = self.add_complete_question()
        self.set_status(question_id, "validated")

        reject_question(self.database_path, question_id)

        self.assertEqual(get_question(self.database_path, question_id).status, "rejected")

    def test_rejected_question_needs_no_change(self) -> None:
        question_id = self.add_complete_question()
        self.set_status(question_id, "rejected")
        self.set_updated_at(question_id)

        result = reject_question(self.database_path, question_id)

        self.assertFalse(result.changed)
        self.assertEqual(
            get_question(self.database_path, question_id).updated_at, "2000-01-01T00:00:00.000Z"
        )

    def test_reject_updates_timestamp_and_rejects_unknown_id(self) -> None:
        question_id = self.add_complete_question()
        self.set_updated_at(question_id)

        reject_question(self.database_path, question_id)

        self.assertNotEqual(
            get_question(self.database_path, question_id).updated_at, "2000-01-01T00:00:00.000Z"
        )
        with self.assertRaisesRegex(QuestionNotFoundError, "Question not found: #42"):
            reject_question(self.database_path, 42)
