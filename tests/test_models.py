"""Tests for atomic_fact.models — serialization and validation."""

import json

import pytest
from pydantic import ValidationError

from atomic_fact.models import AtomicFact, ExtractionResult


def _make_fact(**overrides):
    defaults = {
        "fact": "Wayne met the president.",
        "quote": "Congressman Wayne met with the president on October 4, 1968.",
        "entities": ["Wayne", "the president"],
        "dates": ["1968-10-04"],
        "confidence": "high",
    }
    defaults.update(overrides)
    return AtomicFact(**defaults)


class TestAtomicFact:
    def test_roundtrip_json(self):
        fact = _make_fact()
        data = json.loads(fact.model_dump_json())
        restored = AtomicFact(**data)
        assert restored == fact

    def test_entities_and_dates_default_to_empty(self):
        fact = AtomicFact(fact="x", quote="x", confidence="low")
        assert fact.entities == []
        assert fact.dates == []

    def test_confidence_enum_values(self):
        for level in ("high", "medium", "low"):
            fact = _make_fact(confidence=level)
            assert fact.confidence == level

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValidationError):
            _make_fact(confidence="super_high")

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            AtomicFact(fact="x", quote="x")  # missing confidence


class TestExtractionResult:
    def test_empty_result(self):
        result = ExtractionResult()
        assert result.facts == []
        assert json.loads(result.model_dump_json()) == {"facts": []}

    def test_result_with_facts(self):
        facts = [_make_fact(), _make_fact(fact="Another fact.", confidence="low")]
        result = ExtractionResult(facts=facts)
        assert len(result.facts) == 2

    def test_json_schema_has_expected_keys(self):
        schema = ExtractionResult.model_json_schema()
        assert "facts" in schema["properties"]
