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

- [x] Add a useful `--help` description to the CLI
- [x] Update `README.md` with usage instructions and example output
- [x] Ensure `ruff` passes cleanly
- [x] Tag v0.1.0

## Phase 8: Collection Mode (Multi-Document Support)

Accept a directory of `.txt` files and process each document independently, producing a combined output with per-document provenance.

### 8.1 Models (`models.py`)

- [x] Add `DocumentResult` model: `source: str` (filename) + `facts: list[AtomicFact]`
- [x] Add `CollectionResult` model: `documents: list[DocumentResult]`
- [x] Existing `ExtractionResult` stays unchanged (single-doc mode)

### 8.2 Reader (`reader.py`)

- [x] Add `read_directory(path: str) -> list[tuple[str, str]]` — returns `(filename, text)` pairs for all `.txt` files in the directory
- [x] Validate the path is a directory and contains at least one `.txt` file
- [x] Raise clear errors for empty directories or non-directory paths

### 8.3 CLI (`cli.py`)

- [x] Detect whether the `FILE` argument is a file or a directory
- [x] Single file → existing behavior (`ExtractionResult`)
- [x] Directory → iterate over files from `read_directory`, call `extract` / `extract_v2` per document, assemble `CollectionResult`
- [x] Output `CollectionResult` JSON when in directory mode
- [x] Progress reporting: show which document is being processed (e.g., `[2/5] memo_1968.txt`)

### 8.4 Extractor (`extractor.py`)

- [x] No changes needed — `extract()` and `extract_v2()` already process a single document's text. Collection-level orchestration stays in `cli.py`.

### 8.5 Tests

- [x] Unit tests for `read_directory` (happy path, empty dir, no `.txt` files, nested dirs ignored)
- [x] Unit tests for `DocumentResult` / `CollectionResult` serialization
- [x] CLI integration test: pass a temp directory with multiple `.txt` files, verify JSON output shape matches `CollectionResult`
- [x] CLI integration test: single-file mode still produces `ExtractionResult` (backward compat)

### Design decisions

- Each document is processed independently: its own context preamble, chunking, and deduplication. No cross-document context sharing.
- `extractor.py` stays single-document focused. The loop over documents lives in `cli.py` to keep the extractor simple and testable.
- Directory mode only looks at top-level `.txt` files (no recursive descent) to keep behavior predictable.
- The `--context` flag applies to all documents when in directory mode (or is auto-generated per document if omitted).


## Possible extensions

* Input formats. PDF and HTML ingestion were already on the roadmap. A reader plugin system where each format gets its own module (reader_pdf.py, reader_html.py) that converts to plain text before hitting the existing pipeline. Minimal changes to the core.

* Fact deduplication across documents. If you're processing multiple documents about the same topic, the same facts will show up repeatedly. A cross-document dedup step — maybe embedding-based similarity rather than exact quote matching — would clean that up.

* API-level batching to save costs. Instead of sending 1000 batches synchronously, submit as a batch job. 

* Include start or observation date, and end date.

* Entity resolution and linking. Right now entities are just strings. Linking "Bob Lazar", "Lazar", and "he" to a canonical entity ID would make the output much more useful for downstream analysis. Could be a separate post-processing module.

* Export formats. Beyond JSON — CSV/TSV for spreadsheet analysis, a knowledge graph format (like triples: subject-predicate-object), or even a simple SQLite database for querying.
  * Could potentially include the HTML interface as an "output"

* Confidence calibration. Right now confidence is the LLM's self-assessment, which isn't very reliable. You could cross-reference: if the same fact appears in multiple chunks or multiple documents, bump its confidence. If it only appears once with weak language, lower it.

* A web UI. A simple Flask or Streamlit frontend where you drag in a document and browse the extracted facts interactively, filter by entity or date, etc.
  * Jinja templating -- create a `ReportRenderer` class that accepts a template path and a result object.

### Scoring for relevance or novelty or information density

CONCLUSION: Keep the second-pass filter, apply IDF on the document only -- works really well!

* Rather than filtering out overly-general factoids, define a scoring rubric and have the second LLM pass return scores. Could score from 1-5, and then combine in an overall index; possibly also include a sentence containing the LLM's reasoning.
  * Potential axes:
    * Specificity -- Level of detail or precision
    * Information density -- Rewards facts that encode multiple "constraints"
    * Verifiability -- Contains numbers, dates, named entities
    * Novelty -- Contains new information
  * LLM may be better at ranking these than assigning a score (could we then map the ranks to a score?)

* Non-LLM scores:
  * Named entity count -- just count the list of entities
  * Numeric density -- percent of numbers/percentages/dates/etc..
  * IDF-based token rarity -- `mean(idf(token) for token in fact)`. High specificity facts correspond to higher IDF weight
    * THIS SEEMS TO WORK WELL -- calculated entirely on the document itself! With a general "corpus" like the Wikipedia article, it still has interesting results, but not quite specificity.
  * Raw length -- too long not atomic, too short can't contain much interesting information
  * Dependency complexity -- Counting tree depth or clause count, where more structure implies more information
    * Rewards lists more than anything
  * Redundancy penalization -- Cluster facts using embeddings, then `novelty_score = 1 - max_similarity_to_previous_facts`
  * Entropy-based -- Treat a fact as a distribution of tokens, where high entropy implies more information, and low entropy implies a more generic factoid
  * Small local LLM to score perplexity (?)

Measuring surprise:

* `surprisal(x) = -log P(x)` where high surprisal has low `P(x)`, and a common will have a high `P(x)`
* For a factoid (sentence), can approximate with a language model:

$$surprisal(sentence) = - \sum^{T}_{t=1} log P(w_t | w_{<t})$$

which is just the negative log-likelihood (NLL) of the sentence.

* Related concept: perplexity: $perplexity = e^{\frac{1}{T} NLL}$. Can use as local model like GPT-2 ot othjer local LM, with `transformers` library and `AutoTokenizer` and `AutoModelForCausalLM`.
  - Can also use logits to find which parts of the sentence carry the most information: `logits = outputs.logits; probs = torch.softmax(logits, dim=-1)`

* Conditional surprisal -- use $P(fact | document)$ instead of just $P(fact)$ -- "how surprising is this fact given the rest of the document?"

* N-gam langauge models to get $P(w_t |  w_{t-1}, w{t-2})$; use KenLM or SRILM
* Take average IDF of tokens in a sentence to ghet a crude surprisal
* Embedding distance: Get the embedding of the factoid, compare to document/corpus centroid. Then `surprisal = 1 - cosine_similarity(fact_embedding, corpus_mean)`. Outlier facts will be more surprising. Example Python code:

```{python}
import numpy as np
from openai import OpenAI

client = OpenAI()

def get_embeddings(texts):
    res = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return np.array([e.embedding for e in res.data])

embeddings = get_embeddings(df["fact"].tolist())
centroid = embeddings.mean(axis=0)

cosine_sim = embeddings @ centroid / (
    np.linalg.norm(embeddings, axis=1) * np.linalg.norm(centroid)
)

df["semantic_surprise"] = 1 - cosine_sim
```

Note that  raw LLM will increase with sentence length, so it may be worothj correcting with average per token or normalized scores. Also, a fact may be surprising in general, but obvious within a domain, so it is best to use domain-specific training data or domain-specific LM.

References:

* "Claim extraction for fact-checking: Data, mdoels, and automated metrics"
* "Fact in fragments: Deconstructing complex claims via LLM-based atomic fact extraction and verifiation"
* "FEVEROUS: Fact extraction and verification over unstructured and structured information" -- Trying to detect "check-worthy claims"
* "Information extraction from scientific articles: A survey" -- "key insights extraction", "salient sentence detection"
* "An empirical study on information extraction using large langauge models"
