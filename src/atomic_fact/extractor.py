"""Core extraction logic — LLM interaction.

Long documents are automatically chunked (paragraph/sentence-aware with
overlap) and each chunk is sent as a separate API call. The first chunk
receives an auto-generated context preamble; subsequent chunks receive
the accumulated extracted facts as context for coreference resolution
and deduplication.

TODO
----
- For really long documents, we may need to limit the number of previous facts
  that are sent to the LLM; e.g., only include the last 50 extracted facts.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

import click
import openai

from atomic_fact.chunker import chunk_text
from atomic_fact.models import ExtractionResult

logger = logging.getLogger("atomic_fact")

SYSTEM_PROMPT_FIRST = """\
You extract atomic facts from text for investigative analysis.

An atomic fact is a single, specific, verifiable claim that an investigator \
would write down — a concrete event, action, relationship, or dated occurrence \
involving identifiable people, organizations, or places.

INCLUDE a claim only if it passes ALL of these tests:
1. VERIFIABLE: Could be confirmed or denied with evidence.
2. SPECIFIC: Names WHO did what, to WHOM, WHEN, or WHERE.
3. ATTRIBUTED: The actors or sources are identified, not vague.
4. INVESTIGATIVELY SIGNIFICANT: Ask "so what?" — would an investigator \
note this? Mundane observations, general descriptions, and commonly known \
facts do not qualify.

EXCLUDE:
- Opinions, preferences, feelings, or attitudes
- General descriptions or characterizations of places, people, or things
- Vague or unattributed claims ("his credentials are disputed" — by whom?)
- General knowledge, rhetorical statements, or editorial commentary

COREFERENCE: Resolve all pronouns and vague references ("the team", "he", \
"they") to proper nouns using the provided context. Every fact must be \
understandable on its own.

For each fact, provide:
- fact: clear standalone statement
- quote: verbatim source passage
- people: people mentioned
- organizations: organizations mentioned
- places: places mentioned
- dates: ISO 8601 where possible
- confidence: "high" (explicit), "medium" (minor inference), "low" (weakly implied)

The user message includes a CONTEXT section and a DOCUMENT TEXT section. \
Use CONTEXT only for reference resolution. Extract facts ONLY from DOCUMENT TEXT.\
"""

SYSTEM_PROMPT_SUBSEQUENT = """\
You extract atomic facts from text for investigative analysis. You are \
processing one chunk of a larger document. Previous chunks have already been \
processed and their extracted facts are provided to you.

An atomic fact is a single, specific, verifiable claim that an investigator \
would write down — a concrete event, action, relationship, or dated occurrence \
involving identifiable people, organizations, or places.

INCLUDE a claim only if it passes ALL of these tests:
1. VERIFIABLE: Could be confirmed or denied with evidence.
2. SPECIFIC: Names WHO did what, to WHOM, WHEN, or WHERE.
3. ATTRIBUTED: The actors or sources are identified, not vague.
4. INVESTIGATIVELY SIGNIFICANT: Ask "so what?" — would an investigator \
note this?

EXCLUDE:
- Opinions, preferences, feelings, or attitudes
- General descriptions or characterizations
- Vague or unattributed claims
- General knowledge, rhetorical statements, or editorial commentary

COREFERENCE: The user message includes PREVIOUSLY EXTRACTED FACTS from \
earlier chunks. Use these to understand who and what is being discussed. \
Resolve all pronouns and vague references to proper nouns.

DO NOT DUPLICATE: The previously extracted facts have ALREADY been recorded. \
Do NOT re-extract, rephrase, or restate any fact that is substantially the \
same as one already listed. Only extract genuinely NEW facts.

For each NEW fact, provide:
- fact: clear standalone statement
- quote: verbatim source passage
- people, organizations, places, dates, confidence

Extract NEW facts ONLY from the DOCUMENT TEXT section.\
"""

CONTEXT_PROMPT = """\
Read the following text (which is the beginning of a longer document) and \
produce a brief context summary in 200 words or fewer. Identify:
- The key people mentioned and their roles or affiliations.
- The key organizations, programs, or groups mentioned.
- Any shorthand, abbreviations, or vague references used throughout.
- The general subject matter of the document.

Write the summary as plain prose. This summary will be provided as context \
to a fact extraction system processing later sections of the document.\
"""

DEFAULT_MODEL = "gpt-5.4-mini"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise click.UsageError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it with: export OPENAI_API_KEY='sk-...'"
        )
    return openai.OpenAI(api_key=api_key)


def _get_async_client() -> openai.AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise click.UsageError(
            "OPENAI_API_KEY environment variable is not set. "
            "Set it with: export OPENAI_API_KEY='sk-...'"
        )
    return openai.AsyncOpenAI(api_key=api_key)


def _dedup_facts(result, all_facts, seen_quotes):
    new_count = 0
    for fact in result.facts:
        normalized = fact.quote.strip().lower()
        if normalized not in seen_quotes:
            seen_quotes.add(normalized)
            all_facts.append(fact)
            new_count += 1
    return new_count


def _build_chunk_prompt(i, chunk, context, all_facts):
    if i == 1:
        system_prompt = SYSTEM_PROMPT_FIRST
        preamble = (
            "=== CONTEXT (for reference only — do NOT extract facts from this section) ===\n"
            f"{context}\n"
            "=== END CONTEXT ==="
        )
    else:
        system_prompt = SYSTEM_PROMPT_SUBSEQUENT
        facts_summary = "\n".join(f"- {f.fact}" for f in all_facts)
        preamble = (
            "=== PREVIOUSLY EXTRACTED FACTS (do NOT re-extract these) ===\n"
            f"{facts_summary}\n"
            "=== END PREVIOUSLY EXTRACTED FACTS ==="
        )
    user_message = (
        f"{preamble}\n\n"
        "=== DOCUMENT TEXT (extract NEW facts ONLY from this section) ===\n"
        f"{chunk}\n"
        "=== END DOCUMENT TEXT ==="
    )
    return system_prompt, user_message


# ---------------------------------------------------------------------------
# Sync extraction
# ---------------------------------------------------------------------------


def extract(text: str, model: str = DEFAULT_MODEL) -> ExtractionResult:
    """Extract atomic facts from text using the OpenAI API."""
    client = _get_client()

    logger.info("Generating context preamble from document...")
    context = _generate_context(client, text, model)
    logger.info("Context: %s...", context[:120])

    chunks = chunk_text(text)
    all_facts = []
    seen_quotes: set[str] = set()
    total = len(chunks)
    logger.info("Extracting facts using %s (%d chunks)...", model, total)

    for i, chunk in enumerate(chunks, 1):
        logger.debug("  Processing chunk %d/%d (%d chars)...", i, total, len(chunk))
        system_prompt, user_message = _build_chunk_prompt(i, chunk, context, all_facts)
        result = _extract_chunk(
            client, user_message, model, system_prompt=system_prompt
        )
        new_count = _dedup_facts(result, all_facts, seen_quotes)
        logger.debug(
            "  Found %d new facts (chunk returned %d total)",
            new_count,
            len(result.facts),
        )
        if i < total:
            time.sleep(5)

    logger.info("Done — %d atomic facts extracted.", len(all_facts))
    return ExtractionResult(facts=all_facts)


# ---------------------------------------------------------------------------
# Async extraction
# ---------------------------------------------------------------------------


async def async_extract(text: str, model: str = DEFAULT_MODEL) -> ExtractionResult:
    """Async version of extract()."""
    client = _get_async_client()

    logger.info("Generating context preamble from document...")
    context = await _async_generate_context(client, text, model)
    logger.info("Context: %s...", context[:120])

    chunks = chunk_text(text)
    all_facts = []
    seen_quotes: set[str] = set()
    total = len(chunks)
    logger.info("Extracting facts using %s (%d chunks)...", model, total)

    for i, chunk in enumerate(chunks, 1):
        logger.debug("  Processing chunk %d/%d (%d chars)...", i, total, len(chunk))
        system_prompt, user_message = _build_chunk_prompt(i, chunk, context, all_facts)
        result = await _async_extract_chunk(
            client, user_message, model, system_prompt=system_prompt
        )
        new_count = _dedup_facts(result, all_facts, seen_quotes)
        logger.debug(
            "  Found %d new facts (chunk returned %d total)",
            new_count,
            len(result.facts),
        )
        if i < total:
            await asyncio.sleep(5)

    logger.info("Done — %d atomic facts extracted.", len(all_facts))
    return ExtractionResult(facts=all_facts)


# ---------------------------------------------------------------------------
# Private helpers — sync
# ---------------------------------------------------------------------------


def _generate_context(client: openai.OpenAI, text: str, model: str) -> str:
    sample = text[:4000]
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CONTEXT_PROMPT},
                {"role": "user", "content": sample},
            ],
        )
    except openai.APIError as exc:
        raise click.UsageError(
            f"OpenAI API error during context generation: {exc}"
        ) from exc
    return completion.choices[0].message.content or ""


def _extract_chunk(
    client, text, model, system_prompt=SYSTEM_PROMPT_FIRST, max_retries=3
):
    for attempt in range(1, max_retries + 1):
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format=ExtractionResult,
            )
        except openai.AuthenticationError as exc:
            raise click.UsageError(f"OpenAI API authentication failed: {exc.message}")
        except (openai.RateLimitError, openai.APITimeoutError) as exc:
            if attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    "Retrying in %ds (attempt %d/%d): %s",
                    wait,
                    attempt,
                    max_retries,
                    exc,
                )
                time.sleep(wait)
                continue
            raise click.UsageError(
                f"OpenAI API error after {max_retries} retries: {exc}"
            )
        except openai.APIError as exc:
            if attempt < max_retries and exc.status_code and exc.status_code >= 500:
                wait = 2**attempt
                logger.warning(
                    "Retrying in %ds (attempt %d/%d): %s",
                    wait,
                    attempt,
                    max_retries,
                    exc,
                )
                time.sleep(wait)
                continue
            raise click.UsageError(f"OpenAI API error: {exc}") from exc
        else:
            break
    result = completion.choices[0].message.parsed
    if result is None:
        raise click.UsageError("The model returned an empty or unparseable response.")
    return result


# ---------------------------------------------------------------------------
# Private helpers — async
# ---------------------------------------------------------------------------


async def _async_generate_context(
    client: openai.AsyncOpenAI, text: str, model: str
) -> str:
    sample = text[:4000]
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CONTEXT_PROMPT},
                {"role": "user", "content": sample},
            ],
        )
    except openai.APIError as exc:
        raise click.UsageError(
            f"OpenAI API error during context generation: {exc}"
        ) from exc
    return completion.choices[0].message.content or ""


async def _async_extract_chunk(
    client, text, model, system_prompt=SYSTEM_PROMPT_FIRST, max_retries=3
):
    for attempt in range(1, max_retries + 1):
        try:
            completion = await client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format=ExtractionResult,
            )
        except openai.AuthenticationError as exc:
            raise click.UsageError(f"OpenAI API authentication failed: {exc.message}")
        except (openai.RateLimitError, openai.APITimeoutError) as exc:
            if attempt < max_retries:
                wait = 2**attempt
                logger.warning(
                    "Retrying in %ds (attempt %d/%d): %s",
                    wait,
                    attempt,
                    max_retries,
                    exc,
                )
                await asyncio.sleep(wait)
                continue
            raise click.UsageError(
                f"OpenAI API error after {max_retries} retries: {exc}"
            )
        except openai.APIError as exc:
            if attempt < max_retries and exc.status_code and exc.status_code >= 500:
                wait = 2**attempt
                logger.warning(
                    "Retrying in %ds (attempt %d/%d): %s",
                    wait,
                    attempt,
                    max_retries,
                    exc,
                )
                await asyncio.sleep(wait)
                continue
            raise click.UsageError(f"OpenAI API error: {exc}") from exc
        else:
            break
    result = completion.choices[0].message.parsed
    if result is None:
        raise click.UsageError("The model returned an empty or unparseable response.")
    return result
