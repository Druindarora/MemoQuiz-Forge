"""SQLite database setup for MemoQuiz Forge."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


DEFAULT_DATABASE_PATH = Path("data") / "memoquiz-forge.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    domain TEXT,
    concept TEXT,
    level TEXT CHECK (level IN ('basic', 'intermediate', 'advanced')),
    tags TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'validated', 'rejected')),
    exported INTEGER NOT NULL DEFAULT 0 CHECK (exported IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    exported_at TEXT,
    question_fingerprint TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_status_exported
    ON questions (status, exported);

CREATE INDEX IF NOT EXISTS idx_questions_question_fingerprint
    ON questions (question_fingerprint);

CREATE INDEX IF NOT EXISTS idx_questions_content_fingerprint
    ON questions (content_fingerprint);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection, creating the parent directory when needed."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path = DEFAULT_DATABASE_PATH) -> Path:
    """Create the database and its schema if they do not already exist."""
    with closing(connect(database_path)) as connection, connection:
        connection.executescript(SCHEMA)
    return database_path
