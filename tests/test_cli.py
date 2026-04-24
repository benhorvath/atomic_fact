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
                people=["Wayne"],
                organizations=[],
                places=[],
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
        assert "atomic-fact" in result.output

    def test_extract_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["extract", "--help"])
        assert result.exit_code == 0
        assert "Extract atomic facts" in result.output

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_stdout_output(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text about Wayne.")
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(f)])
        assert result.exit_code == 0
        assert "Wayne met the president" in result.output

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_stdout_is_pretty_printed(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text.")
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(f)])
        assert result.exit_code == 0
        assert "\n" in result.output
        assert "  " in result.output

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_file_output(self, mock_extract, tmp_path):
        f = tmp_path / "input.txt"
        f.write_text("Some text.")
        out = tmp_path / "output.json"
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(f), "--output", str(out)])
        assert result.exit_code == 0
        assert "Wrote 1 facts" in result.output
        assert out.read_text().startswith('{\n  "facts"')

    def test_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ["extract", "nonexistent.txt"])
        assert result.exit_code != 0


class TestCLIDirectoryMode:
    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_directory_outputs_collection_json(self, mock_extract, tmp_path):
        (tmp_path / "a.txt").write_text("Doc A.")
        (tmp_path / "b.txt").write_text("Doc B.")
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(tmp_path)])
        assert result.exit_code == 0
        assert '"documents"' in result.output
        assert '"source"' in result.output

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_directory_file_output(self, mock_extract, tmp_path):
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "a.txt").write_text("Doc A.")
        out = tmp_path / "output.json"
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(docs), "--output", str(out)])
        assert result.exit_code == 0
        content = out.read_text()
        assert '"documents"' in content
        assert '"a.txt"' in content

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_single_file_still_returns_extraction_result(self, mock_extract, tmp_path):
        f = tmp_path / "single.txt"
        f.write_text("Just one file.")
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(f)])
        assert result.exit_code == 0
        assert '"facts"' in result.output
        assert '"documents"' not in result.output


class TestCLIResume:
    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_cache_files_written(self, mock_extract, tmp_path):
        (tmp_path / "a.txt").write_text("Doc A.")
        (tmp_path / "b.txt").write_text("Doc B.")
        runner = CliRunner()
        result = runner.invoke(main, ["extract", str(tmp_path)])
        assert result.exit_code == 0
        cache_dir = tmp_path / ".atomic_fact_cache"
        assert cache_dir.exists()
        assert (cache_dir / "a.txt.json").exists()
        assert (cache_dir / "b.txt.json").exists()

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_resume_skips_cached(self, mock_extract, tmp_path):
        (tmp_path / "a.txt").write_text("Doc A.")
        (tmp_path / "b.txt").write_text("Doc B.")
        runner = CliRunner()
        runner.invoke(main, ["extract", str(tmp_path)])
        assert mock_extract.call_count == 2
        mock_extract.reset_mock()
        result = runner.invoke(main, ["extract", str(tmp_path), "--resume"])
        assert result.exit_code == 0
        assert mock_extract.call_count == 0
        assert '"documents"' in result.output

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_resume_processes_only_new(self, mock_extract, tmp_path):
        (tmp_path / "a.txt").write_text("Doc A.")
        runner = CliRunner()
        runner.invoke(main, ["extract", str(tmp_path)])
        assert mock_extract.call_count == 1
        mock_extract.reset_mock()
        (tmp_path / "b.txt").write_text("Doc B.")
        result = runner.invoke(main, ["extract", str(tmp_path), "--resume"])
        assert result.exit_code == 0
        assert mock_extract.call_count == 1

    @patch("atomic_fact.cli.run_extract", return_value=_sample_result())
    def test_without_resume_reprocesses_all(self, mock_extract, tmp_path):
        (tmp_path / "a.txt").write_text("Doc A.")
        runner = CliRunner()
        runner.invoke(main, ["extract", str(tmp_path)])
        mock_extract.reset_mock()
        result = runner.invoke(main, ["extract", str(tmp_path)])
        assert result.exit_code == 0
        assert mock_extract.call_count == 1
