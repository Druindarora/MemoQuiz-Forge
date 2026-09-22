"""Tests for bulk validation of draft questions."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge.questions import add_question, get_question, validate_draft_questions


class BulkValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_question(self, *, domain="angular", concept="components", level="basic") -> int:
        return add_question(
            self.database_path,
            question=f"Question {len(self.ids) + 1}",
            answer="Answer",
            domain=domain,
            concept=concept,
            level=level,
        ).id

    @property
    def ids(self) -> list[int]:
        with closing(connect(self.database_path)) as connection:
            return [row[0] for row in connection.execute("SELECT id FROM questions ORDER BY id")]

    def set_status(self, question_id: int, status: str) -> None:
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute("UPDATE questions SET status = ? WHERE id = ?", (status, question_id))

    def set_updated_at(self, question_id: int) -> None:
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET updated_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
                (question_id,),
            )

    def test_validates_multiple_complete_drafts(self) -> None:
        first_id = self.add_question()
        second_id = self.add_question(domain="sql", concept="indexes", level="intermediate")

        result = validate_draft_questions(self.database_path)

        self.assertEqual(result.validated, 2)
        self.assertEqual(result.incomplete, [])
        self.assertEqual(get_question(self.database_path, first_id).status, "validated")
        self.assertEqual(get_question(self.database_path, second_id).status, "validated")

    def test_skips_incomplete_drafts_and_reports_their_fields(self) -> None:
        complete_id = self.add_question()
        incomplete_id = self.add_question(concept=None, level=None)
        self.set_updated_at(incomplete_id)

        result = validate_draft_questions(self.database_path)

        self.assertEqual(result.validated, 1)
        self.assertEqual([(item.id, item.problem) for item in result.incomplete], [
            (incomplete_id, "missing concept, level."),
        ])
        self.assertEqual(get_question(self.database_path, complete_id).status, "validated")
        incomplete = get_question(self.database_path, incomplete_id)
        self.assertEqual(incomplete.status, "draft")
        self.assertEqual(incomplete.updated_at, "2000-01-01T00:00:00.000Z")

    def test_filters_by_domain_concept_level_and_combination(self) -> None:
        angular_basic = self.add_question(domain="angular", concept="components", level="basic")
        angular_advanced = self.add_question(domain="angular", concept="routing", level="advanced")
        sql_basic = self.add_question(domain="sql", concept="indexes", level="basic")

        self.assertEqual(
            validate_draft_questions(self.database_path, domain="angular", level="basic").validated,
            1,
        )
        self.assertEqual(get_question(self.database_path, angular_basic).status, "validated")
        self.assertEqual(get_question(self.database_path, angular_advanced).status, "draft")
        self.assertEqual(get_question(self.database_path, sql_basic).status, "draft")

        self.assertEqual(
            validate_draft_questions(self.database_path, concept="routing").validated, 1
        )
        self.assertEqual(get_question(self.database_path, angular_advanced).status, "validated")
        self.assertEqual(validate_draft_questions(self.database_path, level="basic").validated, 1)
        self.assertEqual(get_question(self.database_path, sql_basic).status, "validated")

    def test_ignores_validated_and_rejected_questions(self) -> None:
        validated_id = self.add_question()
        rejected_id = self.add_question()
        self.set_status(validated_id, "validated")
        self.set_status(rejected_id, "rejected")
        self.set_updated_at(validated_id)
        self.set_updated_at(rejected_id)

        result = validate_draft_questions(self.database_path)

        self.assertEqual(result.selected, 0)
        self.assertEqual(get_question(self.database_path, validated_id).updated_at, "2000-01-01T00:00:00.000Z")
        self.assertEqual(get_question(self.database_path, rejected_id).updated_at, "2000-01-01T00:00:00.000Z")

    def test_updates_only_validated_questions_and_handles_no_match(self) -> None:
        complete_id = self.add_question(domain="angular")
        incomplete_id = self.add_question(domain=None)
        self.set_updated_at(complete_id)
        self.set_updated_at(incomplete_id)

        result = validate_draft_questions(self.database_path, domain="angular")

        self.assertEqual(result.validated, 1)
        self.assertNotEqual(
            get_question(self.database_path, complete_id).updated_at, "2000-01-01T00:00:00.000Z"
        )
        self.assertEqual(
            get_question(self.database_path, incomplete_id).updated_at, "2000-01-01T00:00:00.000Z"
        )
        self.assertEqual(validate_draft_questions(self.database_path, domain="java").selected, 0)
