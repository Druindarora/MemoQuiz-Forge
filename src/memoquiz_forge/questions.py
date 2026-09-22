"""Question creation and duplicate checks."""

from __future__ import annotations

import json
from contextlib import closing
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


@dataclass(frozen=True)
class EditedQuestion:
    """Outcome of editing a question."""

    id: int
    has_question_conflict: bool
    modified: bool


class QuestionNotFoundError(Exception):
    """Raised when an operation targets an unknown question ID."""


@dataclass(frozen=True)
class Question:
    """A question stored in the local database."""

    id: int
    question: str
    answer: str
    domain: str | None
    concept: str | None
    level: str | None
    tags: list[str]
    status: str
    exported: bool
    created_at: str
    updated_at: str
    exported_at: str | None


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

    with closing(connect(database_path)) as connection, connection:
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


def list_questions(
    database_path: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    concept: str | None = None,
    level: str | None = None,
    unexported: bool = False,
) -> list[Question]:
    """Return questions matching the provided filters, ordered by ID."""
    filters: list[str] = []
    parameters: list[str | int] = []
    for column, value in (
        ("status", status),
        ("domain", domain),
        ("concept", concept),
        ("level", level),
    ):
        if value is not None:
            filters.append(f"{column} = ?")
            parameters.append(value)
    if unexported:
        filters.append("exported = 0")

    where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
    query = f"SELECT * FROM questions{where_clause} ORDER BY id"

    with closing(connect(database_path)) as connection:
        connection.row_factory = _row_to_question
        return connection.execute(query, parameters).fetchall()


def get_question(database_path: Path, question_id: int) -> Question | None:
    """Return one question by ID, or None when it does not exist."""
    with closing(connect(database_path)) as connection:
        connection.row_factory = _row_to_question
        return connection.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()


def edit_question(
    database_path: Path,
    question_id: int,
    *,
    question: str | None = None,
    answer: str | None = None,
    domain: str | None = None,
    concept: str | None = None,
    level: str | None = None,
    tags: list[str] | None = None,
) -> EditedQuestion:
    """Update explicitly provided question fields and preserve all others."""
    if question is not None and not question.strip():
        raise ValueError("Question must not be empty.")
    if answer is not None and not answer.strip():
        raise ValueError("Answer must not be empty.")
    if level is not None and level not in ALLOWED_LEVELS:
        allowed_levels = ", ".join(sorted(ALLOWED_LEVELS))
        raise ValueError(f"Invalid level {level!r}. Allowed values: {allowed_levels}.")

    with closing(connect(database_path)) as connection, connection:
        connection.row_factory = _row_to_question
        existing = connection.execute(
            "SELECT * FROM questions WHERE id = ?", (question_id,)
        ).fetchone()
        connection.row_factory = None
        if existing is None:
            raise QuestionNotFoundError(f"Question not found: #{question_id}")

        new_question = question if question is not None else existing.question
        new_answer = answer if answer is not None else existing.answer
        new_domain = domain if domain is not None else existing.domain
        new_concept = concept if concept is not None else existing.concept
        new_level = level if level is not None else existing.level
        new_tags = tags if tags is not None else existing.tags
        content_changed = new_question != existing.question or new_answer != existing.answer
        changed = content_changed or any(
            (
                new_domain != existing.domain,
                new_concept != existing.concept,
                new_level != existing.level,
                new_tags != existing.tags,
            )
        )
        if not changed:
            return EditedQuestion(id=question_id, has_question_conflict=False, modified=False)

        new_question_hash = question_fingerprint(new_question)
        new_content_hash = content_fingerprint(new_question, new_answer)
        question_conflict = False
        if content_changed:
            exact_duplicate = connection.execute(
                """
                SELECT id FROM questions
                WHERE content_fingerprint = ? AND id != ?
                LIMIT 1
                """,
                (new_content_hash, question_id),
            ).fetchone()
            if exact_duplicate is not None:
                raise ExactDuplicateError(
                    f"Exact duplicate of existing question #{exact_duplicate[0]}."
                )
            question_conflict = connection.execute(
                """
                SELECT 1 FROM questions
                WHERE question_fingerprint = ? AND id != ?
                LIMIT 1
                """,
                (new_question_hash, question_id),
            ).fetchone() is not None

        connection.execute(
            """
            UPDATE questions
            SET question = ?, answer = ?, domain = ?, concept = ?, level = ?, tags = ?,
                question_fingerprint = ?, content_fingerprint = ?,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                new_question,
                new_answer,
                new_domain,
                new_concept,
                new_level,
                json.dumps(new_tags, ensure_ascii=False),
                new_question_hash,
                new_content_hash,
                question_id,
            ),
        )

    return EditedQuestion(
        id=question_id, has_question_conflict=question_conflict, modified=True
    )


def _row_to_question(cursor: object, row: tuple[object, ...]) -> Question:
    """Convert a SQLite result row into a Question."""
    columns = [column[0] for column in cursor.description]  # type: ignore[attr-defined]
    values = dict(zip(columns, row, strict=True))
    return Question(
        id=values["id"],  # type: ignore[arg-type]
        question=values["question"],  # type: ignore[arg-type]
        answer=values["answer"],  # type: ignore[arg-type]
        domain=values["domain"],  # type: ignore[arg-type]
        concept=values["concept"],  # type: ignore[arg-type]
        level=values["level"],  # type: ignore[arg-type]
        tags=json.loads(values["tags"]),  # type: ignore[arg-type]
        status=values["status"],  # type: ignore[arg-type]
        exported=bool(values["exported"]),
        created_at=values["created_at"],  # type: ignore[arg-type]
        updated_at=values["updated_at"],  # type: ignore[arg-type]
        exported_at=values["exported_at"],  # type: ignore[arg-type]
    )
