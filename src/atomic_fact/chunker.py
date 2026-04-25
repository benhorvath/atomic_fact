"""Text chunking with paragraph/sentence-aware splitting and overlap.

Development notes:
    - Uses langchain's RecursiveCharacterTextSplitter which tries to split
      on paragraph breaks ("\\n\\n"), then newlines ("\\n"), then sentences
      (" "), then characters — in that order. This keeps atomic facts
      intact across chunk boundaries as much as possible.
    - Overlap is expressed as a fraction (default 0.10 = 10%) of
      max_chars, converted to an absolute character count for the splitter.
    - The chunk_text() interface stays the same so the rest of the
      codebase (extractor.py) doesn't need to change.
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

import click

DEFAULT_MAX_CHARS = 12_000
DEFAULT_OVERLAP = 0.10


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: float = DEFAULT_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks, respecting paragraph and sentence
    boundaries where possible.

    Args:
        text: The full text to chunk.
        max_chars: Maximum character count per chunk.
        overlap: Fraction of max_chars to overlap between consecutive chunks
                 (e.g., 0.10 for 10%).

    Returns:
        A list of text chunks.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    overlap_chars = int(max_chars * overlap)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True,
    )

    chunks = splitter.split_text(text)
    click.echo(
        f"Text is {len(text):,} chars — split into {len(chunks)} chunks "
        f"(max {max_chars:,} chars, {overlap:.0%} overlap)",
        err=True,
    )
    return chunks
