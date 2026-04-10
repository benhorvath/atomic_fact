"""Core extraction logic — LLM interaction.

Development notes:
    - We use OpenAI's structured output (beta parse API) to get the LLM to
      return JSON that matches our Pydantic schema directly. This avoids
      manual JSON parsing and gives us validation for free.
    - The system prompt is kept separate from the user content so the LLM
      has clear instruction vs. input boundaries.
    - API errors are caught and re-raised as click.UsageError for clean CLI
      output. We distinguish auth errors (bad key) from transient ones
      (rate limits, timeouts) in the messaging.
    - The default model is gpt-4o but is configurable via the `model`
      parameter, which flows in from the CLI --model flag.
    - Long documents are automatically chunked (paragraph/sentence-aware
      with overlap) and each chunk is sent as a separate API call. Results
      are merged and deduplicated by quote to avoid double-counting facts
      that appear in the overlap region.
"""

from __future__ import annotations

import os

import click
import openai

from atomic_fact.chunker import chunk_text
from atomic_fact.models import ExtractionResult

SYSTEM_PROMPT = """\
You are an expert fact extractor. Your job is to read a text document and \
identify every "atomic fact" — a single, specific, non-trivial statement of \
fact that would be relevant from an investigative or detective viewpoint.

Rules:
- Each fact must be explicitly stated or strongly implied in the text.
- Each fact must be specific: who, what, when, where.
- Exclude general knowledge (e.g., "water is H2O").
- Each fact must be atomic — one fact per entry, not compound statements.
- For each fact, provide:
  - fact: a clear standalone statement of the fact.
  - quote: the verbatim passage from the source text that supports it.
  - entities: any proper nouns / named entities (people, places, orgs, etc.).
  - dates: any dates mentioned, standardized to ISO 8601 where possible \
(e.g., "1968-10-04"). If only a year or month is known, use partial ISO 8601 \
(e.g., "1968", "1968-10"). If the date is too vague, include it as-is.
  - confidence: "high" if the fact is clearly and explicitly stated, "medium" \
if it requires minor inference, "low" if it is only weakly implied.

Return ALL atomic facts you can find. Do not summarize or editorialize.\
"""


DEFAULT_MODEL = "gpt-4o"


def extract(text: str, model: str = DEFAULT_MODEL) -> ExtractionResult:
    """Extract atomic facts from the given text using the OpenAI API.

    Long documents are automatically chunked and each chunk is processed
    separately. Results are merged and deduplicated.

    Args:
        text: The full text content to analyze.
        model: The OpenAI model to use.

    Returns:
        An ExtractionResult containing the extracted atomic facts.

    Raises:
        click.UsageError: On API authentication, rate-limit, or other errors.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise click.UsageError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it with: export OPENAI_API_KEY='sk-...'"
        )

    client = openai.OpenAI(api_key=api_key)
    chunks = chunk_text(text)
    all_facts = []
    seen_quotes: set[str] = set()

    for chunk in chunks:
        result = _extract_chunk(client, chunk, model)
        for fact in result.facts:
            # Deduplicate by normalized quote to handle overlap regions
            normalized = fact.quote.strip().lower()
            if normalized not in seen_quotes:
                seen_quotes.add(normalized)
                all_facts.append(fact)

    return ExtractionResult(facts=all_facts)


def _extract_chunk(client: openai.OpenAI, text: str, model: str) -> ExtractionResult:
    """Send a single chunk to the OpenAI API and return parsed results."""
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format=ExtractionResult,
        )
    except openai.AuthenticationError:
        raise click.UsageError(
            "OpenAI API authentication failed. Check your OPENAI_API_KEY."
        )
    except openai.RateLimitError:
        raise click.UsageError(
            "OpenAI API rate limit exceeded. Wait a moment and try again."
        )
    except openai.APITimeoutError:
        raise click.UsageError(
            "OpenAI API request timed out. Try again or use a faster model."
        )
    except openai.APIError as exc:
        raise click.UsageError(f"OpenAI API error: {exc}") from exc

    result = completion.choices[0].message.parsed

    if result is None:
        raise click.UsageError(
            "The model returned an empty or unparseable response. "
            "Try again or use a different model."
        )

    return result
