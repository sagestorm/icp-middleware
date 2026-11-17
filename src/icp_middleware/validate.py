"""Interrogative validation against ICP SPEC §5 error codes."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from icp_middleware.constants import (
    AUX_TOKENS,
    EMO_LEXICON,
    ERROR_CODES,
    ERROR_MESSAGES,
    INFORMATION_ACCESS_ASYMMETRIC,
    MAX_LEN,
    MIN_LEN,
    PROTOCOL_VERSION_STR,
    WH_TOKENS,
)
from icp_middleware.normalize import normalize_surface, trim_only
from icp_middleware.types import ValidationResult

_FACT_REF_RE = re.compile(r"^F-[0-9]{3}$")
_FIRST_ALPHA_RE = re.compile(r"[A-Za-z]+")

# SPEC §5.1 — coordinating join after ? / mid-string question boundary
_ATOM_AFTER_Q = re.compile(r"\?\s*(and|or|also)\b", re.IGNORECASE)
_ATOM_Q_BOUNDARY = re.compile(r"\?\s+[A-Z]")
_ATOM_AND_ALSO = re.compile(r"\b(and also|as well as)\b", re.IGNORECASE)
# Fixture/SPEC fail example: two wh/aux clauses joined by and|or|also|plus
_OPENERS = "|".join(sorted(WH_TOKENS | AUX_TOKENS, key=len, reverse=True))
_ATOM_TWO_CLAUSES = re.compile(
    rf"\b(?:{_OPENERS})\b.{{0,120}}?\b(?:and|or|also|plus)\b\s+"
    rf"(?:{_OPENERS})\b",
    re.IGNORECASE | re.DOTALL,
)
_ATOM_SEMI_SLASH = re.compile(
    rf";\s*(?:{_OPENERS})\b|/\s*(?:{_OPENERS})\b",
    re.IGNORECASE,
)

_EMO_WORD = re.compile(
    r"\b(?:angry|furious|outrageous|terrible|awful|horrible|disgusting|"
    r"hate|stupid|idiot|incompetent|shocking|appalling)\b",
    re.IGNORECASE,
)
_EMO_INTENSIFIED = re.compile(
    r"\b(?:so (?:angry|mad|upset)|completely (?:failed|broken)|utterly)\b",
    re.IGNORECASE,
)

_LEAD_OPENER = re.compile(
    r"^(?:why did you|why didn't you|why won't you|don't you agree|"
    r"isn't it true|wouldn't you say)\b",
    re.IGNORECASE,
)
_LEAD_MISCONDUCT = re.compile(
    r"\b(?:cover[- ]?up|lie[sd]?|lied|guilty|to blame|at fault)\b",
    re.IGNORECASE,
)
_LEAD_ACCUSATION = re.compile(
    r"\b(?:you|they|management|leadership)\b",
    re.IGNORECASE,
)
_LEAD_PREFERRED = re.compile(
    r"\b(?:obviously|clearly|everyone knows|of course)\b",
    re.IGNORECASE,
)

_META_PATTERNS = (
    re.compile(
        r"\b(?:this (?:survey|study|questionnaire|form|protocol)|"
        r"your (?:prompt|instructions|system prompt))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:are you (?:an )?ai|language model|chatgpt|llm)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:how (?:should|do) i (?:answer|respond)|what are you looking for)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:rate (?:this|the) (?:survey|experience)|net promoter)\b",
        re.IGNORECASE,
    ),
)


def _fails_atom(text: str) -> bool:
    if text.count("?") > 1:
        return True
    if _ATOM_AFTER_Q.search(text) or _ATOM_Q_BOUNDARY.search(text):
        return True
    if _ATOM_AND_ALSO.search(text):
        return True
    if _ATOM_TWO_CLAUSES.search(text):
        return True
    if ";" in text or _ATOM_SEMI_SLASH.search(text):
        return True
    return False


def _fails_wh(surface: str) -> bool:
    if not surface.endswith("?"):
        return True
    match = _FIRST_ALPHA_RE.search(surface)
    if not match:
        return True
    token = match.group(0).lower()
    return token not in WH_TOKENS and token not in AUX_TOKENS


def _fails_emo(text: str) -> bool:
    if "!" in text:
        return True
    if _EMO_WORD.search(text) or _EMO_INTENSIFIED.search(text):
        return True
    return False


def _fails_lead(text: str) -> bool:
    if _LEAD_OPENER.search(text.strip()):
        return True
    if _LEAD_MISCONDUCT.search(text) and _LEAD_ACCUSATION.search(text):
        return True
    if _LEAD_PREFERRED.search(text):
        return True
    return False


def _fails_meta(text: str) -> bool:
    return any(p.search(text) for p in _META_PATTERNS)


def _fails_len(raw: str) -> bool:
    trimmed = trim_only(raw)
    n = len(trimmed)  # Unicode scalars (Python str code points)
    return not (MIN_LEN <= n <= MAX_LEN)


def _fails_fact(
    information_access: str,
    fact_refs: Sequence[str],
    fact_ids_allowed: Sequence[str] | None,
) -> bool:
    for ref in fact_refs:
        if not _FACT_REF_RE.match(ref):
            return True
    if information_access == INFORMATION_ACCESS_ASYMMETRIC:
        if not fact_refs:
            return True
        if fact_ids_allowed is not None:
            allowed = set(fact_ids_allowed)
            ref_set = set(fact_refs)
            if not ref_set.issubset(allowed) or not (ref_set & allowed):
                return True
    return False


def validate_interrogative(
    text: str,
    *,
    information_access: str,
    fact_ids_allowed: Sequence[str] | None = None,
    fact_refs: Iterable[str] | None = None,
) -> ValidationResult:
    """Validate an interrogative against ICP SPEC §5 gates.

    Returns a :class:`ValidationResult` with ``passed`` / ``codes`` for the
    Python API and protocol fields (``status``, ``errors``, ``gates_passed``).
    """
    refs = list(fact_refs or ())
    surface = normalize_surface(text)

    failed: list[str] = []
    # Evaluate all gates (order matches ERROR_CODES)
    checks = {
        "E_ATOM": _fails_atom(text),
        "E_WH": _fails_wh(surface if surface else trim_only(text)),
        "E_EMO": _fails_emo(text),
        "E_LEAD": _fails_lead(text),
        "E_LEN": _fails_len(text),
        "E_META": _fails_meta(text),
        "E_FACT": _fails_fact(information_access, refs, fact_ids_allowed),
    }
    for code in ERROR_CODES:
        if checks[code]:
            failed.append(code)

    gates_passed = tuple(c for c in ERROR_CODES if c not in failed)
    errors = tuple(
        {"code": c, "message": ERROR_MESSAGES[c]} for c in failed
    )
    status = "accepted" if not failed else "rejected"
    return ValidationResult(
        passed=not failed,
        codes=tuple(failed),
        status=status,
        errors=errors,
        gates_passed=gates_passed,
        protocol_version=PROTOCOL_VERSION_STR,
    )
