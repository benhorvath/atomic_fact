"""Tests for atomic_fact.reader — file reading and validation."""

import pytest
import click

from atomic_fact.reader import read_text


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
