"""Tests for MemoQuiz JSON exports."""

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge.exporter import QuestionExportError, export_questions
from memoquiz_forge.questions import add_question, get_question


class ExportQuestionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database_path = self.directory / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_question(
        self,
        question: str,
        *,
        domain: str = "angular",
        concept: str = "components",
        level: str = "basic",
        status: str = "validated",
        exported: bool = False,
    ) -> int:
        question_id = add_question(
            self.database_path,
            question=question,
            answer=f"Answer for {question}",
            domain=domain,
            concept=concept,
            level=level,
            tags=["tag"],
        ).id
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET status = ?, exported = ? WHERE id = ?",
                (status, int(exported), question_id),
            )
        return question_id

    def load_export(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8") as exported_file:
            return json.load(exported_file)

    def test_exports_one_question_with_memoquiz_format_and_unicode(self) -> None:
        question_id = self.add_question("Qu'est-ce qu'un composant ?")
        output_path = self.directory / "memoquiz.json"

        result = export_questions(self.database_path, output_path, count=20)

        self.assertEqual(result.exported, 1)
        self.assertEqual(
            self.load_export(output_path),
            [
                {
                    "question": "Qu'est-ce qu'un composant ?",
                    "answer": "Answer for Qu'est-ce qu'un composant ?",
                }
            ],
        )
        self.assertEqual(set(self.load_export(output_path)[0]), {"question", "answer"})
        exported_question = get_question(self.database_path, question_id)
        self.assertTrue(exported_question.exported)
        self.assertIsNotNone(exported_question.exported_at)

    def test_exports_multiple_questions_by_id_and_respects_count(self) -> None:
        first_id = self.add_question("First")
        second_id = self.add_question("Second")
        third_id = self.add_question("Third")
        output_path = self.directory / "memoquiz.json"

        result = export_questions(self.database_path, output_path, count=2)

        self.assertEqual(result.exported, 2)
        self.assertEqual(
            [item["question"] for item in self.load_export(output_path)], ["First", "Second"]
        )
        self.assertTrue(get_question(self.database_path, first_id).exported)
        self.assertTrue(get_question(self.database_path, second_id).exported)
        self.assertFalse(get_question(self.database_path, third_id).exported)

    def test_ignores_non_validated_and_already_exported_questions(self) -> None:
        draft_id = self.add_question("Draft", status="draft")
        rejected_id = self.add_question("Rejected", status="rejected")
        exported_id = self.add_question("Already exported", exported=True)
        selected_id = self.add_question("Selected")
        output_path = self.directory / "memoquiz.json"

        export_questions(self.database_path, output_path, count=20)

        self.assertEqual([item["question"] for item in self.load_export(output_path)], ["Selected"])
        self.assertFalse(get_question(self.database_path, draft_id).exported)
        self.assertFalse(get_question(self.database_path, rejected_id).exported)
        self.assertTrue(get_question(self.database_path, exported_id).exported)
        self.assertTrue(get_question(self.database_path, selected_id).exported)

    def test_filters_by_metadata_and_combines_filters(self) -> None:
        angular_id = self.add_question("Angular", domain="angular", concept="components", level="basic")
        self.add_question("Routing", domain="angular", concept="routing", level="advanced")
        self.add_question("SQL", domain="sql", concept="indexes", level="basic")
        output_path = self.directory / "memoquiz.json"

        result = export_questions(
            self.database_path,
            output_path,
            count=20,
            domain="angular",
            concept="components",
            level="basic",
        )

        self.assertEqual(result.exported, 1)
        self.assertEqual(self.load_export(output_path)[0]["question"], "Angular")
        self.assertTrue(get_question(self.database_path, angular_id).exported)

    def test_exports_fewer_available_questions_and_creates_no_file_when_empty(self) -> None:
        self.add_question("Only question")
        output_path = self.directory / "memoquiz.json"

        result = export_questions(self.database_path, output_path, count=20)
        empty_path = self.directory / "empty.json"
        empty_result = export_questions(self.database_path, empty_path, count=20)

        self.assertEqual(result.exported, 1)
        self.assertEqual(empty_result.exported, 0)
        self.assertFalse(empty_path.exists())

    def test_refuses_to_overwrite_unless_forced(self) -> None:
        self.add_question("Question")
        output_path = self.directory / "memoquiz.json"
        output_path.write_text("existing", encoding="utf-8")

        with self.assertRaisesRegex(QuestionExportError, "already exists"):
            export_questions(self.database_path, output_path, count=1)
        self.assertEqual(output_path.read_text(encoding="utf-8"), "existing")

        result = export_questions(self.database_path, output_path, count=1, force=True)
        self.assertEqual(result.exported, 1)
        self.assertEqual(self.load_export(output_path)[0]["question"], "Question")

    def test_marks_timestamps_only_after_successful_write(self) -> None:
        question_id = self.add_question("Question")
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE questions SET updated_at = '2000-01-01T00:00:00.000Z' WHERE id = ?",
                (question_id,),
            )

        export_questions(self.database_path, self.directory / "memoquiz.json", count=1)

        question = get_question(self.database_path, question_id)
        self.assertNotEqual(question.updated_at, "2000-01-01T00:00:00.000Z")
        self.assertIsNotNone(question.exported_at)

    def test_does_not_mark_questions_when_file_write_fails(self) -> None:
        question_id = self.add_question("Question")
        output_path = self.directory / "memoquiz.json"

        with patch(
            "memoquiz_forge.exporter._write_payload", side_effect=OSError("disk full")
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                export_questions(self.database_path, output_path, count=1)

        question = get_question(self.database_path, question_id)
        self.assertFalse(question.exported)
        self.assertIsNone(question.exported_at)

    def test_rejects_non_positive_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly positive"):
            export_questions(self.database_path, self.directory / "memoquiz.json", count=0)
