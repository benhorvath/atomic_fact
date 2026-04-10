"""CLI smoke tests using Click's test runner."""

from unittest.mock import patch

from click.testing import CliRunner

from atomic_fact.cli import main
from atomic_fact.models import AtomicFact, Confidence, ExtractionResult


def _sample_result():
    return ExtractionResult(
        facts=[
            AtomicFact(
                fact="Wayne met the president.",
                quote="Congressman Wayne met with the president.",
                entities=["Wayne"],
                dates=["1968-10-04"],
                confidence=Confidence.HIGH,
            )
        ]
    )


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Extract atomic facts" in result.output

    @patch("atomic_fact.cli.extract", return_value=_sample_result())
    def test_stdout_output(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text about Wayne.")
        runner = CliRunner()
        result = runner.invoke(main, [str(f)])
        assert result.exit_code == 0
        assert "Wayne met the president" in result.output

    @patch("atomic_fact.cli.extract", return_value=_sample_result())
    def test_pretty_output(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text.")
        runner = CliRunner()
        result = runner.invoke(main, [str(f), "--pretty"])
        assert result.exit_code == 0
        # Pretty output has newlines and indentation
        assert "\n" in result.output
        assert "  " in result.output

    @patch("atomic_fact.cli.extract", return_value=_sample_result())
    def test_file_output(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text.")
        out = tmp_path / "output.json"
        runner = CliRunner()
        result = runner.invoke(main, [str(f), "--output", str(out)])
        assert result.exit_code == 0
        assert "Wrote 1 facts" in result.output
        assert out.read_text().startswith('{"facts"')

    def test_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["nonexistent.txt"])
        assert result.exit_code != 0
