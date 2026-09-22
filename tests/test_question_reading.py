"""Tests for listing and retrieving questions."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from memoquiz_forge.database import connect, initialize_database
from memoquiz_forge.questions import add_question, get_question, list_questions


class QuestionReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "forge.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_sample_questions(self) -> None:
        angular = add_question(
            self.database_path,
            question="What is an Angular component?",
            answer="A UI building block.",
            domain="angular",
            concept="components",
            level="basic",
            tags=["frontend"],
        )
        sql = add_question(
            self.database_path,
            question="What is an SQL index?",
            answer="A lookup structure.",
            domain="sql",
            concept="indexes",
            level="intermediate",
            tags=["database", "performance"],
        )
        git = add_question(
            self.database_path,
            question="What does git rebase do?",
            answer="It reapplies commits.",
            domain="git",
            concept="merge-rebase",
            level="advanced",
        )
        with closing(connect(self.database_path)) as connection, connection:
            connection.execute("UPDATE questions SET status = 'validated' WHERE id = ?", (sql.id,))
            connection.execute("UPDATE questions SET exported = 1 WHERE id = ?", (git.id,))
        self.angular_id = angular.id
        self.sql_id = sql.id
        self.git_id = git.id

    def test_list_is_empty_when_no_questions_exist(self) -> None:
        self.assertEqual(list_questions(self.database_path), [])

    def test_list_returns_multiple_questions(self) -> None:
        self.add_sample_questions()

        self.assertEqual([question.id for question in list_questions(self.database_path)], [1, 2, 3])

    def test_list_filters_by_status(self) -> None:
        self.add_sample_questions()

        questions = list_questions(self.database_path, status="validated")

        self.assertEqual([question.id for question in questions], [self.sql_id])

    def test_list_filters_by_domain(self) -> None:
        self.add_sample_questions()

        questions = list_questions(self.database_path, domain="angular")

        self.assertEqual([question.id for question in questions], [self.angular_id])

    def test_list_filters_by_concept(self) -> None:
        self.add_sample_questions()

        questions = list_questions(self.database_path, concept="indexes")

        self.assertEqual([question.id for question in questions], [self.sql_id])

    def test_list_filters_by_level(self) -> None:
        self.add_sample_questions()

        questions = list_questions(self.database_path, level="advanced")

        self.assertEqual([question.id for question in questions], [self.git_id])

    def test_list_filters_unexported_questions(self) -> None:
        self.add_sample_questions()

        questions = list_questions(self.database_path, unexported=True)

        self.assertEqual([question.id for question in questions], [self.angular_id, self.sql_id])

    def test_list_combines_filters(self) -> None:
        self.add_sample_questions()

        questions = list_questions(
            self.database_path, domain="angular", status="draft", unexported=True
        )

        self.assertEqual([question.id for question in questions], [self.angular_id])

    def test_get_question_returns_full_details(self) -> None:
        self.add_sample_questions()

        question = get_question(self.database_path, self.sql_id)

        self.assertIsNotNone(question)
        assert question is not None
        self.assertEqual(question.answer, "A lookup structure.")
        self.assertEqual(question.tags, ["database", "performance"])
        self.assertEqual(question.status, "validated")
        self.assertIsNotNone(question.created_at)
        self.assertIsNotNone(question.updated_at)

    def test_get_question_returns_none_when_id_does_not_exist(self) -> None:
        self.assertIsNone(get_question(self.database_path, 42))
