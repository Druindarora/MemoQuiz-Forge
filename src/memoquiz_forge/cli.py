"""Command-line interface for MemoQuiz Forge."""

from __future__ import annotations

import argparse

from memoquiz_forge.database import DEFAULT_DATABASE_PATH, initialize_database
from memoquiz_forge.questions import (
    ExactDuplicateError,
    QuestionNotFoundError,
    QuestionValidationError,
    add_question,
    edit_question,
    get_question,
    list_questions,
    reject_question,
    validate_question,
)


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
    edit_parser = subparsers.add_parser("edit", help="Edit an existing question.")
    edit_parser.add_argument("id", type=int, help="Question ID.")
    edit_parser.add_argument("--question", help="Question text.")
    edit_parser.add_argument("--answer", help="Answer text.")
    edit_parser.add_argument("--domain", help="Technical domain.")
    edit_parser.add_argument("--concept", help="Specific concept.")
    edit_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Question level."
    )
    edit_parser.add_argument("--tag", dest="tags", action="append", help="Replacement tag.")
    list_parser = subparsers.add_parser("list", help="List questions.")
    list_parser.add_argument("--status", choices=("draft", "validated", "rejected"))
    list_parser.add_argument("--domain")
    list_parser.add_argument("--concept")
    list_parser.add_argument("--level", choices=("basic", "intermediate", "advanced"))
    list_parser.add_argument("--unexported", action="store_true")
    show_parser = subparsers.add_parser("show", help="Show a question in detail.")
    show_parser.add_argument("id", type=int, help="Question ID.")
    validate_parser = subparsers.add_parser("validate", help="Validate a complete question.")
    validate_parser.add_argument("id", type=int, help="Question ID.")
    reject_parser = subparsers.add_parser("reject", help="Reject a question.")
    reject_parser.add_argument("id", type=int, help="Question ID.")
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
    elif args.command == "list":
        questions = list_questions(
            DEFAULT_DATABASE_PATH,
            status=args.status,
            domain=args.domain,
            concept=args.concept,
            level=args.level,
            unexported=args.unexported,
        )
        if not questions:
            print("No questions found.")
            return
        for question in questions:
            print(
                f"#{question.id} | {question.question} | "
                f"domain={question.domain or '-'} | concept={question.concept or '-'} | "
                f"level={question.level or '-'} | status={question.status} | "
                f"exported={'yes' if question.exported else 'no'}"
            )
    elif args.command == "edit":
        try:
            edited_question = edit_question(
                DEFAULT_DATABASE_PATH,
                args.id,
                question=args.question,
                answer=args.answer,
                domain=args.domain,
                concept=args.concept,
                level=args.level,
                tags=args.tags,
            )
        except (ExactDuplicateError, QuestionNotFoundError, ValueError) as error:
            raise SystemExit(f"Unable to edit question: {error}") from error

        if not edited_question.modified:
            print(f"No changes made to question #{edited_question.id}.")
        else:
            print(f"Question updated: #{edited_question.id}")
        if edited_question.has_question_conflict:
            print("Warning: a question with similar text already exists.")
    elif args.command == "show":
        question = get_question(DEFAULT_DATABASE_PATH, args.id)
        if question is None:
            raise SystemExit(f"Question not found: #{args.id}")
        print(f"id: {question.id}")
        print(f"question: {question.question}")
        print(f"answer: {question.answer}")
        print(f"domain: {question.domain or '-'}")
        print(f"concept: {question.concept or '-'}")
        print(f"level: {question.level or '-'}")
        print(f"tags: {', '.join(question.tags) if question.tags else '-'}")
        print(f"status: {question.status}")
        print(f"exported: {'yes' if question.exported else 'no'}")
        print(f"created_at: {question.created_at}")
        print(f"updated_at: {question.updated_at}")
        print(f"exported_at: {question.exported_at or '-'}")
    elif args.command == "validate":
        try:
            status_change = validate_question(DEFAULT_DATABASE_PATH, args.id)
        except (QuestionNotFoundError, QuestionValidationError) as error:
            raise SystemExit(f"Unable to validate question #{args.id}: {error}") from error
        if status_change.changed:
            print(f"Question validated: #{status_change.id}")
        else:
            print(f"Question #{status_change.id} is already validated; no changes made.")
    elif args.command == "reject":
        try:
            status_change = reject_question(DEFAULT_DATABASE_PATH, args.id)
        except QuestionNotFoundError as error:
            raise SystemExit(f"Unable to reject question #{args.id}: {error}") from error
        if status_change.changed:
            print(f"Question rejected: #{status_change.id}")
        else:
            print(f"Question #{status_change.id} is already rejected; no changes made.")
