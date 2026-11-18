"""Interrogative validation against ICP SPEC §5 error codes."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from icp_middleware.constants import (
    AUX_TOKENS,
    BANAL_INTERROGATIVES,
    ERROR_CODES,
    ERROR_MESSAGES,
    INFORMATION_ACCESS_ASYMMETRIC,
    MAX_LEN,
    MIN_LEN,
    PROTOCOL_VERSION_STR,
    SPEC_STOPWORDS,
    WH_TOKENS,
)
from icp_middleware.normalize import normalize_surface, trim_only
from icp_middleware.types import ValidationResult

_FACT_REF_RE = re.compile(r"^F-[0-9]{3}$")
_FIRST_ALPHA_RE = re.compile(r"[A-Za-z]+")
_CONTENT_TOKEN_RE = re.compile(r"[A-Za-z0-9]{4,}", re.UNICODE)

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

# SPEC §5.8 E_SPEC — generic / banal templates
_SPEC_GENERIC_EVENT = re.compile(
    r"^\s*what\s+(?:event|incident|situation|issue)\s+(?:is|was)\s+"
    r"(?:being\s+)?(?:described|this)\b",
    re.IGNORECASE,
)
_SPEC_WHAT_HAPPENED = re.compile(r"^\s*what\s+happened(?:\?|\s*$)", re.IGNORECASE)
_SPEC_GOING_ON = re.compile(
    r"^\s*what\s+(?:is|was)\s+going\s+on\b",
    re.IGNORECASE,
)
_SPEC_TELL_MORE = re.compile(
    r"^\s*can\s+you\s+(?:tell|explain)\s+(?:me\s+)?more\b",
    re.IGNORECASE,
)
_SPEC_TELL_ABOUT = re.compile(
    r"^\s*what\s+(?:do|can)\s+you\s+tell\s+me\s+about\s+(?:the\s+)?"
    r"(?:event|incident)\b",
    re.IGNORECASE,
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


# Prepositional fronts before a wh-word (e.g. "At what time…", "In which…").
_WH_PREP_FRONT = re.compile(
    r"^(?:at|in|on|for|by|to|from)\s+"
    r"(?:who|what|when|where|why|which|how|whose|whom)\b",
    re.IGNORECASE,
)


def _fails_wh(surface: str) -> bool:
    if not surface.endswith("?"):
        return True
    if _WH_PREP_FRONT.match(surface.lstrip()):
        return False
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


def content_tokens(text: str) -> frozenset[str]:
    """Extract E_SPEC content tokens (len ≥4, lowercased, stopwords dropped)."""
    raw = {m.group(0).lower() for m in _CONTENT_TOKEN_RE.finditer(text)}
    return frozenset(t for t in raw if t not in SPEC_STOPWORDS)


def _what_happened_lacks_substance(text: str) -> bool:
    """True when ``what happened`` has no other content word len ≥5 besides happened."""
    if not _SPEC_WHAT_HAPPENED.match(text.strip()):
        return False
    extras = [
        t
        for t in _CONTENT_TOKEN_RE.findall(text.lower())
        if t != "happened" and len(t) >= 5
    ]
    return not extras


def matches_banal_template(text: str) -> bool:
    """Return True when the interrogative matches an E_SPEC generic template."""
    surface = trim_only(text)
    lowered = surface.lower()
    if lowered in BANAL_INTERROGATIVES:
        return True
    if _SPEC_GENERIC_EVENT.match(surface):
        return True
    if _what_happened_lacks_substance(surface):
        return True
    if _SPEC_GOING_ON.match(surface):
        return True
    if _SPEC_TELL_MORE.match(surface):
        return True
    if _SPEC_TELL_ABOUT.match(surface):
        return True
    return False


def _fails_spec(text: str, fact_sheet_text: str | None) -> bool:
    if matches_banal_template(text):
        return True
    sheet = (fact_sheet_text or "").strip()
    if not sheet:
        return False
    q_tokens = content_tokens(text)
    sheet_tokens = content_tokens(sheet)
    return not (q_tokens & sheet_tokens)


def validate_interrogative(
    text: str,
    *,
    information_access: str,
    fact_ids_allowed: Sequence[str] | None = None,
    fact_refs: Iterable[str] | None = None,
    fact_sheet_text: str | None = None,
) -> ValidationResult:
    """Validate an interrogative against ICP SPEC §5 gates.

    Returns a :class:`ValidationResult` with ``passed`` / ``codes`` for the
    Python API and protocol fields (``status``, ``errors``, ``gates_passed``).

    When ``fact_sheet_text`` is non-empty, ``E_SPEC`` also requires content-token
    overlap between the interrogative and the sheet.
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
        "E_SPEC": _fails_spec(text, fact_sheet_text),
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
