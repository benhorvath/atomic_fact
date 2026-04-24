"""Build an interactive entity co-occurrence network from atomic-fact output.

Entities that appear together in the same fact are connected. Edge weights
are the pointwise mutual information of co-occurrence (PMI). Interactive
output written to an HTML file.

Usage:
    uv run python scripts/entity_network.py input.json -o network.html
    uv run python scripts/entity_network.py input.json --min-pmi 1.0
    uv run python scripts/entity_network.py input.json --entity "Harry Reid"
"""

from __future__ import annotations

import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path

import click
import networkx as nx


def _load_facts(data: dict) -> list[dict]:
    facts = []
    if "documents" in data:
        for doc in data["documents"]:
            for fact in doc["facts"]:
                facts.append(fact)
    elif "facts" in data:
        facts = data["facts"]
    return facts


def _get_entities(fact: dict) -> list[tuple[str, str]]:
    entities = []
    for p in fact.get("people", []):
        entities.append((p, "person"))
    for o in fact.get("organizations", []):
        entities.append((o, "org"))
    for pl in fact.get("places", []):
        entities.append((pl, "place"))
    return entities


def _build_graph(facts: list[dict], min_pmi: float) -> nx.Graph:
    n_facts = len(facts)
    entity_count: Counter[str] = Counter()
    pair_count: Counter[tuple[str, str]] = Counter()
    entity_type: dict[str, str] = {}

    for fact in facts:
        entities = _get_entities(fact)
        names = set()
        for name, etype in entities:
            entity_count[name] += 1
            entity_type[name] = etype
            names.add(name)
        for a, b in combinations(sorted(names), 2):
            pair_count[(a, b)] += 1

    G = nx.Graph()
    for name, count in entity_count.items():
        G.add_node(name, count=count, entity_type=entity_type[name])

    for (a, b), co_count in pair_count.items():
        if co_count < 2:
            continue
        p_ab = co_count / n_facts
        p_a = entity_count[a] / n_facts
        p_b = entity_count[b] / n_facts
        pmi = math.log2(p_ab / (p_a * p_b))
        if pmi >= min_pmi:
            G.add_edge(a, b, weight=round(pmi, 3), co_count=co_count)

    isolates = list(nx.isolates(G))
    G.remove_nodes_from(isolates)
    return G


TYPE_COLORS = {"person": "#bc8cff", "org": "#58a6ff", "place": "#39d2c0"}


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")


def _render_html(G: nx.Graph, output: str, focus_entity: str | None) -> None:
    if focus_entity:
        if focus_entity not in G:
            click.echo(f"Entity '{focus_entity}' not found.", err=True)
            click.echo(f"Available: {', '.join(sorted(G.nodes())[:20])}...", err=True)
            return
        neighbors = set(G.neighbors(focus_entity)) | {focus_entity}
        G = G.subgraph(neighbors).copy()

    # Build vis.js data
    nodes_js = []
    for node in G.nodes():
        d = G.nodes[node]
        count = d.get("count", 1)
        etype = d.get("entity_type", "person")
        color = TYPE_COLORS.get(etype, "#8b949e")
        size = max(12, min(50, count * 3))
        label = _escape(node)
        title = _escape(f"{node} ({etype}, {count} mentions)")
        nodes_js.append(
            f'{{id:"{label}",label:"{label}",size:{size},'
            f'color:"{color}",title:"{title}",font:{{color:"#e6edf3",size:11}}}}'
        )

    edges_js = []
    for a, b, d in G.edges(data=True):
        pmi = d.get("weight", 0)
        co = d.get("co_count", 0)
        width = max(1, min(8, pmi))
        title = _escape(f"PMI: {pmi:.2f}, co-occurrences: {co}")
        edges_js.append(
            f'{{from:"{_escape(a)}",to:"{_escape(b)}",value:{width},'
            f'title:"{title}",color:{{color:"#30363d",highlight:"#58a6ff"}}}}'
        )

    nodes_str = ",\n      ".join(nodes_js)
    edges_str = ",\n      ".join(edges_js)

    html = f"""\
<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Entity Network</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body {{ margin:0; background:#0d1117; font-family:sans-serif; color:#e6edf3 }}
  #network {{ width:100%; height:100vh }}
  #info {{ position:fixed; top:12px; left:12px; background:#161b22; border:1px solid #30363d;
    border-radius:8px; padding:12px 16px; font-size:13px; color:#8b949e; z-index:10 }}
  #info strong {{ color:#e6edf3 }}
  .legend {{ display:flex; gap:12px; margin-top:8px }}
  .legend span {{ display:flex; align-items:center; gap:4px; font-size:11px }}
  .legend .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block }}
</style>
</head><body>
<div id="info">
  <strong>Entity Network</strong> — {len(G.nodes())} nodes, {len(G.edges())} edges<br>
  <div class="legend">
    <span><span class="dot" style="background:#bc8cff"></span>People</span>
    <span><span class="dot" style="background:#58a6ff"></span>Orgs</span>
    <span><span class="dot" style="background:#39d2c0"></span>Places</span>
  </div>
</div>
<div id="network"></div>
<script>
  var nodes = new vis.DataSet([
      {nodes_str}
  ]);
  var edges = new vis.DataSet([
      {edges_str}
  ]);
  var container = document.getElementById("network");
  var data = {{ nodes: nodes, edges: edges }};
  var options = {{
    physics: {{
      barnesHut: {{ gravitationalConstant: -3000, centralGravity: 0.3, springLength: 150, damping: 0.09 }},
      stabilization: {{ iterations: 200 }}
    }},
    interaction: {{ hover: true, tooltipDelay: 100, navigationButtons: true }},
    edges: {{ smooth: {{ type: "continuous" }} }}
  }};
  new vis.Network(container, data, options);
</script>
</body></html>"""

    Path(output).write_text(html, encoding="utf-8")
    click.echo(f"Wrote {output} ({len(G.nodes())} nodes, {len(G.edges())} edges)", err=True)


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default="entity_network.html",
              show_default=True, help="Output HTML file.")
@click.option("--min-pmi", type=float, default=0.5, show_default=True,
              help="Minimum PMI to include an edge.")
@click.option("--entity", default=None,
              help="Focus on a single entity and its neighbors.")
def main(input_file: str, output: str, min_pmi: float, entity: str | None) -> None:
    """Build an interactive entity co-occurrence network."""
    data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    facts = _load_facts(data)
    click.echo(f"Loaded {len(facts)} facts", err=True)

    G = _build_graph(facts, min_pmi)
    click.echo(f"Graph: {len(G.nodes())} nodes, {len(G.edges())} edges (min_pmi={min_pmi})", err=True)

    _render_html(G, output, entity)


if __name__ == "__main__":
    main()
