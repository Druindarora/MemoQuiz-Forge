"""Command-line interface for MemoQuiz Forge."""

from __future__ import annotations

import argparse

from memoquiz_forge.database import DEFAULT_DATABASE_PATH, initialize_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memoquiz-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create the local SQLite database.")
    return parser


def main() -> None:
    """Run the command-line application."""
    args = build_parser().parse_args()

    if args.command == "init":
        database_path = initialize_database(DEFAULT_DATABASE_PATH)
        print(f"Database initialized: {database_path}")
