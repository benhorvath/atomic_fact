"""CLI entry point for atomic-fact.

Provides subcommands:
    atomic-fact extract  — extract atomic facts from text files
    atomic-fact resolve  — apply entity aliases and recompute scores
    atomic-fact view     — generate an HTML report from JSON output
    atomic-fact cluster  — cluster facts by topic using embeddings
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click

from atomic_fact.aliases import apply_aliases, load_aliases
from atomic_fact.extractor import async_extract, extract as run_extract
from atomic_fact.models import CollectionResult, DocumentResult
from atomic_fact.reader import read_directory, read_text
from atomic_fact.scoring import compute_entropy, compute_idf_scores

CACHE_DIR_NAME = ".atomic_fact_cache"
logger = logging.getLogger("atomic_fact")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("atomic_fact")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)


# -----------------------------------------------------------------------
# Top-level group
# -----------------------------------------------------------------------


@click.group()
@click.version_option(package_name="atomic-fact")
def main() -> None:
    """atomic-fact — extract atomic facts from text documents using LLMs."""


# -----------------------------------------------------------------------
# extract subcommand
# -----------------------------------------------------------------------


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--model", default="gpt-5.4-mini", show_default=True, help="OpenAI model to use."
)
@click.option(
    "--output",
    type=click.Path(),
    default=None,
    help="Write JSON output to a file instead of stdout.",
)
@click.option(
    "--resume",
    is_flag=True,
    help="In directory mode, skip documents whose results are already cached.",
)
@click.option(
    "--concurrency",
    default=1,
    show_default=True,
    type=int,
    help="Documents to process in parallel (directory mode).",
)
@click.option("--verbose", is_flag=True, help="Enable debug-level logging.")
def extract(
    path: str,
    model: str,
    output: str | None,
    resume: bool,
    concurrency: int,
    verbose: bool,
) -> None:
    """Extract atomic facts from a text file or directory of text files.

    PATH can be a single .txt file or a directory containing .txt files.
    Requires the OPENAI_API_KEY environment variable.
    """
    _setup_logging(verbose)

    if Path(path).is_dir():
        if concurrency > 1:
            asyncio.run(
                _process_directory_async(
                    path,
                    async_extract,
                    model,
                    output,
                    resume,
                    concurrency,
                )
            )
        else:
            _process_directory(path, run_extract, model, output, resume)
    else:
        _process_file(path, run_extract, model, output)


# -----------------------------------------------------------------------
# resolve subcommand
# -----------------------------------------------------------------------


@main.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "--aliases",
    type=click.Path(exists=True),
    required=True,
    help="TOML file mapping entity name variants to canonical forms.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output JSON file. Defaults to overwriting the input.",
)
def resolve(json_file: str, aliases: str, output: str | None) -> None:
    """Apply entity aliases to an existing JSON output and recompute scores.

    Reads a previously extracted JSON file, applies the alias mapping to
    entity tags (people, organizations, places), recomputes IDF and entropy
    scores, and writes the result.
    """
    from atomic_fact.viewer import _normalize_to_collection

    json_path = Path(json_file)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    alias_map = load_aliases(aliases)

    # Normalize, apply aliases, recompute scores
    collection = _normalize_to_collection(data)
    all_facts = [fact for doc in collection.documents for fact in doc.facts]
    apply_aliases(all_facts, alias_map)
    compute_idf_scores(all_facts)
    compute_entropy(all_facts)

    # Write back in original format
    if "documents" in data:
        json_str = collection.model_dump_json(indent=2)
    else:
        from atomic_fact.models import ExtractionResult

        json_str = ExtractionResult(facts=all_facts).model_dump_json(indent=2)

    out_path = Path(output) if output else json_path
    out_path.write_text(json_str, encoding="utf-8")
    click.echo(f"Resolved {len(all_facts)} facts -> {out_path}")


# -----------------------------------------------------------------------
# view subcommand
# -----------------------------------------------------------------------


@main.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "--title", default="atomic-fact report", help="Title to display in the HTML report."
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Output HTML file path. Defaults to <input>.html.",
)
def view(json_file: str, title: str, output: str | None) -> None:
    """Generate an HTML report from atomic-fact JSON output."""
    from atomic_fact.viewer import _normalize_to_collection, generate_html

    json_path = Path(json_file)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    collection = _normalize_to_collection(data)
    html = generate_html(collection, title=title)

    if output is None:
        output = str(json_path.with_suffix(".html"))

    total_facts = sum(len(d.facts) for d in collection.documents)
    Path(output).write_text(html, encoding="utf-8")
    click.echo(f"Wrote report to {output} ({total_facts} facts)")


# -----------------------------------------------------------------------
# cluster subcommand
# -----------------------------------------------------------------------


@main.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=None,
    help="Write JSON output to file. Prints to stdout if omitted.",
)
@click.option(
    "--epsilon",
    type=float,
    default=0.3,
    show_default=True,
    help="HDBSCAN epsilon for sub-clustering. Lower = more clusters.",
)
def cluster(json_file: str, output: str | None, epsilon: float) -> None:
    """Cluster atomic facts by topic using sentence embeddings."""
    from atomic_fact.cluster import main as cluster_main

    # Invoke the cluster module's click command directly via its context
    ctx = click.Context(cluster_main, info_name="cluster")
    ctx.invoke(cluster_main, json_file=json_file, output=output, epsilon=epsilon)


# -----------------------------------------------------------------------
# Internal helpers for extract
# -----------------------------------------------------------------------


def _process_file(path, extractor, model, output):
    """Process a single text file."""
    text = read_text(path)
    result = extractor(text, model=model)
    compute_idf_scores(result.facts)
    compute_entropy(result.facts)
    json_str = result.model_dump_json(indent=2)
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        click.echo(f"Wrote {len(result.facts)} facts to {output}")
    else:
        click.echo(json_str)


def _process_directory(path, extractor, model, output, resume):
    """Process all .txt files in a directory (sequential)."""
    files = read_directory(path)
    total = len(files)
    logger.info("Found %d .txt file(s) in %s", total, path)
    cache_dir = Path(path) / CACHE_DIR_NAME
    cache_dir.mkdir(exist_ok=True)
    documents: list[DocumentResult] = []
    cached_count = 0
    for i, (filename, text) in enumerate(files, 1):
        cache_file = cache_dir / f"{filename}.json"
        if resume and cache_file.exists():
            doc = DocumentResult(**json.loads(cache_file.read_text(encoding="utf-8")))
            documents.append(doc)
            cached_count += 1
            logger.info(
                "[%d/%d] %s (cached, %d facts)", i, total, filename, len(doc.facts)
            )
            continue
        logger.info("[%d/%d] %s", i, total, filename)
        result = extractor(text, model=model)
        doc = DocumentResult(source=filename, facts=result.facts)
        cache_file.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        documents.append(doc)
    _write_collection(documents, total, cached_count, output)


async def _process_directory_async(
    path, async_extractor, model, output, resume, concurrency
):
    """Process all .txt files in a directory (parallel with semaphore)."""
    files = read_directory(path)
    total = len(files)
    logger.info(
        "Found %d .txt file(s) in %s (concurrency=%d)", total, path, concurrency
    )
    cache_dir = Path(path) / CACHE_DIR_NAME
    cache_dir.mkdir(exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)

    async def process_one(idx, filename, text):
        cache_file = cache_dir / f"{filename}.json"
        if resume and cache_file.exists():
            doc = DocumentResult(**json.loads(cache_file.read_text(encoding="utf-8")))
            logger.info(
                "[%d/%d] %s (cached, %d facts)", idx, total, filename, len(doc.facts)
            )
            return idx, filename, doc
        async with semaphore:
            logger.info("[%d/%d] %s (processing)", idx, total, filename)
            result = await async_extractor(text, model=model)
            doc = DocumentResult(source=filename, facts=result.facts)
            cache_file.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
            logger.info(
                "[%d/%d] %s done (%d facts)", idx, total, filename, len(doc.facts)
            )
            return idx, filename, doc

    tasks = [process_one(i, fn, txt) for i, (fn, txt) in enumerate(files, 1)]
    completed = await asyncio.gather(*tasks)
    completed_sorted = sorted(completed, key=lambda x: x[0])
    documents = [doc for _, _, doc in completed_sorted]
    cached_count = sum(
        1
        for _, (fn, _) in enumerate(files, 1)
        if resume and (cache_dir / f"{fn}.json").exists()
    )
    _write_collection(documents, total, cached_count, output)


def _write_collection(documents, total, cached_count, output):
    """Assemble CollectionResult, compute scores, and write."""
    all_facts = [fact for doc in documents for fact in doc.facts]
    compute_idf_scores(all_facts)
    compute_entropy(all_facts)
    collection = CollectionResult(documents=documents)
    total_facts = sum(len(d.facts) for d in documents)
    json_str = collection.model_dump_json(indent=2)
    if cached_count:
        logger.info(
            "Resumed: %d cached, %d processed", cached_count, total - cached_count
        )
    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        logger.info(
            "Wrote %d facts from %d documents to %s", total_facts, total, output
        )
    else:
        click.echo(json_str)
