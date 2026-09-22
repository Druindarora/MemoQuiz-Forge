"""MemoQuiz-compatible JSON exports."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from memoquiz_forge.database import connect


class QuestionExportError(Exception):
    """Raised when an export cannot safely be created."""


@dataclass(frozen=True)
class ExportResult:
    """Outcome of an export attempt."""

    exported: int
    output_path: Path | None


def export_questions(
    database_path: Path,
    output_path: Path,
    *,
    count: int,
    domain: str | None = None,
    concept: str | None = None,
    level: str | None = None,
    force: bool = False,
) -> ExportResult:
    """Write selected questions to JSON, then mark them as exported."""
    if count <= 0:
        raise ValueError("Count must be a strictly positive integer.")

    selected_questions = _select_questions(
        database_path, count=count, domain=domain, concept=concept, level=level
    )
    if not selected_questions:
        return ExportResult(exported=0, output_path=None)
    if output_path.exists() and not force:
        raise QuestionExportError(
            f"Destination file already exists: {output_path}. Use --force to overwrite it."
        )

    payload = [
        {"question": question, "answer": answer}
        for _, question, answer in selected_questions
    ]
    _write_payload(output_path, payload)
    _mark_exported(database_path, [question_id for question_id, _, _ in selected_questions])
    return ExportResult(exported=len(selected_questions), output_path=output_path)


def _select_questions(
    database_path: Path,
    *,
    count: int,
    domain: str | None,
    concept: str | None,
    level: str | None,
) -> list[tuple[int, str, str]]:
    filters = ["status = 'validated'", "exported = 0"]
    parameters: list[str | int] = []
    for column, value in (("domain", domain), ("concept", concept), ("level", level)):
        if value is not None:
            filters.append(f"{column} = ?")
            parameters.append(value)
    parameters.append(count)

    query = (
        "SELECT id, question, answer FROM questions "
        f"WHERE {' AND '.join(filters)} ORDER BY id LIMIT ?"
    )
    with closing(connect(database_path)) as connection:
        return connection.execute(query, parameters).fetchall()


def _write_payload(output_path: Path, payload: list[dict[str, str]]) -> None:
    """Write a human-readable UTF-8 MemoQuiz payload."""
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")


def _mark_exported(database_path: Path, question_ids: list[int]) -> None:
    """Mark exactly the questions included in the completed file."""
    placeholders = ", ".join("?" for _ in question_ids)
    with closing(connect(database_path)) as connection, connection:
        connection.execute(
            f"""
            UPDATE questions
            SET exported = 1,
                exported_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id IN ({placeholders})
            """,
            question_ids,
        )
