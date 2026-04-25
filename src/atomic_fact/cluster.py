"""Cluster facts by topic using sentence embeddings + HDBSCAN.

Embeds each fact, clusters by topic, identifies anomalous facts that
are far from any cluster centroid. Large clusters are recursively
sub-clustered for finer granularity.

Usage:
    uv run python -m atomic_fact.cluster input.json -o clusters.json
    uv run python -m atomic_fact.cluster input.json --epsilon 0.25
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN


MIN_CLUSTER_SIZE = 3
MAX_CLUSTER_SIZE = 30


def _load_facts(data: dict) -> list[dict]:
    """Extract facts from either single-doc or multi-doc JSON."""
    facts: list[dict] = []
    if "documents" in data:
        for doc in data["documents"]:
            for fact in doc["facts"]:
                facts.append({"text": fact["fact"], "source": doc["source"]})
    elif "facts" in data:
        for fact in data["facts"]:
            facts.append({"text": fact["fact"], "source": "(single document)"})
    return facts


def _cluster(embeddings: np.ndarray, epsilon: float) -> np.ndarray:
    """Run HDBSCAN with recursive sub-clustering of large clusters."""
    clusterer = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=2, metric="euclidean")
    labels = clusterer.fit_predict(embeddings)

    n_initial = len(set(labels)) - (1 if -1 in labels else 0)
    click.echo(f"Initial pass: {n_initial} clusters, {(labels == -1).sum()} noise", err=True)

    final_labels = labels.copy()
    next_label = max(labels) + 1 if len(labels) > 0 else 0

    for label in range(n_initial):
        indices = np.where(labels == label)[0]
        if len(indices) <= MAX_CLUSTER_SIZE:
            continue
        click.echo(f"  Re-clustering cluster {label} ({len(indices)} facts, epsilon={epsilon})...", err=True)
        sub = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=2,
                       metric="euclidean", cluster_selection_epsilon=epsilon)
        sub_labels = sub.fit_predict(embeddings[indices])
        n_sub = len(set(sub_labels)) - (1 if -1 in sub_labels else 0)
        click.echo(f"    -> {n_sub} sub-clusters, {(sub_labels == -1).sum()} noise", err=True)
        for i, sl in enumerate(sub_labels):
            if sl == -1:
                final_labels[indices[i]] = -1
            else:
                final_labels[indices[i]] = next_label + sl
        next_label += n_sub

    return final_labels


def _build_results(facts: list[dict], embeddings: np.ndarray, labels: np.ndarray) -> dict:
    """Build structured JSON output from clustering results."""
    clusters: dict[int, list[int]] = {}
    for i, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(i)

    centroids: dict[int, np.ndarray] = {}
    for label, indices in clusters.items():
        if label == -1:
            continue
        centroids[label] = embeddings[indices].mean(axis=0)

    cluster_list = []
    for label in sorted(
        [l for l in clusters if l != -1],
        key=lambda l: len(clusters[l]),
        reverse=True,
    ):
        indices = clusters[label]
        centroid = centroids[label]
        dists = [float(np.linalg.norm(embeddings[i] - centroid)) for i in indices]
        representative_idx = indices[int(np.argmin(dists))]

        members = []
        for i, d in sorted(zip(indices, dists), key=lambda x: x[1]):
            members.append({
                "fact": facts[i]["text"],
                "source": facts[i]["source"],
                "distance_to_centroid": round(d, 4),
            })

        cluster_list.append({
            "cluster_id": int(label),
            "size": len(indices),
            "representative": facts[representative_idx]["text"],
            "facts": members,
        })

    anomalies = []
    if centroids:
        for i in range(len(facts)):
            min_dist = float(min(
                np.linalg.norm(embeddings[i] - c) for c in centroids.values()
            ))
            anomalies.append({
                "fact": facts[i]["text"],
                "source": facts[i]["source"],
                "min_distance_to_centroid": round(min_dist, 4),
                "cluster": int(labels[i]),
            })
        anomalies.sort(key=lambda x: x["min_distance_to_centroid"], reverse=True)

    noise_list = []
    if -1 in clusters:
        for i in clusters[-1]:
            noise_list.append({"fact": facts[i]["text"], "source": facts[i]["source"]})

    return {
        "summary": {
            "total_facts": len(facts),
            "num_clusters": len(cluster_list),
            "num_noise": len(noise_list),
        },
        "clusters": cluster_list,
        "anomalies": anomalies[:20],
        "noise": noise_list,
    }


@click.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="Write JSON output to file. Prints to stdout if omitted.")
@click.option("--epsilon", type=float, default=0.3, show_default=True,
              help="HDBSCAN cluster_selection_epsilon for sub-clustering. Lower = more clusters.")
def main(json_file: str, output: str | None, epsilon: float) -> None:
    """Cluster atomic facts by topic using sentence embeddings + HDBSCAN."""
    json_path = Path(json_file)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    facts = _load_facts(data)
    click.echo(f"Loaded {len(facts)} facts", err=True)

    if len(facts) < MIN_CLUSTER_SIZE:
        click.echo("Not enough facts to cluster.", err=True)
        sys.exit(1)

    click.echo("Loading embedding model...", err=True)
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    click.echo("Encoding facts...", err=True)
    embeddings = model.encode([f["text"] for f in facts], normalize_embeddings=True)

    labels = _cluster(embeddings, epsilon)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = (labels == -1).sum()
    click.echo(f"Final: {n_clusters} clusters, {n_noise} noise", err=True)

    results = _build_results(facts, embeddings, labels)
    json_str = json.dumps(results, indent=2, ensure_ascii=False)

    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        click.echo(f"Wrote {output}", err=True)
    else:
        click.echo(json_str)


if __name__ == "__main__":
    main()
