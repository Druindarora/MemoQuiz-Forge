"""Tests for JSON batch imports."""

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge import importer
from memoquiz_forge.importer import (
    QuestionImportError,
    import_questions,
    import_questions_from_json,
)
from memoquiz_forge.questions import add_question, get_question, list_questions


class ImportQuestionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.database_path = self.directory / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_json(self, payload: object, name: str = "questions.json") -> Path:
        path = self.directory / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_imports_minimal_format_as_drafts(self) -> None:
        result = import_questions(
            self.database_path,
            self.write_json([{"question": "What is SQL?", "answer": "A query language."}]),
        )

        question = get_question(self.database_path, 1)
        assert question is not None
        self.assertEqual(result.imported, 1)
        self.assertEqual(question.status, "draft")
        self.assertFalse(question.exported)
        self.assertIsNone(question.domain)
        self.assertEqual(question.tags, [])

    def test_imports_enriched_format_and_multiple_questions(self) -> None:
        result = import_questions(
            self.database_path,
            self.write_json(
                [
                    {
                        "question": "What is an input?",
                        "answer": "A parent-to-child binding.",
                        "domain": "angular",
                        "concept": "component-communication",
                        "level": "basic",
                        "tags": ["input", "components"],
                    },
                    {"question": "What is Git?", "answer": "A VCS."},
                ]
            ),
        )

        first_question = get_question(self.database_path, 1)
        self.assertEqual(result.imported, 2)
        self.assertEqual(first_question.domain, "angular")
        self.assertEqual(first_question.concept, "component-communication")
        self.assertEqual(first_question.level, "basic")
        self.assertEqual(first_question.tags, ["input", "components"])

    def test_imports_json_payload_as_validated_questions(self) -> None:
        result = import_questions_from_json(
            self.database_path,
            json.dumps(
                [
                    {
                        "question": "What does an index accelerate?",
                        "answer": "Queries that can use its indexed columns.",
                        "domain": "sql",
                        "concept": "indexes",
                        "level": "intermediate",
                        "tags": ["performance"],
                    }
                ]
            ),
            status="validated",
        )

        question = get_question(self.database_path, 1)
        assert question is not None
        self.assertEqual(result.imported, 1)
        self.assertEqual(question.status, "validated")
        self.assertFalse(question.exported)

    def test_rejects_incomplete_validated_json_payload_without_writing(self) -> None:
        with self.assertRaisesRegex(
            QuestionImportError, "cannot import as validated: missing concept, level"
        ):
            import_questions_from_json(
                self.database_path,
                json.dumps(
                    [{"question": "What is SQL?", "answer": "A query language.", "domain": "sql"}]
                ),
                status="validated",
            )

        self.assertEqual(list_questions(self.database_path), [])

    def test_rejects_invalid_file_structure_without_writing(self) -> None:
        invalid_payloads = [
            {"question": "Not an array", "answer": "No"},
            [{"answer": "Missing question"}],
            [{"question": "Missing answer"}],
            [{"question": "", "answer": "Answer"}],
            [{"question": "Question", "answer": ""}],
            [{"question": 1, "answer": "Answer"}],
            [{"question": "Question", "answer": "Answer", "domain": 1}],
            [{"question": "Question", "answer": "Answer", "level": "expert"}],
            [{"question": "Question", "answer": "Answer", "tags": "tag"}],
            [{"question": "Question", "answer": "Answer", "tags": ["tag", 1]}],
            [{"question": "Question", "answer": "Answer", "status": "validated"}],
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(QuestionImportError):
                    import_questions(self.database_path, self.write_json(payload))
                self.assertEqual(list_questions(self.database_path), [])

    def test_reports_invalid_item_index(self) -> None:
        path = self.write_json(
            [
                {"question": "Question one", "answer": "Answer one"},
                {"question": "Question two"},
            ]
        )

        with self.assertRaisesRegex(QuestionImportError, r'Invalid item #2: "answer"'):
            import_questions(self.database_path, path)

    def test_rejects_invalid_json_and_missing_file(self) -> None:
        invalid_json = self.directory / "invalid.json"
        invalid_json.write_text("{not json", encoding="utf-8")

        with self.assertRaisesRegex(QuestionImportError, "Invalid JSON"):
            import_questions(self.database_path, invalid_json)
        with self.assertRaisesRegex(QuestionImportError, "File not found"):
            import_questions(self.database_path, self.directory / "missing.json")
        self.assertEqual(list_questions(self.database_path), [])

    def test_skips_exact_duplicates_from_database_and_same_file(self) -> None:
        add_question(self.database_path, question="What is SQL?", answer="A query language.")
        result = import_questions(
            self.database_path,
            self.write_json(
                [
                    {"question": "what is sql ?", "answer": "A query language."},
                    {"question": "What is Git?", "answer": "A VCS."},
                    {"question": " what is git? ", "answer": "A VCS."},
                ]
            ),
        )

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.skipped_duplicates, 2)
        self.assertEqual(len(list_questions(self.database_path)), 2)

    def test_imports_question_conflict_with_different_answer(self) -> None:
        add_question(self.database_path, question="What is SQL?", answer="A query language.")

        result = import_questions(
            self.database_path,
            self.write_json(
                [
                    {
                        "question": "what is sql ?",
                        "answer": "A language for relational databases.",
                    }
                ]
            ),
        )

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.question_conflicts, 1)

    def test_rolls_back_all_writes_when_an_unexpected_write_error_occurs(self) -> None:
        path = self.write_json(
            [
                {"question": "Question one", "answer": "Answer one"},
                {"question": "Question two", "answer": "Answer two"},
            ]
        )
        original_insert_question = importer._insert_question
        calls = 0

        def fail_on_second_insert(connection: object, item: object, status: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("disk failure")
            original_insert_question(connection, item)

        with patch(
            "memoquiz_forge.importer._insert_question", side_effect=fail_on_second_insert
        ):
            with self.assertRaisesRegex(RuntimeError, "disk failure"):
                import_questions(self.database_path, path)

        self.assertEqual(calls, 2)
        self.assertEqual(list_questions(self.database_path), [])
