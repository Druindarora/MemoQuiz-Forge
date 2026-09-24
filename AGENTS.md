# MemoQuiz Forge agent notes

## Run locally

- Requires Python 3.11+ and uses only the standard library at runtime. Set up with `python3 -m venv .venv && source .venv/bin/activate && python -m pip install --editable .`.
- Run the CLI through the installed `memoquiz-forge` script (or `PYTHONPATH=src python -m memoquiz_forge`). Its default SQLite path is relative to the current directory: `data/memoquiz-forge.db`.
- Initialize a working database before using commands: `memoquiz-forge init`. Local `data/*.db` files are intentionally ignored by Git.
- Run the full suite with `PYTHONPATH=src python -W error::ResourceWarning -m unittest discover -v`. Run a focused test with `PYTHONPATH=src python -m unittest tests.test_exporter.ExportQuestionsTests.test_exports_one_question_with_memoquiz_format_and_unicode -v`.

## Structure and invariants

- Keep argument parsing and terminal output in `src/memoquiz_forge/cli.py`; place question operations in `questions.py` and batch file workflows in `importer.py` / `exporter.py`.
- `database.py` owns the SQLite schema and `data/` creation. The schema uses `CREATE TABLE IF NOT EXISTS`; changing it does not migrate existing local databases.
- Reuse `fingerprints.py` for all duplicate decisions. Its normalization intentionally preserves technical syntax symbols; do not broaden punctuation removal without adding regression tests.
- Import validates the entire JSON structure before writing and inserts the batch transactionally. Export writes the MemoQuiz JSON before marking selected rows `exported`; preserve this ordering.
- Export payloads must contain only `question` and `answer`, selected deterministically by ascending ID from validated, unexported rows.
