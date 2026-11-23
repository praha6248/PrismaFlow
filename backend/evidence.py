"""Text matching shared by community retrieval and citation checks."""

from __future__ import annotations

import math
import re
from typing import Any


SHORT_TERMS = {"ai", "vr", "ar", "ux", "ui", "3d"}
STOPWORDS = {"for", "the", "and", "with", "how", "what", "when", "your", "you", "from", "into", "about", "best", "app", "apps",
             "dla", "jak", "oraz", "się", "jest", "czy", "które", "który", "przez", "jako", "przy", "nad", "pod", "bez"}


def terms(query: str) -> list[str]:
    """Return 5-character stems of the meaningful words of a query."""
    words = re.findall(r"[^\W_]+", query.casefold())
    return list(dict.fromkeys(w[:5] for w in words if w not in STOPWORDS and (len(w) >= 3 or w in SHORT_TERMS)))


def relevant(text: str, stems: list[str], minimum: float) -> bool:
    """Tell whether enough query stems occur in a text."""
    if not stems:
        return False
    words = re.findall(r"[^\W_]+", text.casefold())
    tokens = {word[:5] for word in words}
    if "ai" in stems and re.search(r"artificial intelligence|sztuczn\w* inteligenc", text, re.I):
        tokens.add("ai")
    if any(stem not in tokens for stem in stems if stem in SHORT_TERMS):
        return False
    return len(tokens.intersection(stems)) >= max(1, math.ceil(len(stems) * minimum))


def supports_problem(item: dict[str, Any], problem: dict[str, Any]) -> bool:
    """Require a discussion related to the selected problem before citing it."""
    if item["source"] not in ("community", "reddit"):
        return False
    text = " ".join((item["title"], item.get("body") or "", (item.get("meta") or {}).get("original") or ""))
    title_terms = terms(problem["title"])
    keyword_terms = terms(problem.get("keyword") or "")
    qualifiers = [term for term in title_terms if term in SHORT_TERMS]
    if qualifiers and not relevant(text, qualifiers, 1):
        return False
    return relevant(text, title_terms, 0.4) or relevant(text, keyword_terms, 0.5)
