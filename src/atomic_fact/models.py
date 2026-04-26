"""Data models for atomic fact extraction output.

Development notes:
    - Confidence is a str Enum rather than a plain Literal so it serializes
      cleanly to JSON ("high" not "Confidence.HIGH") while still being
      constrainable in Pydantic validation. It also gives us a single source
      of truth if we ever add or rename levels.
    - Field descriptions on every attribute serve double duty: they document
      the schema for developers AND they feed into Pydantic's
      .model_json_schema(), which we pass to the OpenAI API as structured
      output guidance. Clear descriptions improve LLM compliance with the
      expected format.
    - entities and dates use default_factory=list so they're optional in
      practice (the LLM may not find any) but always present in the output
      as empty lists, keeping the JSON shape consistent for consumers.
    - dates are kept as list[str] rather than list[datetime] because the
      source text may contain partial or ambiguous dates ("October 1968",
      "the early 1970s") that don't parse to a full datetime. We ask the
      LLM to standardize to ISO 8601 where possible, but accept freeform
      strings as a fallback.
    - ExtractionResult wraps the list so the top-level JSON is always an
      object ({"facts": [...]}) rather than a bare array. This is friendlier
      for OpenAI structured output and leaves room to add metadata later
      (e.g., token usage, model name, source file).
    - from __future__ import annotations is used for PEP 604 union syntax
      (str | None) compatibility on Python 3.11.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """Confidence level for an extracted atomic fact."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AtomicFact(BaseModel):
    """A single atomic fact extracted from a text document."""

    fact: str = Field(description="Standalone factual statement")
    quote: str = Field(description="Verbatim quote from the source text")
    people: list[str] = Field(
        default_factory=list,
        description="People mentioned (e.g., 'George Washington', 'Britney Spears')",
    )
    organizations: list[str] = Field(
        default_factory=list,
        description="Organizations mentioned (e.g., 'NASA', 'CIA', 'DIA')",
    )
    places: list[str] = Field(
        default_factory=list,
        description="Places mentioned (e.g., 'Kentucky', 'Newport')",
    )
    dates: list[str] = Field(
        default_factory=list,
        description="Detected dates in ISO 8601 format where possible",
    )
    confidence: Confidence = Field(
        description="Confidence level of the extraction",
    )
    idf_score: float | None = Field(
        default=None,
        description="Mean IDF score of the fact's tokens (computed post-extraction)",
    )
    entropy: float | None = Field(
        default=None,
        description="Shannon entropy of the fact's token distribution (computed post-extraction)",
    )


class ExtractionResult(BaseModel):
    """Wrapper for a list of extracted atomic facts."""

    facts: list[AtomicFact] = Field(default_factory=list)


class DocumentResult(BaseModel):
    """Extraction results for a single document within a collection."""

    source: str = Field(description="Source filename (e.g., 'memo_1968.txt')")
    facts: list[AtomicFact] = Field(default_factory=list)


class CollectionResult(BaseModel):
    """Wrapper for multi-document extraction results."""

    documents: list[DocumentResult] = Field(default_factory=list)
