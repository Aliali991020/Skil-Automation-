"""Knowledge layer — brand-aligned markdown assets under /knowledge/.

Every generated script, sales reply, and brief stays 100% aligned with the
creator's brand identity by drawing hooks, pricing, and language rules from
these files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import KNOWLEDGE_DIR


def list_knowledge() -> dict[str, str]:
    """Return {filename: content} for every markdown file in /knowledge/."""
    if not KNOWLEDGE_DIR.exists():
        return {}
    out: dict[str, str] = {}
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        try:
            out[path.name] = path.read_text(encoding="utf-8")
        except Exception:
            out[path.name] = ""
    return out


def get(topic: str) -> str:
    """Return the content of a knowledge file by topic name (with or without .md)."""
    name = topic if topic.endswith(".md") else f"{topic}.md"
    path = KNOWLEDGE_DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def search(term: str) -> list[tuple[str, str]]:
    """Naive full-text search across the knowledge base.

    Returns [(filename, snippet)] for files containing the term.
    """
    term_lower = term.lower()
    results: list[tuple[str, str]] = []
    for name, content in list_knowledge().items():
        if term_lower in content.lower():
            idx = content.lower().find(term_lower)
            start = max(0, idx - 120)
            end = min(len(content), idx + 180)
            snippet = content[start:end].replace("\n", " ")
            results.append((name, snippet))
    return results
