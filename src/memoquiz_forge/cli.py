"""Command-line interface for MemoQuiz Forge."""

from __future__ import annotations

import argparse
from pathlib import Path

from memoquiz_forge.database import DEFAULT_DATABASE_PATH, initialize_database
from memoquiz_forge.exporter import QuestionExportError, export_questions
from memoquiz_forge.importer import QuestionImportError, import_questions
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
    validate_draft_questions,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memoquiz-forge",
        description="Outil local de préparation et d'export de questions pour MemoQuiz.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Crée la base SQLite locale.")
    add_parser = subparsers.add_parser("add", help="Ajoute une question en brouillon.")
    add_parser.add_argument("--question", required=True, help="Texte de la question.")
    add_parser.add_argument("--answer", required=True, help="Texte de la réponse.")
    add_parser.add_argument("--domain", help="Domaine technique, par exemple angular ou sql.")
    add_parser.add_argument("--concept", help="Concept précis, par exemple indexes.")
    add_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Niveau de difficulté."
    )
    add_parser.add_argument("--tag", dest="tags", action="append", default=[], help="Tag, répétable.")
    edit_parser = subparsers.add_parser("edit", help="Modifie une question existante.")
    edit_parser.add_argument("id", type=int, help="Identifiant numérique de la question.")
    edit_parser.add_argument("--question", help="Nouveau texte de la question.")
    edit_parser.add_argument("--answer", help="Nouveau texte de la réponse.")
    edit_parser.add_argument("--domain", help="Nouveau domaine technique.")
    edit_parser.add_argument("--concept", help="Nouveau concept précis.")
    edit_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Nouveau niveau de difficulté."
    )
    edit_parser.add_argument(
        "--tag", dest="tags", action="append", help="Tag de remplacement, répétable."
    )
    list_parser = subparsers.add_parser("list", help="Affiche une liste concise des questions.")
    list_parser.add_argument("--status", choices=("draft", "validated", "rejected"), help="Statut à afficher.")
    list_parser.add_argument("--domain", help="Domaine à afficher.")
    list_parser.add_argument("--concept", help="Concept à afficher.")
    list_parser.add_argument("--level", choices=("basic", "intermediate", "advanced"), help="Niveau à afficher.")
    list_parser.add_argument("--unexported", action="store_true", help="Uniquement les questions jamais exportées.")
    show_parser = subparsers.add_parser("show", help="Affiche le détail d'une question.")
    show_parser.add_argument("id", type=int, help="Identifiant numérique de la question.")
    validate_parser = subparsers.add_parser("validate", help="Valide une question complète.")
    validate_parser.add_argument("id", type=int, help="Identifiant numérique de la question.")
    validate_all_parser = subparsers.add_parser(
        "validate-all", help="Valide les brouillons complets."
    )
    validate_all_parser.add_argument("--domain", help="Limiter au domaine indiqué.")
    validate_all_parser.add_argument("--concept", help="Limiter au concept indiqué.")
    validate_all_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Limiter au niveau indiqué."
    )
    reject_parser = subparsers.add_parser("reject", help="Rejette une question sans la supprimer.")
    reject_parser.add_argument("id", type=int, help="Identifiant numérique de la question.")
    import_parser = subparsers.add_parser("import", help="Importe des questions depuis un fichier JSON.")
    import_parser.add_argument("file", type=Path, help="Chemin du fichier JSON à importer.")
    export_parser = subparsers.add_parser("export", help="Exporte des questions validées vers MemoQuiz.")
    export_parser.add_argument("file", type=Path, help="Chemin du fichier JSON à créer.")
    export_parser.add_argument(
        "--count", required=True, type=int, help="Nombre maximal à exporter (entier strictement positif)."
    )
    export_parser.add_argument("--domain", help="Limiter au domaine indiqué.")
    export_parser.add_argument("--concept", help="Limiter au concept indiqué.")
    export_parser.add_argument(
        "--level", choices=("basic", "intermediate", "advanced"), help="Limiter au niveau indiqué."
    )
    export_parser.add_argument("--force", action="store_true", help="Autorise l'écrasement d'un fichier existant.")
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
    elif args.command == "validate-all":
        result = validate_draft_questions(
            DEFAULT_DATABASE_PATH,
            domain=args.domain,
            concept=args.concept,
            level=args.level,
        )
        if result.selected == 0:
            print("No draft questions found.")
            return
        print("Bulk validation complete:")
        print(f"- {result.validated} validated")
        print(f"- {len(result.incomplete)} incomplete skipped")
        if result.incomplete:
            print("Incomplete:")
            for incomplete_question in result.incomplete:
                print(f"- #{incomplete_question.id}: {incomplete_question.problem}")
    elif args.command == "import":
        try:
            result = import_questions(DEFAULT_DATABASE_PATH, args.file)
        except QuestionImportError as error:
            raise SystemExit(f"Unable to import questions: {error}") from error
        print("Import complete:")
        print(f"- {result.imported} imported")
        print(f"- {result.skipped_duplicates} exact duplicates skipped")
        print(f"- {result.question_conflicts} question conflicts")
    elif args.command == "export":
        try:
            result = export_questions(
                DEFAULT_DATABASE_PATH,
                args.file,
                count=args.count,
                domain=args.domain,
                concept=args.concept,
                level=args.level,
                force=args.force,
            )
        except (QuestionExportError, ValueError, OSError) as error:
            raise SystemExit(f"Unable to export questions: {error}") from error
        if result.exported == 0:
            print("No questions available for export.")
            return
        print("Export complete:")
        print(f"- {result.exported} questions exported")
        print(f"- file: {result.output_path}")
