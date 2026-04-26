"""User-supplied entity alias resolution.

Reads a TOML file mapping variant entity names to canonical forms
and applies the mapping to the structured entity fields on each fact.
Only entity tags (people, organizations, places) are modified —
fact text and quotes are left untouched.

Example aliases.toml:

    [people]
    "Senator Reid" = "Harry Reid"
    "Reid" = "Harry Reid"

    [organizations]
    "National Aeronautics and Space Administration" = "NASA"
    "the space agency" = "NASA"

    [places]
    "the ranch" = "Waggoner Ranch"
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from atomic_fact.models import AtomicFact

# Maps alias TOML sections to AtomicFact field names
_SECTION_TO_FIELD = {
    "people": "people",
    "organizations": "organizations",
    "places": "places",
}


def load_aliases(path: str) -> dict[str, dict[str, str]]:
    """Load an aliases TOML file.

    Returns:
        Dict keyed by section name ("people", "organizations", "places"),
        each containing a mapping of variant -> canonical name.
    """
    text = Path(path).read_text(encoding="utf-8")
    raw = tomllib.loads(text)
    aliases: dict[str, dict[str, str]] = {}
    for section in _SECTION_TO_FIELD:
        if section in raw and isinstance(raw[section], dict):
            aliases[section] = {str(k): str(v) for k, v in raw[section].items()}
    return aliases


def apply_aliases(
    facts: list[AtomicFact],
    aliases: dict[str, dict[str, str]],
) -> list[AtomicFact]:
    """Replace entity tag values using the alias mapping.

    For each fact, walks people/organizations/places and replaces
    any matching key (case-insensitive) with its canonical value.
    Deduplicates the resulting list to avoid repeated canonical names.

    Args:
        facts: List of extracted atomic facts.
        aliases: Output of load_aliases().

    Returns:
        The same list with entity fields updated in place.
    """
    for fact in facts:
        for section, field in _SECTION_TO_FIELD.items():
            mapping = aliases.get(section, {})
            if not mapping:
                continue
            # Build case-insensitive lookup
            lower_map = {k.lower(): v for k, v in mapping.items()}
            original: list[str] = getattr(fact, field)
            resolved = []
            seen: set[str] = set()
            for name in original:
                canonical = lower_map.get(name.lower(), name)
                if canonical not in seen:
                    resolved.append(canonical)
                    seen.add(canonical)
            setattr(fact, field, resolved)
    return facts
