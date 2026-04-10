# Development Plan — atomic-fact

## Phase 1: Project Scaffolding

Set up the source layout and install dependencies.

- [x] Create `src/atomic_fact/` package with `__init__.py`
- [x] Create placeholder modules: `cli.py`, `extractor.py`, `models.py`, `reader.py`
- [x] Create `tests/` directory with `__init__.py`
- [x] Install dependencies: `openai`, `pydantic`, `click`
- [x] Install dev dependencies: `pytest`, `ruff`
- [x] Update `pyproject.toml` with project metadata and entry point
- [x] Wire `main.py` to delegate to `cli.py`

## Phase 2: Data Models

Define the output schema using Pydantic.

- [x] Define `AtomicFact` model in `models.py`:
  - `fact: str` — standalone factual statement
  - `quote: str` — verbatim source quote
  - `entities: list[str]` — detected named entities
  - `dates: list[str]` — detected dates in ISO 8601 format
  - `confidence: Confidence` — high / medium / low (enum)
- [x] Define `ExtractionResult` wrapper model containing a list of `AtomicFact` objects

## Phase 3: Text Reader

Build the input handling module.

- [x] Implement `read_text(path: str) -> str` in `reader.py`
- [x] Validate file exists and is a `.txt` file
- [x] Handle encoding (default UTF-8)
- [x] Raise clear errors for missing or unreadable files

## Phase 4: LLM Extractor

Core extraction logic using the OpenAI API.

- [x] Build the extraction prompt that instructs the LLM to:
  - Identify atomic facts from an investigative viewpoint
  - Exclude general knowledge
  - Return structured JSON matching the `AtomicFact` schema
  - Include verbatim quotes, entities, dates, and confidence
- [x] Implement `extract(text: str, model: str) -> ExtractionResult` in `extractor.py`
- [x] Use OpenAI's structured output / JSON mode where possible
- [x] Handle API errors gracefully (auth, rate limits, timeouts)
- [x] Support configurable model name (default: `gpt-4o`)

## Phase 5: CLI

Wire everything together with Click.

- [x] Implement CLI in `cli.py` with the following interface:
  ```
  atomic-fact <file> [--model MODEL] [--output FILE] [--pretty]
  ```
  - `<file>` — path to input text file (required)
  - `--model` — OpenAI model override (default: `gpt-4o`)
  - `--output` — write JSON to file instead of stdout
  - `--pretty` — pretty-print JSON output
- [x] Read `OPENAI_API_KEY` from environment, error if missing
- [x] Print results to stdout as JSON (or write to file with `--output`)

## Phase 6: Testing

- [x] Unit tests for `models.py` (serialization, validation)
- [x] Unit tests for `reader.py` (happy path, missing file, bad encoding)
- [x] Integration test for `extractor.py` using a mocked OpenAI response
- [x] CLI smoke test using Click's test runner

## Phase 7: Polish

- [ ] Add a useful `--help` description to the CLI
- [ ] Update `README.md` with usage instructions and example output
- [ ] Ensure `ruff` passes cleanly
- [ ] Tag v0.1.0
