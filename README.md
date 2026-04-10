# atomic-fact

Extract atomic facts from text documents using LLMs.

An "atomic fact" is a single, specific, non-trivial statement of fact — the kind you'd highlight during an investigation. General knowledge is excluded; what remains are claims involving people, places, dates, and events.

## Setup

```bash
uv sync
export OPENAI_API_KEY='sk-...'
```

## Usage

```bash
# Print JSON to stdout
uv run python main.py document.txt

# Pretty-print
uv run python main.py document.txt --pretty

# Write to file
uv run python main.py document.txt --output results.json

# Use a different model
uv run python main.py document.txt --model gpt-4o-mini
```

## Output Format

```json
{
  "facts": [
    {
      "fact": "Congressman Wayne met with the president on October 4, 1968.",
      "quote": "Congressman Wayne met with the president on October 4, 1968.",
      "entities": ["Congressman Wayne", "the president"],
      "dates": ["1968-10-04"],
      "confidence": "high"
    }
  ]
}
```

Each fact includes:
- `fact` — standalone factual statement
- `quote` — verbatim source text
- `entities` — detected named entities
- `dates` — dates in ISO 8601 format where possible
- `confidence` — high, medium, or low

## Development

```bash
uv run pytest           # run tests
uv run ruff check .     # lint
uv run ruff format .    # format
```
