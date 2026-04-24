"""Tests for atomic_fact.reader — file reading and validation."""

import pytest
import click

from atomic_fact.reader import read_directory, read_text


class TestReadText:
    def test_reads_txt_file(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("Hello world.", encoding="utf-8")
        assert read_text(str(f)) == "Hello world."

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(click.UsageError, match="File not found"):
            read_text(str(tmp_path / "nope.txt"))

    def test_wrong_extension_raises(self, tmp_path):
        f = tmp_path / "data.pdf"
        f.write_text("fake pdf", encoding="utf-8")
        with pytest.raises(click.UsageError, match="Unsupported file type"):
            read_text(str(f))

    def test_bad_encoding_raises(self, tmp_path):
        f = tmp_path / "bad.txt"
        f.write_bytes(b"\xff\xfe" + "héllo".encode("utf-16-le"))
        with pytest.raises(click.UsageError, match="Could not decode"):
            read_text(str(f), encoding="ascii")

    def test_custom_encoding(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes("café".encode("latin-1"))
        assert read_text(str(f), encoding="latin-1") == "café"


class TestReadDirectory:
    def test_reads_all_txt_files(self, tmp_path):
        (tmp_path / "b.txt").write_text("bravo", encoding="utf-8")
        (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
        result = read_directory(str(tmp_path))
        assert result == [("a.txt", "alpha"), ("b.txt", "bravo")]

    def test_sorted_by_filename(self, tmp_path):
        for name in ["z.txt", "m.txt", "a.txt"]:
            (tmp_path / name).write_text(name, encoding="utf-8")
        filenames = [name for name, _ in read_directory(str(tmp_path))]
        assert filenames == ["a.txt", "m.txt", "z.txt"]

    def test_ignores_non_txt_files(self, tmp_path):
        (tmp_path / "doc.txt").write_text("yes", encoding="utf-8")
        (tmp_path / "doc.pdf").write_text("no", encoding="utf-8")
        (tmp_path / "readme.md").write_text("no", encoding="utf-8")
        result = read_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0][0] == "doc.txt"

    def test_ignores_nested_directories(self, tmp_path):
        (tmp_path / "top.txt").write_text("top", encoding="utf-8")
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested", encoding="utf-8")
        result = read_directory(str(tmp_path))
        assert len(result) == 1
        assert result[0][0] == "top.txt"

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(click.UsageError, match="No .txt files found"):
            read_directory(str(tmp_path))

    def test_not_a_directory_raises(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi", encoding="utf-8")
        with pytest.raises(click.UsageError, match="Not a directory"):
            read_directory(str(f))
