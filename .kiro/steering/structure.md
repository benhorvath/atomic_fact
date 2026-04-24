# Project Structure

```
atomic-fact/
├── .kiro/steering/       # AI steering rules and project context
├── .venv/                # Virtual environment (managed by uv, git-ignored)
├── main.py               # CLI entry point
├── pyproject.toml        # Project metadata and dependencies
├── .python-version       # Pinned Python version (3.11)
├── .gitignore
└── README.md
```

## Planned Layout

As the project grows, the intended structure is:

```
atomic-fact/
├── src/
│   └── atomic_fact/
│       ├── __init__.py
│       ├── chunker.py       # Paragraph/sentence-aware text chunking with overlap
│       ├── cli.py          # CLI argument parsing and entry point
│       ├── extractor.py    # Core extraction logic (LLM interaction)
│       ├── models.py       # Data models for atomic facts (output schema)
│       ├── reader.py       # Text file reading / input handling
│       └── viewer.py       # HTML report generation from JSON output
├── tests/
│   └── ...
├── main.py
├── pyproject.toml
└── ...
```

## Conventions

- Source code lives under `src/atomic_fact/`
- One module per responsibility (reading input, calling the LLM, defining output models)
- Tests mirror the source layout under `tests/`
- CLI entry point is `main.py`, which delegates to `src/atomic_fact/cli.py`
- `reader.py` handles both single-file and directory input (enumerating `.txt` files)
- `models.py` contains both `ExtractionResult` (single-doc) and `CollectionResult` (multi-doc) schemas
- `extractor.py` processes one document at a time; collection-level orchestration lives in `cli.py`
