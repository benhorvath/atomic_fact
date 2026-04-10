# Tech Stack

- Language: Python >= 3.11
- Package manager: uv
- Project config: pyproject.toml
- Virtual environment: .venv (managed by uv)

## Key Dependencies

- `openai` — OpenAI API client for LLM calls
- `pydantic` — Data models and JSON schema for atomic fact output
- `click` — CLI framework for argument parsing and commands
- `langchain-text-splitters` — Paragraph/sentence-aware text chunking (RecursiveCharacterTextSplitter)

## Dev Dependencies

- `pytest` — Testing
- `ruff` — Linting and formatting

## Common Commands

```bash
uv sync                        # Install/sync all dependencies
uv add <pkg>                   # Add a runtime dependency
uv add --dev <pkg>             # Add a dev dependency
uv run main.py <file>          # Run the CLI on a text file
uv run pytest                  # Run tests
uv run ruff check .            # Lint
uv run ruff format .           # Format
```

## Environment Variables

- `OPENAI_API_KEY` — Required. OpenAI API key for LLM access.
