"""JSON batch import for MemoQuiz Forge."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from memoquiz_forge.database import connect
from memoquiz_forge.fingerprints import content_fingerprint, question_fingerprint
from memoquiz_forge.questions import ALLOWED_LEVELS


ALLOWED_FIELDS = {"question", "answer", "domain", "concept", "level", "tags"}
ALLOWED_IMPORT_STATUSES = {"draft", "validated"}
FORBIDDEN_FIELDS = {
    "id",
    "status",
    "exported",
    "created_at",
    "updated_at",
    "exported_at",
    "question_fingerprint",
    "content_fingerprint",
}


class QuestionImportError(Exception):
    """Raised when an import source cannot be read or validated."""


@dataclass(frozen=True)
class ImportItem:
    """A validated question ready for insertion."""

    question: str
    answer: str
    domain: str | None
    concept: str | None
    level: str | None
    tags: list[str]
    question_fingerprint: str
    content_fingerprint: str


@dataclass(frozen=True)
class ImportResult:
    """Counts produced by a completed import."""

    imported: int
    skipped_duplicates: int
    question_conflicts: int


def import_questions(database_path: Path, input_path: Path) -> ImportResult:
    """Validate and import a JSON batch in one database transaction."""
    items = _read_and_validate(input_path)
    return _import_items(database_path, items, status="draft")


def import_questions_from_json(
    database_path: Path, payload_text: str, *, status: str = "draft"
) -> ImportResult:
    """Validate and import a JSON payload without creating an input file."""
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as error:
        raise QuestionImportError(f"Invalid JSON: {error.msg}") from error

    return import_questions_payload(database_path, payload, status=status)


def import_questions_payload(
    database_path: Path, payload: object, *, status: str = "draft"
) -> ImportResult:
    """Validate and import an already decoded JSON payload."""
    items = _validate_payload(payload)
    return _import_items(database_path, items, status=status)


def _import_items(
    database_path: Path, items: list[ImportItem], *, status: str
) -> ImportResult:
    if status not in ALLOWED_IMPORT_STATUSES:
        raise ValueError(f"Invalid import status: {status!r}.")
    if status == "validated":
        _validate_items_for_validated_import(items)

    imported = 0
    skipped_duplicates = 0
    question_conflicts = 0
    with closing(connect(database_path)) as connection, connection:
        content_fingerprints = {
            row[0] for row in connection.execute("SELECT content_fingerprint FROM questions")
        }
        question_fingerprints = {
            row[0] for row in connection.execute("SELECT question_fingerprint FROM questions")
        }
        for item in items:
            if item.content_fingerprint in content_fingerprints:
                skipped_duplicates += 1
                continue
            if item.question_fingerprint in question_fingerprints:
                question_conflicts += 1

            _insert_question(connection, item, status)
            imported += 1
            content_fingerprints.add(item.content_fingerprint)
            question_fingerprints.add(item.question_fingerprint)

    return ImportResult(imported, skipped_duplicates, question_conflicts)


def _read_and_validate(input_path: Path) -> list[ImportItem]:
    try:
        with input_path.open(encoding="utf-8") as input_file:
            payload = json.load(input_file)
    except FileNotFoundError as error:
        raise QuestionImportError(f"File not found: {input_path}") from error
    except OSError as error:
        raise QuestionImportError(f"Unable to read file: {input_path}") from error
    except json.JSONDecodeError as error:
        raise QuestionImportError(f"Invalid JSON: {error.msg}") from error

    return _validate_payload(payload)


def _validate_payload(payload: object) -> list[ImportItem]:
    if not isinstance(payload, list):
        raise QuestionImportError("Invalid JSON root: expected an array.")
    return [_validate_item(item, index) for index, item in enumerate(payload, start=1)]


def _validate_item(item: object, index: int) -> ImportItem:
    if not isinstance(item, dict):
        _invalid_item(index, "must be an object.")

    unknown_fields = set(item) - ALLOWED_FIELDS
    forbidden_fields = unknown_fields & FORBIDDEN_FIELDS
    if forbidden_fields:
        _invalid_item(index, f'"{sorted(forbidden_fields)[0]}" is managed by Forge.')
    if unknown_fields:
        _invalid_item(index, f'unknown field "{sorted(unknown_fields)[0]}".')

    question = _required_string(item, index, "question")
    answer = _required_string(item, index, "answer")
    domain = _optional_string(item, index, "domain")
    concept = _optional_string(item, index, "concept")
    level = _optional_string(item, index, "level")
    if level is not None and level not in ALLOWED_LEVELS:
        _invalid_item(index, '"level" must be basic, intermediate, or advanced.')

    tags_value = item.get("tags", [])
    if not isinstance(tags_value, list) or not all(
        isinstance(tag, str) for tag in tags_value
    ):
        _invalid_item(index, '"tags" must be an array of strings.')

    return ImportItem(
        question=question,
        answer=answer,
        domain=domain,
        concept=concept,
        level=level,
        tags=tags_value,
        question_fingerprint=question_fingerprint(question),
        content_fingerprint=content_fingerprint(question, answer),
    )


def _required_string(item: dict[str, object], index: int, field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        _invalid_item(index, f'"{field}" must be a non-empty string.')
    return value


def _optional_string(item: dict[str, object], index: int, field: str) -> str | None:
    if field not in item:
        return None
    value = item[field]
    if not isinstance(value, str):
        _invalid_item(index, f'"{field}" must be a string.')
    return value


def _invalid_item(index: int, message: str) -> None:
    raise QuestionImportError(f"Invalid item #{index}: {message}")


def _validate_items_for_validated_import(items: list[ImportItem]) -> None:
    """Ensure an approved import can enter the validated workflow state."""
    for index, item in enumerate(items, start=1):
        missing_fields = [
            field
            for field, value in (
                ("domain", item.domain),
                ("concept", item.concept),
                ("level", item.level),
            )
            if value is None or not value.strip()
        ]
        if missing_fields:
            _invalid_item(
                index,
                f"cannot import as validated: missing {', '.join(missing_fields)}.",
            )


def _insert_question(
    connection: sqlite3.Connection, item: ImportItem, status: str = "draft"
) -> None:
    """Insert a previously validated item with the requested workflow status."""
    connection.execute(
        """
        INSERT INTO questions (
            question, answer, domain, concept, level, tags, status,
            question_fingerprint, content_fingerprint
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.question,
            item.answer,
            item.domain,
            item.concept,
            item.level,
            json.dumps(item.tags, ensure_ascii=False),
            status,
            item.question_fingerprint,
            item.content_fingerprint,
        ),
    )
