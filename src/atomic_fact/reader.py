"""Text file reading and input handling.

Development notes:
    - We restrict input to .txt files for now. The plan is to add other
      format modules (PDF, HTML, etc.) later, so this module stays focused
      on plain text only.
    - Encoding defaults to UTF-8 but is configurable, since real-world
      text files sometimes come in Latin-1 or other encodings.
    - Errors are raised as click.UsageError so they surface cleanly in
      the CLI with a non-zero exit code and no traceback.
"""

from __future__ import annotations

from pathlib import Path

import click


def read_text(path: str, encoding: str = "utf-8") -> str:
    """Read a plain text file and return its contents as a string.

    Args:
        path: Path to the text file.
        encoding: File encoding. Defaults to UTF-8.

    Returns:
        The full text content of the file.

    Raises:
        click.UsageError: If the file is missing, not a .txt file,
            or cannot be decoded.
    """
    filepath = Path(path)

    if not filepath.exists():
        raise click.UsageError(f"File not found: {filepath}")

    if filepath.suffix.lower() != ".txt":
        raise click.UsageError(
            f"Unsupported file type '{filepath.suffix}'. Only .txt files are supported."
        )

    try:
        return filepath.read_text(encoding=encoding)
    except UnicodeDecodeError as exc:
        raise click.UsageError(
            f"Could not decode '{filepath}' as {encoding}: {exc}"
        ) from exc
