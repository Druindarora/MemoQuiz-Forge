"""Command-line interface for MemoQuiz Forge."""

from __future__ import annotations

import argparse

from memoquiz_forge.database import DEFAULT_DATABASE_PATH, initialize_database
from memoquiz_forge.questions import ExactDuplicateError, add_question


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memoquiz-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create the local SQLite database.")
    add_parser = subparsers.add_parser("add", help="Add a draft question.")
    add_parser.add_argument("--question", required=True, help="Question text.")
    add_parser.add_argument("--answer", required=True, help="Answer text.")
    add_parser.add_argument("--domain", help="Technical domain.")
    add_parser.add_argument("--concept", help="Specific concept.")
    add_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Question level."
    )
    add_parser.add_argument("--tag", dest="tags", action="append", default=[], help="Tag.")
    return parser


def main() -> None:
    """Run the command-line application."""
    args = build_parser().parse_args()

    if args.command == "init":
        database_path = initialize_database(DEFAULT_DATABASE_PATH)
        print(f"Database initialized: {database_path}")
    elif args.command == "add":
        try:
            added_question = add_question(
                DEFAULT_DATABASE_PATH,
                question=args.question,
                answer=args.answer,
                domain=args.domain,
                concept=args.concept,
                level=args.level,
                tags=args.tags,
            )
        except (ExactDuplicateError, ValueError) as error:
            raise SystemExit(f"Unable to add question: {error}") from error

        print(f"Question added as draft: #{added_question.id}")
        if added_question.has_question_conflict:
            print("Warning: a question with similar text already exists.")
