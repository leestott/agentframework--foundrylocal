"""Smoke tests for the Local Research & Synthesis Desk.

These tests verify the non-LLM parts of the codebase (document loading,
tool functions, bootstrapper config) without requiring a running Foundry
Local service.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ────────────────────────────────────────────────────────────────────
# Document loader tests
# ────────────────────────────────────────────────────────────────────

def test_load_documents_empty_folder():
    """Loading from an empty folder returns zero chunks."""
    from src.app.documents import load_documents

    with tempfile.TemporaryDirectory() as tmp:
        docs = load_documents(tmp)
        assert docs.file_count == 0
        assert len(docs.chunks) == 0


def test_load_documents_with_files():
    """Loading from a folder with .txt files returns correct chunks."""
    from src.app.documents import load_documents

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.txt"
        p.write_text("Line one\nLine two\nLine three\n", encoding="utf-8")

        docs = load_documents(tmp)
        assert docs.file_count == 1
        assert len(docs.chunks) >= 1
        assert "Line one" in docs.combined_text
        assert "[sample.txt" in docs.combined_text


def test_load_documents_skips_unsupported():
    """Non-supported file extensions are ignored."""
    from src.app.documents import load_documents

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "data.bin").write_bytes(b"\x00\x01\x02")
        (Path(tmp) / "notes.txt").write_text("hello", encoding="utf-8")

        docs = load_documents(tmp)
        assert docs.file_count == 1  # only .txt loaded


def test_load_documents_chunking():
    """Large files are split into chunks respecting max_chars_per_chunk."""
    from src.app.documents import load_documents

    with tempfile.TemporaryDirectory() as tmp:
        big = "A" * 80 + "\n"  # 81 chars per line
        (Path(tmp) / "big.txt").write_text(big * 100, encoding="utf-8")

        docs = load_documents(tmp, max_chars_per_chunk=500)
        assert len(docs.chunks) > 1


# ────────────────────────────────────────────────────────────────────
# Tool function tests
# ────────────────────────────────────────────────────────────────────

def test_word_count():
    from src.app.agents import word_count

    assert "3" in word_count("hello world today")


def test_extract_keywords():
    from src.app.agents import extract_keywords

    text = "foundry foundry local local model model agent"
    result = extract_keywords(text)
    assert "foundry" in result or "local" in result or "model" in result


def test_extract_keywords_no_repeats():
    from src.app.agents import extract_keywords

    result = extract_keywords("each word is unique here today")
    assert "(none detected)" in result


# ────────────────────────────────────────────────────────────────────
# FoundryLocalBootstrapper config tests (no service needed)
# ────────────────────────────────────────────────────────────────────

def test_bootstrapper_default_alias():
    """Default alias matches .env.example or falls back to qwen2.5."""
    from src.app.foundry_boot import FoundryLocalBootstrapper

    os.environ.pop("MODEL_ALIAS", None)
    boot = FoundryLocalBootstrapper()
    assert boot.alias == "qwen2.5-0.5b"


def test_bootstrapper_custom_alias():
    from src.app.foundry_boot import FoundryLocalBootstrapper

    boot = FoundryLocalBootstrapper(alias="phi-3.5-mini")
    assert boot.alias == "phi-3.5-mini"


def test_foundry_connection_dataclass():
    from src.app.foundry_boot import FoundryConnection

    conn = FoundryConnection(
        endpoint="http://localhost:5272/v1",
        api_key="none",
        model_id="test-model",
        model_alias="test",
    )
    assert conn.endpoint == "http://localhost:5272/v1"
    assert conn.model_alias == "test"
