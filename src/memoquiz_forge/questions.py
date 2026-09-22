"""Question creation and duplicate checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from memoquiz_forge.database import connect
from memoquiz_forge.fingerprints import content_fingerprint, question_fingerprint


ALLOWED_LEVELS = {"basic", "intermediate", "advanced"}


class ExactDuplicateError(Exception):
    """Raised when a question with identical content already exists."""


@dataclass(frozen=True)
class AddedQuestion:
    """Outcome of adding a question."""

    id: int
    has_question_conflict: bool


def add_question(
    database_path: Path,
    *,
    question: str,
    answer: str,
    domain: str | None = None,
    concept: str | None = None,
    level: str | None = None,
    tags: list[str] | None = None,
) -> AddedQuestion:
    """Create a draft question, rejecting exact content duplicates."""
    if not question.strip():
        raise ValueError("Question must not be empty.")
    if not answer.strip():
        raise ValueError("Answer must not be empty.")
    if level is not None and level not in ALLOWED_LEVELS:
        allowed_levels = ", ".join(sorted(ALLOWED_LEVELS))
        raise ValueError(f"Invalid level {level!r}. Allowed values: {allowed_levels}.")

    question_hash = question_fingerprint(question)
    content_hash = content_fingerprint(question, answer)

    with connect(database_path) as connection:
        exact_duplicate = connection.execute(
            "SELECT id FROM questions WHERE content_fingerprint = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
        if exact_duplicate is not None:
            raise ExactDuplicateError(
                f"Exact duplicate of existing question #{exact_duplicate[0]}."
            )

        question_conflict = connection.execute(
            "SELECT 1 FROM questions WHERE question_fingerprint = ? LIMIT 1",
            (question_hash,),
        ).fetchone() is not None

        cursor = connection.execute(
            """
            INSERT INTO questions (
                question, answer, domain, concept, level, tags,
                question_fingerprint, content_fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question,
                answer,
                domain,
                concept,
                level,
                json.dumps(tags or [], ensure_ascii=False),
                question_hash,
                content_hash,
            ),
        )

    return AddedQuestion(id=cursor.lastrowid, has_question_conflict=question_conflict)
