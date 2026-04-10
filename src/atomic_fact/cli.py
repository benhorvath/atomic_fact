"""CLI entry point for atomic-fact."""

from __future__ import annotations

from pathlib import Path

import click

from atomic_fact.extractor import extract
from atomic_fact.reader import read_text


@click.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--model",
    default="gpt-4o",
    show_default=True,
    help="OpenAI model to use.",
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.option(
    "--pretty",
    is_flag=True,
    help="Pretty-print the JSON output.",
)
def main(file: str, model: str, output: str | None, pretty: bool) -> None:
    """Extract atomic facts from a text document.

    Reads FILE (a .txt file), sends it to the OpenAI API, and outputs
    a JSON array of atomic facts with quotes, entities, dates, and
    confidence levels.

    Requires the OPENAI_API_KEY environment variable to be set.
    """
    text = read_text(file)
    result = extract(text, model=model)

    indent = 2 if pretty else None
    json_str = result.model_dump_json(indent=indent)

    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        click.echo(f"Wrote {len(result.facts)} facts to {output}")
    else:
        click.echo(json_str)
