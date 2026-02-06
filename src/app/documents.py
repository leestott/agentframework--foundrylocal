"""
Document loader utility.
────────────────────────
Reads local text/markdown files from a folder and returns their content
with filename + line-number metadata so agents can cite sources accurately.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".rst", ".html"}


@dataclass
class DocumentChunk:
    """A chunk of a local document with citation metadata."""
    filename: str
    start_line: int
    end_line: int
    text: str


@dataclass
class LoadedDocuments:
    """All documents loaded from a folder."""
    chunks: list[DocumentChunk] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        """Single string with [filename, lines X-Y] headers for each chunk."""
        parts: list[str] = []
        for c in self.chunks:
            header = f"[{c.filename}, lines {c.start_line}-{c.end_line}]"
            parts.append(f"{header}\n{c.text}")
        return "\n\n".join(parts)

    @property
    def file_count(self) -> int:
        seen: set[str] = set()
        for c in self.chunks:
            seen.add(c.filename)
        return len(seen)


def load_documents(folder: str | Path, max_chars_per_chunk: int = 2000) -> LoadedDocuments:
    """Load and chunk all supported files from *folder*.

    Each file is split into chunks of ≤ *max_chars_per_chunk* characters
    (on line boundaries) so that they fit within typical context windows.
    """
    folder = Path(folder)
    if not folder.is_dir():
        log.warning("Documents folder does not exist: %s", folder)
        return LoadedDocuments()

    docs = LoadedDocuments()
    for fpath in sorted(folder.iterdir()):
        if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not fpath.is_file():
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("Skipping %s: %s", fpath.name, exc)
            continue

        lines = text.splitlines(keepends=True)
        chunk_lines: list[str] = []
        chunk_start = 1
        char_count = 0

        for i, line in enumerate(lines, start=1):
            chunk_lines.append(line)
            char_count += len(line)
            if char_count >= max_chars_per_chunk:
                docs.chunks.append(
                    DocumentChunk(
                        filename=fpath.name,
                        start_line=chunk_start,
                        end_line=i,
                        text="".join(chunk_lines),
                    )
                )
                chunk_lines = []
                chunk_start = i + 1
                char_count = 0

        if chunk_lines:
            docs.chunks.append(
                DocumentChunk(
                    filename=fpath.name,
                    start_line=chunk_start,
                    end_line=chunk_start + len(chunk_lines) - 1,
                    text="".join(chunk_lines),
                )
            )

    log.info(
        "Loaded %d chunk(s) from %d file(s) in %s",
        len(docs.chunks),
        docs.file_count,
        folder,
    )
    return docs
