"""Tests for database initialization."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from memoquiz_forge.database import initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialization_creates_parent_directory_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "nested" / "data" / "forge.db"

            result = initialize_database(database_path)

            self.assertEqual(result, database_path)
            self.assertTrue(database_path.is_file())

    def test_questions_schema_contains_expected_columns_and_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "forge.db"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(questions)")
                }
                indexes = {
                    row[1]
                    for row in connection.execute("PRAGMA index_list(questions)")
                }
                schema = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'questions'"
                ).fetchone()[0]

            self.assertEqual(
                columns,
                {
                    "id",
                    "question",
                    "answer",
                    "domain",
                    "concept",
                    "level",
                    "tags",
                    "status",
                    "exported",
                    "created_at",
                    "updated_at",
                    "exported_at",
                    "question_fingerprint",
                    "content_fingerprint",
                },
            )
            self.assertTrue(
                {
                    "idx_questions_status_exported",
                    "idx_questions_question_fingerprint",
                    "idx_questions_content_fingerprint",
                }.issubset(indexes)
            )
            self.assertIn("'basic', 'intermediate', 'advanced'", schema)
            self.assertIn("'draft', 'validated', 'rejected'", schema)

    def test_initialization_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "forge.db"

            initialize_database(database_path)
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                table_count = connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'questions'"
                ).fetchone()[0]

            self.assertEqual(table_count, 1)

    def test_draft_metadata_can_be_null_but_level_values_are_constrained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "forge.db"
            initialize_database(database_path)

            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO questions (
                        question, answer, domain, concept, level,
                        question_fingerprint, content_fingerprint
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("Question", "Answer", None, None, None, "question", "content"),
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO questions (
                            question, answer, domain, concept, level,
                            question_fingerprint, content_fingerprint
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            "Another question",
                            "Another answer",
                            None,
                            None,
                            "expert",
                            "another-question",
                            "another-content",
                        ),
                    )
