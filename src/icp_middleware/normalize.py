"""Cleaning-only normalization (ICP SPEC §6.2). No paraphrase."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from icp_middleware.constants import INFORMATION_ACCESS_IDENTICAL

_WS_RE = re.compile(r"\s+")
_WRAP_QUOTES = (
    ('"', '"'),
    ("'", "'"),
    ("\u201c", "\u201d"),
    ("\u2018", "\u2019"),
)


def trim_only(text: str) -> str:
    """Trim leading/trailing whitespace only (E_LEN scalar basis)."""
    return text.strip()


def normalize_surface(text: str) -> str:
    """NFC + trim + whitespace collapse + optional wrap-quote strip.

    Does not paraphrase. Does not add ``?`` to non-questions.
    """
    nfc = unicodedata.normalize("NFC", text)
    cleaned = _WS_RE.sub(" ", nfc.strip())
    for left, right in _WRAP_QUOTES:
        if len(cleaned) >= 2 and cleaned.startswith(left) and cleaned.endswith(right):
            cleaned = cleaned[len(left) : -len(right)].strip()
            cleaned = _WS_RE.sub(" ", cleaned)
            break
    # Ensure single trailing ? if terminator lost solely due to trim of quotes
    # and the body still looks interrogative — only when original had '?' .
    if "?" in text and cleaned and not cleaned.endswith("?"):
        cleaned = cleaned.rstrip("?.!") + "?"
    return cleaned


def normalize_interrogative(
    text: str,
    *,
    information_access: str = INFORMATION_ACCESS_IDENTICAL,
    fact_ids_allowed: Sequence[str] | None = None,
    fact_refs: Sequence[str] | None = None,
    fact_sheet_text: str | None = None,
) -> str | None:
    """Cleaning-only normalize; ``None`` if validation fails."""
    from icp_middleware.validate import validate_interrogative

    result = validate_interrogative(
        text,
        information_access=information_access,
        fact_ids_allowed=fact_ids_allowed,
        fact_refs=fact_refs,
        fact_sheet_text=fact_sheet_text,
    )
    if not result.passed:
        return None
    return normalize_surface(text)
