"""Tests for atomic_fact.extractor — mocked OpenAI integration."""

from unittest.mock import MagicMock, patch

import pytest
import click

from atomic_fact.extractor import extract
from atomic_fact.models import AtomicFact, Confidence, ExtractionResult


def _mock_completion(result: ExtractionResult):
    """Build a mock OpenAI completion response."""
    message = MagicMock()
    message.parsed = result
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _sample_result():
    return ExtractionResult(
        facts=[
            AtomicFact(
                fact="Wayne met the president.",
                quote="Congressman Wayne met with the president on October 4, 1968.",
                entities=["Wayne", "the president"],
                dates=["1968-10-04"],
                confidence=Confidence.HIGH,
            )
        ]
    )


class TestExtract:
    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    @patch("atomic_fact.extractor.openai.OpenAI")
    def test_single_chunk_returns_facts(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.beta.chat.completions.parse.return_value = _mock_completion(
            _sample_result()
        )

        result = extract("Some short text.", model="gpt-4o")

        assert len(result.facts) == 1
        assert result.facts[0].fact == "Wayne met the president."
        mock_client.beta.chat.completions.parse.assert_called_once()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    @patch("atomic_fact.extractor.openai.OpenAI")
    def test_deduplicates_across_chunks(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        # Return the same fact for every chunk call
        mock_client.beta.chat.completions.parse.return_value = _mock_completion(
            _sample_result()
        )

        # Force multiple chunks by using a very small max_chars
        with patch(
            "atomic_fact.extractor.chunk_text", return_value=["chunk1", "chunk2"]
        ):
            result = extract("long text", model="gpt-4o")

        # Same quote in both chunks — should be deduplicated to 1
        assert len(result.facts) == 1

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_raises(self):
        with pytest.raises(click.UsageError, match="OPENAI_API_KEY"):
            extract("some text")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"})
    @patch("atomic_fact.extractor.openai.OpenAI")
    def test_none_response_raises(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.beta.chat.completions.parse.return_value = _mock_completion(
            None  # type: ignore
        )
        # Patch _mock_completion to return None for parsed
        msg = MagicMock()
        msg.parsed = None
        choice = MagicMock()
        choice.message = msg
        comp = MagicMock()
        comp.choices = [choice]
        mock_client.beta.chat.completions.parse.return_value = comp

        with pytest.raises(click.UsageError, match="empty or unparseable"):
            extract("some text")
