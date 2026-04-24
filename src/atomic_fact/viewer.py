"""Generate an HTML viewer from atomic-fact JSON output.

Usage:
    uv run python -m atomic_fact.viewer results.json -o report.html
    uv run python -m atomic_fact.viewer results.json  # writes to results.html
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click

from atomic_fact.models import AtomicFact, CollectionResult, DocumentResult, ExtractionResult


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _normalize_to_collection(data: dict) -> CollectionResult:
    """Normalize any JSON input to a CollectionResult."""
    if "documents" in data:
        return CollectionResult(**data)
    return CollectionResult(
        documents=[DocumentResult(source="(single document)", facts=ExtractionResult(**data).facts)]
    )


def generate_html(collection: CollectionResult) -> str:
    """Generate a self-contained HTML report from a CollectionResult."""
    all_facts: list[tuple[str, AtomicFact]] = []
    for doc in collection.documents:
        for fact in doc.facts:
            all_facts.append((doc.source, fact))

    multi_doc = len(collection.documents) > 1
    total_facts = len(all_facts)
    entity_counts: Counter[tuple[str, str]] = Counter()
    confidence_counts: Counter[str] = Counter()

    for _source, fact in all_facts:
        for p in fact.people:
            entity_counts[(p, "person")] += 1
        for o in fact.organizations:
            entity_counts[(o, "org")] += 1
        for pl in fact.places:
            entity_counts[(pl, "place")] += 1
        for d in fact.dates:
            entity_counts[(d, "date")] += 1
        confidence_counts[fact.confidence.value] += 1

    unique_entities = len(entity_counts)
    high = confidence_counts.get("high", 0)
    medium = confidence_counts.get("medium", 0)
    low = confidence_counts.get("low", 0)

    # Top 20 entity bubbles for the main content area
    all_entity_items = entity_counts.most_common()
    entity_tags = ""
    for idx_e, ((name, etype), count) in enumerate(all_entity_items):
        if idx_e >= 20:
            break
        entity_tags += (
            f'<span class="entity-tag {etype}" data-entity="{_escape(name)}" '
            f'onclick="toggleEntityFilter(this)">{_escape(name)} '
            f'<span class="entity-count">\u00d7{count}</span></span>\n'
        )

    # Sidebar entity list (ALL entities, searchable, scrollable)
    sidebar_entities = ""
    for (name, etype), count in all_entity_items:
        sidebar_entities += (
            f'<div class="sidebar-entity-item {etype}" data-entity="{_escape(name)}" '
            f'onclick="toggleEntityFilter(this)">'
            f'<span class="sidebar-entity-name">{_escape(name)}</span>'
            f'<span class="sidebar-entity-count">\u00d7{count}</span></div>\n'
        )

    # Document filter checkboxes
    doc_filter_html = ""
    if multi_doc:
        for doc in collection.documents:
            doc_filter_html += (
                f'<label class="doc-checkbox"><input type="checkbox" checked '
                f'value="{_escape(doc.source)}" onchange="applyFilters()">'
                f'<span class="doc-checkbox-label">{_escape(doc.source)}</span>'
                f'<span class="doc-checkbox-count">{len(doc.facts)}</span></label>\n'
            )

    # Build fact cards
    fact_cards = ""
    for idx, (source, fact) in enumerate(all_facts, 1):
        badge_cls = f"badge-{fact.confidence.value}"
        tags = ""
        all_entity_names = []
        for p in fact.people:
            tags += f'<span class="mini-tag entity-tag person">{_escape(p)}</span>'
            all_entity_names.append(p)
        for o in fact.organizations:
            tags += f'<span class="mini-tag entity-tag org">{_escape(o)}</span>'
            all_entity_names.append(o)
        for pl in fact.places:
            tags += f'<span class="mini-tag entity-tag place">{_escape(pl)}</span>'
            all_entity_names.append(pl)
        for d in fact.dates:
            tags += f'<span class="mini-tag entity-tag date">{_escape(d)}</span>'
            all_entity_names.append(d)

        entities_attr = _escape(",".join(all_entity_names))
        idf_val = f"{fact.idf_score:.2f}" if fact.idf_score is not None else ""
        entropy_val = f"{fact.entropy:.2f}" if fact.entropy is not None else ""
        idf_attr = f"{fact.idf_score}" if fact.idf_score is not None else "0"
        entropy_attr = f"{fact.entropy}" if fact.entropy is not None else "0"

        score_badges = ""
        if fact.idf_score is not None:
            score_badges += f'<span class="badge badge-idf" title="Mean IDF">IDF {idf_val}</span>'
        if fact.entropy is not None:
            score_badges += f'<span class="badge badge-entropy" title="Entropy">H {entropy_val}</span>'

        source_badge = ""
        if multi_doc:
            source_badge = f'<span class="badge badge-source" title="{_escape(source)}">{_escape(source)}</span>'

        fact_cards += (
            f'\n    <div class="fact-card" data-entities="{entities_attr}" '
            f'data-confidence="{fact.confidence.value}" data-idf="{idf_attr}" '
            f'data-entropy="{entropy_attr}" data-source="{_escape(source)}">'
            f'\n      <div class="fact-header">'
            f'\n        <span class="fact-number">#{idx}</span>'
            f'\n        <span class="fact-text">{_escape(fact.fact)}</span>'
            f'\n        <div class="fact-badges">{source_badge}{score_badges}'
            f'<span class="badge {badge_cls}">{fact.confidence.value}</span></div>'
            f'\n      </div>'
            f'\n      <div class="fact-meta">'
            f'\n        <div class="fact-entities">{tags}</div>'
            f'\n        <button class="quote-toggle" onclick="this.closest(\'.fact-card\').querySelector(\'.fact-quote\').classList.toggle(\'show\')">source \u25be</button>'
            f'\n      </div>'
            f'\n      <div class="fact-quote">\u201c{_escape(fact.quote)}\u201d</div>'
            f'\n    </div>'
        )

    return _TEMPLATE.format(
        total_facts=total_facts,
        unique_entities=unique_entities,
        high=high,
        medium=medium,
        low=low,
        entity_tags=entity_tags,
        sidebar_entities=sidebar_entities,
        doc_filter=doc_filter_html,
        fact_cards=fact_cards,
    )


_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>atomic-fact report</title>
<style>
:root {{--bg:#0d1117;--surface:#161b22;--surface2:#1c2333;--border:#30363d;
  --text:#e6edf3;--text-muted:#8b949e;--accent:#58a6ff;--green:#3fb950;
  --yellow:#d29922;--orange:#db6d28;--purple:#bc8cff;--cyan:#39d2c0}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6}}
.page{{display:grid;grid-template-columns:260px 1fr;min-height:100vh}}
.sidebar{{background:var(--surface);border-right:1px solid var(--border);padding:16px;
  position:sticky;top:0;height:100vh;overflow-y:auto}}
.sidebar::-webkit-scrollbar{{width:4px}}
.sidebar::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.main{{padding:24px;max-width:960px}}
.sidebar-section{{margin-bottom:20px}}
.sidebar-section h3{{font-size:11px;color:var(--text-muted);text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:8px;font-weight:600}}
.sidebar-section select{{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:6px;padding:6px 8px;font-size:12px;color:var(--text);outline:none;cursor:pointer}}
.conf-btns{{display:flex;gap:4px;flex-wrap:wrap}}
.conf-btns .filter-btn{{padding:4px 10px;border-radius:6px;border:1px solid var(--border);
  background:transparent;color:var(--text-muted);font-size:11px;font-weight:600;cursor:pointer;transition:all .15s}}
.conf-btns .filter-btn:hover{{border-color:var(--accent);color:var(--text)}}
.conf-btns .filter-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.doc-checkbox{{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-muted);cursor:pointer;padding:3px 0}}
.doc-checkbox input{{accent-color:var(--accent);flex-shrink:0}}
.doc-checkbox-label{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.doc-checkbox-count{{font-size:10px;color:var(--text-muted);flex-shrink:0}}
.sidebar-entity-search{{width:100%;background:var(--surface2);border:1px solid var(--border);
  border-radius:6px;padding:5px 8px;font-size:12px;color:var(--text);outline:none;margin-bottom:8px}}
.sidebar-entity-search:focus{{border-color:var(--accent)}}
.sidebar-entity-search::placeholder{{color:var(--text-muted)}}
.sidebar-entity-list{{max-height:300px;overflow-y:auto}}
.sidebar-entity-list::-webkit-scrollbar{{width:4px}}
.sidebar-entity-list::-webkit-scrollbar-thumb{{background:var(--border);border-radius:2px}}
.sidebar-entity-item{{display:flex;align-items:center;justify-content:space-between;
  padding:4px 6px;border-radius:4px;cursor:pointer;font-size:12px;color:var(--text-muted);transition:all .1s}}
.sidebar-entity-item:hover{{background:var(--surface2);color:var(--text)}}
.sidebar-entity-item.active{{background:rgba(88,166,255,.15);color:var(--accent)}}
.sidebar-entity-name{{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-right:6px}}
.sidebar-entity-count{{font-size:10px;flex-shrink:0}}
.sidebar-entity-item.person .sidebar-entity-name::before{{content:'\u25cf ';color:var(--purple);font-size:8px}}
.sidebar-entity-item.org .sidebar-entity-name::before{{content:'\u25cf ';color:var(--accent);font-size:8px}}
.sidebar-entity-item.place .sidebar-entity-name::before{{content:'\u25cf ';color:var(--cyan);font-size:8px}}
.sidebar-entity-item.date .sidebar-entity-name::before{{content:'\u25cf ';color:var(--yellow);font-size:8px}}
</style>
</head>
<body>
<div class="page">
<div class="sidebar">
  <div class="sidebar-section"><h3>Sort</h3>
    <select onchange="sortFacts(this.value)">
      <option value="default">Document order</option>
      <option value="idf-desc">IDF (highest first)</option>
      <option value="idf-asc">IDF (lowest first)</option>
      <option value="entropy-desc">Entropy (highest first)</option>
      <option value="entropy-asc">Entropy (lowest first)</option>
    </select></div>
  <div class="sidebar-section"><h3>Confidence</h3>
    <div class="conf-btns">
      <button class="filter-btn active" data-confidence="all" onclick="setConfidence(this)">All</button>
      <button class="filter-btn" data-confidence="high" onclick="setConfidence(this)">High</button>
      <button class="filter-btn" data-confidence="medium" onclick="setConfidence(this)">Medium</button>
      <button class="filter-btn" data-confidence="low" onclick="setConfidence(this)">Low</button>
    </div></div>
  <div class="sidebar-section"><h3>Documents</h3>{doc_filter}</div>
  <div class="sidebar-section"><h3>Entities ({unique_entities})</h3>
    <input class="sidebar-entity-search" type="text" placeholder="Search entities\u2026" oninput="filterSidebarEntities(this.value)">
    <div class="sidebar-entity-list">{sidebar_entities}</div></div>
</div>
<div class="main">
  <header style="display:flex;align-items:center;padding:16px 0;border-bottom:1px solid var(--border);margin-bottom:24px">
    <h1 style="font-size:20px;font-weight:600;color:var(--accent)">\u269b atomic-fact report</h1></header>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px">
    <div class="sc"><div class="sv" style="color:var(--green)">{total_facts}</div><div class="sl">Atomic Facts</div></div>
    <div class="sc"><div class="sv" style="color:var(--purple)">{unique_entities}</div><div class="sl">Unique Entities</div></div>
    <div class="sc"><div class="sv" style="color:var(--green)">{high}</div><div class="sl">High Confidence</div></div>
    <div class="sc"><div class="sv" style="color:var(--yellow)">{medium} <span style="font-size:14px;color:var(--orange)">/ {low}</span></div><div class="sl">Medium / Low</div></div>
  </div>
  <div class="entity-section" style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:24px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <h2 style="font-size:14px;color:var(--text-muted);font-weight:500;margin:0">Top Entities</h2>
      <button class="clear-btn" id="clearFilter" onclick="clearEntityFilter()" style="display:none;background:var(--surface2);border:1px solid var(--border);color:var(--text-muted);font-size:12px;padding:4px 12px;border-radius:6px;cursor:pointer">Clear filter \u2715</button>
    </div>
    <div class="entity-cloud" style="display:flex;flex-wrap:wrap;gap:8px">{entity_tags}</div>
  </div>
  <div class="facts-section"><h2 id="factsHeading" style="font-size:14px;color:var(--text-muted);margin-bottom:12px;font-weight:500">Extracted Facts</h2>{fact_cards}</div>
</div>
</div>
"""
_TEMPLATE += """\
<style>
.sc{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center}}
.sv{{font-size:28px;font-weight:700}}.sl{{font-size:12px;color:var(--text-muted);margin-top:4px}}
.entity-tag{{padding:4px 12px;border-radius:16px;font-size:13px;font-weight:500;cursor:pointer;
  transition:opacity .15s,transform .15s;user-select:none}}
.entity-tag:hover{{transform:scale(1.05)}}
.entity-tag.active{{box-shadow:0 0 0 2px var(--text)}}.entity-tag.dimmed{{opacity:.3}}
.entity-tag.person{{background:rgba(188,140,255,.15);color:var(--purple);border:1px solid rgba(188,140,255,.3)}}
.entity-tag.org{{background:rgba(88,166,255,.15);color:var(--accent);border:1px solid rgba(88,166,255,.3)}}
.entity-tag.place{{background:rgba(57,210,192,.15);color:var(--cyan);border:1px solid rgba(57,210,192,.3)}}
.entity-tag.date{{background:rgba(210,153,34,.15);color:var(--yellow);border:1px solid rgba(210,153,34,.3)}}
.entity-count{{font-size:11px;opacity:.7;margin-left:4px}}
.fact-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px;transition:border-color .15s}}
.fact-card:hover{{border-color:var(--accent)}}.fact-card.hidden{{display:none}}
.fact-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}}
.fact-number{{font-size:12px;color:var(--text-muted);font-weight:600;min-width:28px}}
.fact-text{{font-size:15px;font-weight:500;flex:1;margin:0 12px}}
.fact-badges{{display:flex;gap:6px;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end}}
.badge{{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;text-transform:uppercase}}
.badge-high{{background:rgba(63,185,80,.15);color:var(--green)}}
.badge-medium{{background:rgba(210,153,34,.15);color:var(--yellow)}}
.badge-low{{background:rgba(219,109,40,.15);color:var(--orange)}}
.badge-idf{{background:rgba(88,166,255,.1);color:var(--accent);font-weight:500;text-transform:none;font-size:10px}}
.badge-entropy{{background:rgba(57,210,192,.1);color:var(--cyan);font-weight:500;text-transform:none;font-size:10px}}
.badge-source{{background:rgba(88,166,255,.08);color:var(--accent);font-weight:500;text-transform:none;font-size:10px;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.fact-quote{{font-size:13px;color:var(--text-muted);font-style:italic;padding:8px 12px;border-left:3px solid var(--border);margin:8px 0 0 40px;background:var(--surface2);border-radius:0 4px 4px 0;display:none}}
.fact-quote.show{{display:block}}
.quote-toggle{{background:none;border:none;color:var(--text-muted);font-size:11px;cursor:pointer;padding:2px 6px;border-radius:4px;margin-left:auto}}
.quote-toggle:hover{{color:var(--accent);background:var(--surface2)}}
.fact-meta{{display:flex;gap:16px;margin-left:40px;margin-top:8px;flex-wrap:wrap;align-items:center}}
.fact-entities{{display:flex;gap:6px;flex-wrap:wrap}}
.mini-tag{{padding:2px 8px;border-radius:10px;font-size:11px}}
</style>
<script>
let activeEntity=null,activeConfidence='all';
function getEnabledDocs(){{const cb=document.querySelectorAll('.doc-checkbox input');if(!cb.length)return null;const s=new Set();cb.forEach(c=>{{if(c.checked)s.add(c.value)}});return s}}
function applyFilters(){{const cards=document.querySelectorAll('.fact-card'),docs=getEnabledDocs();let n=0;cards.forEach(c=>{{const me=!activeEntity||c.dataset.entities.split(',').includes(activeEntity),mc=activeConfidence==='all'||c.dataset.confidence===activeConfidence,md=!docs||docs.has(c.dataset.source);if(me&&mc&&md){{c.classList.remove('hidden');n++}}else{{c.classList.add('hidden')}}}});const h=document.getElementById('factsHeading'),p=[];if(activeEntity)p.push('"'+activeEntity+'"');if(activeConfidence!=='all')p.push(activeConfidence+' confidence');h.textContent=p.length?'Showing '+n+' facts \\u2014 '+p.join(', '):'Showing '+n+' facts'}}
function toggleEntityFilter(el){{const e=el.dataset.entity;if(activeEntity===e){{clearEntityFilter();return}}activeEntity=e;document.getElementById('clearFilter').style.display='inline-block';document.querySelectorAll('.entity-cloud .entity-tag').forEach(t=>{{t.classList.remove('active','dimmed');if(t.dataset.entity===e)t.classList.add('active');else t.classList.add('dimmed')}});document.querySelectorAll('.sidebar-entity-item').forEach(t=>{{t.classList.remove('active');if(t.dataset.entity===e)t.classList.add('active')}});applyFilters()}}
function clearEntityFilter(){{activeEntity=null;document.getElementById('clearFilter').style.display='none';document.querySelectorAll('.entity-cloud .entity-tag').forEach(t=>t.classList.remove('active','dimmed'));document.querySelectorAll('.sidebar-entity-item').forEach(t=>t.classList.remove('active'));applyFilters()}}
function setConfidence(btn){{btn.parentElement.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');activeConfidence=btn.dataset.confidence;applyFilters()}}
function sortFacts(mode){{const c=document.querySelector('.facts-section'),cards=Array.from(c.querySelectorAll('.fact-card'));if(mode==='default'){{cards.sort((a,b)=>parseInt(a.querySelector('.fact-number').textContent.slice(1))-parseInt(b.querySelector('.fact-number').textContent.slice(1)))}}else{{const[f,d]=mode.split('-'),k=f==='idf'?'idf':'entropy',m=d==='desc'?-1:1;cards.sort((a,b)=>m*(parseFloat(a.dataset[k])-parseFloat(b.dataset[k])))}}cards.forEach(x=>c.appendChild(x))}}
function filterSidebarEntities(q){{const lq=q.toLowerCase();document.querySelectorAll('.sidebar-entity-item').forEach(el=>{{el.style.display=el.querySelector('.sidebar-entity-name').textContent.toLowerCase().includes(lq)?'':'none'}})}}
</script>
</body></html>
"""


@click.command()
@click.argument("json_file", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), default=None,
              help="Output HTML file path. Defaults to <input>.html.")
def main(json_file: str, output: str | None) -> None:
    """Convert atomic-fact JSON output into an HTML report."""
    json_path = Path(json_file)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    collection = _normalize_to_collection(data)
    html = generate_html(collection)
    if output is None:
        output = str(json_path.with_suffix(".html"))
    total_facts = sum(len(d.facts) for d in collection.documents)
    Path(output).write_text(html, encoding="utf-8")
    click.echo(f"Wrote report to {output} ({total_facts} facts)")


if __name__ == "__main__":
    main()
