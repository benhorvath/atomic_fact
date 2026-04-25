![atomic-fact banner](banner.png)

Extract atomic facts from text documents using an LLM.

An "atomic fact" is a single, specific, verifiable claim that an investigator would write down -- a concrete event, action, relationship, or dated occurrence involving identifiable people, organizations, or places. General knowledge, opinions, and vague descriptions are excluded.

Once the atomic facts are extracted, they can viewed in an HTML report, or clustered. There is also a tool to perform (manual) entity resolution.

### Output

```json
{
  "facts": [
    {
      "fact": "Tim Cook joined Apple as a senior vice president in 1998.",
      "quote": "I joined Apple as a senior vice president in 1998.",
      "people": ["Tim Cook"],
      "organizations": ["Apple"],
      "places": [],
      "dates": ["1998"],
      "confidence": "high",
      "idf_score": 2.14,
      "entropy": 2.58
    }
  ]
}
```


## Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/atomic-fact.git
cd atomic-fact

# Install dependencies (requires uv — https://docs.astral.sh/uv/)
uv sync

# Set your OpenAI API key
export OPENAI_API_KEY='sk-...'
```

All commands below use `uv run` to run within the project's virtual environment. If you prefer, you can activate the venv directly:

```bash
source .venv/bin/activate
atomic-fact extract --help    # works without uv run
```

For clustering and network analysis scripts, install the optional dependencies:

```bash
uv sync --extra cluster --extra network
```

## Workflow

The intended workflow is iterative:

1. **Extract** — Run your documents through the LLM to get raw atomic facts.
2. **View** — Open the HTML report to inspect entities, scores, and facts.
3. **Resolve** (optional) — Spot entity variants (e.g., "IBM" v. "International Business Machines"), edit an `aliases.toml` file, and re-run resolution. No LLM call needed.
4. **View again** — Rerun the `view` command to regenerate the HTML with "resolved" entities.
5. **Cluster** (optional) — Group facts by topic to find themes and anomalies.

```bash
# 1. Extract
uv run atomic-fact extract ./docs/ --output results.json

# 2. View
uv run atomic-fact view results.json -o report.html

# 3. Optional: Resolve entities (after editing aliases.toml)
uv run atomic-fact resolve results.json --aliases aliases.toml -o results.json

# 4. View again
uv run atomic-fact view results.json -o report.html

# 5. Optional: Cluster
uv run atomic-fact cluster results.json -o clusters.json
```

## Commands

### extract

Extract atomic facts from a single `.txt` file or a directory of `.txt` files.

```bash
uv run atomic-fact extract document.txt
uv run atomic-fact extract document.txt --output results.json
uv run atomic-fact extract document.txt --model gpt-5.4-mini

# Directory (collection mode)
uv run atomic-fact extract ./docs/ --output collection.json
uv run atomic-fact extract ./docs/ --resume              # skip already-cached documents
uv run atomic-fact extract ./docs/ --concurrency 4       # parallel processing
```

| Flag | Description |
|------|-------------|
| `--model TEXT` | OpenAI model to use (default: `gpt-5.4-mini`) |
| `--output PATH` | Write JSON to a file instead of stdout |
| `--resume` | Skip documents whose results are already cached |
| `--concurrency N` | Documents to process in parallel (default: 1) |
| `--verbose` | Enable debug-level logging |

### resolve

Apply entity aliases to an existing JSON output and recompute IDF/entropy scores. Only entity tags (people, organizations, places) are modified -- fact text and source quotes are not touched.

```bash
uv run atomic-fact resolve results.json --aliases aliases.toml -o resolved.json
uv run atomic-fact resolve results.json --aliases aliases.toml   # overwrite in place
```

| Flag | Description |
|------|-------------|
| `--aliases PATH` | (required) TOML file mapping entity variants to canonical forms |
| `-o, --output PATH` | Output JSON file. Defaults to overwriting the input |

Example `aliases.toml`:

```toml
[people]
"Senator Reid" = "Harry Reid"
"Bob Bigelow" = "Robert Bigelow"

[organizations]
"IBM" = "International Business Machines"
"CIA" = "Central Intelligence Agency"

[places]
"the capital" = "Washington DC"
"Washington, DC" = "Washington DC"
```

### view

Generate a self-contained HTML report with a sidebar for filtering by sort order, confidence, document, and entity.

```bash
uv run atomic-fact view results.json -o report.html
```

| Flag | Description |
|------|-------------|
| `-o, --output PATH` | Output HTML file. Defaults to `<input>.html` |

### cluster

Cluster facts by topic using sentence embeddings and HDBSCAN. Large clusters are recursively sub-clustered for finer granularity.

```bash
uv run atomic-fact cluster results.json -o clusters.json
uv run atomic-fact cluster results.json --epsilon 0.2 -o clusters.json
```

| Flag | Description |
|------|-------------|
| `-o, --output PATH` | Write JSON to file. Prints to stdout if omitted |
| `--epsilon FLOAT` | HDBSCAN epsilon for sub-clustering (default: 0.3). Lower = more clusters |

## How It Works

1. Input text is split into chunks (paragraph/sentence-aware with overlap).
2. A context preamble is auto-generated from the beginning of each document.
3. The first chunk is sent to the OpenAI API with the context preamble. Subsequent chunks receive the accumulated extracted facts as context, improving coreference resolution and reducing duplicates.
4. Results are merged and deduplicated by quote text.
5. IDF and entropy scores are computed across all facts (cross-document in collection mode).

In directory mode, each document is processed independently. Intermediate results are cached to `.atomic_fact_cache/` so interrupted runs can be resumed with `--resume`.

## Output Format

```json
{
  "facts": [
    {
      "fact": "Tim Cook joined Apple as a senior vice president in 1998.",
      "quote": "I joined Apple as a senior vice president in 1998.",
      "people": ["Tim Cook"],
      "organizations": ["Apple"],
      "places": [],
      "dates": ["1998"],
      "confidence": "high",
      "idf_score": 2.14,
      "entropy": 2.58
    }
  ]
}
```

Directory mode wraps results per document:

```json
{
  "documents": [
    { "source": "interview_cook.txt", "facts": [...] },
    { "source": "memo_reid.txt", "facts": [...] }
  ]
}
```

| Field | Description |
|-------|-------------|
| `fact` | Standalone factual statement with references resolved to proper nouns |
| `quote` | Verbatim source text |
| `people` | People mentioned |
| `organizations` | Organizations mentioned |
| `places` | Places mentioned |
| `dates` | Dates in ISO 8601 format where possible |
| `confidence` | `high`, `medium`, or `low` |
| `idf_score` | Mean IDF of content words (higher = more specific) |
| `entropy` | Shannon entropy of token distribution (higher = more diverse vocabulary) |

## Scripts

The `scripts/` directory contains an additional analysis script, albeit experimental. It uses the co-occurence of entities in an atomic fact to create an interactive network graph. Edge weight is based on pointwise mututal information (PMI):

```bash
# Interactive entity co-occurrence network (PMI-weighted)
uv run python scripts/entity_network.py results.json -o network.html
```

The `--entity` argument allows the user to filter the network graph:

```
uv run python scripts/entity_network.py results.json --entity "Robert Bigelow" -o bigelow.html
```

## Development

```bash
uv run pytest           # run tests
uv run ruff check .     # lint
uv run ruff format .    # format
```
