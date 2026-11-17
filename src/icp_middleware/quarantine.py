"""Bias quarantine: protocol flags/spans + convenience extractions."""

from __future__ import annotations

import re

from icp_middleware.constants import EMO_EXTENDED, EMO_LEXICON
from icp_middleware.types import BiasQuarantine, BiasSpan

_WORD_RE = re.compile(r"[A-Za-z']+")
_LEAD_OPENER = re.compile(
    r"(why did you|why didn't you|why won't you|don't you agree|"
    r"isn't it true|wouldn't you say)",
    re.IGNORECASE,
)
_LEAD_PREFERRED = re.compile(
    r"\b(obviously|clearly|everyone knows|of course)\b",
    re.IGNORECASE,
)
_META = re.compile(
    r"\b(this (?:survey|study|questionnaire|form|protocol)|"
    r"your (?:prompt|instructions|system prompt)|"
    r"are you (?:an )?ai|language model|chatgpt|llm|"
    r"how (?:should|do) i (?:answer|respond)|what are you looking for|"
    r"rate (?:this|the) (?:survey|experience)|net promoter)\b",
    re.IGNORECASE,
)
_COMPOUND = re.compile(
    r"\b(and|or|also|plus|and also|as well as)\b",
    re.IGNORECASE,
)
_OPENER = re.compile(
    r"\b(who|what|when|where|why|which|how|whose|whom|"
    r"is|are|was|were|do|does|did|can|could|would|should|"
    r"has|have|had|will|may|might)\b",
    re.IGNORECASE,
)


def _spans_for(pattern: re.Pattern[str], text: str, reason: str) -> list[BiasSpan]:
    return [
        BiasSpan(start=m.start(), end=m.end(), reason=reason)
        for m in pattern.finditer(text)
    ]


def quarantine_bias(
    text: str,
    *,
    freeform_affect: str | None = None,
    validation_codes: list[str] | tuple[str, ...] | None = None,
) -> BiasQuarantine:
    """Extract quarantine flags/spans for dual-field persistence."""
    lower_words = [w.lower() for w in _WORD_RE.findall(text)]
    emotion_terms = sorted(
        {w for w in lower_words if w in EMO_LEXICON or w in EMO_EXTENDED}
    )

    leading_modifiers = [m.group(0).lower() for m in _LEAD_OPENER.finditer(text)]
    leading_modifiers += [m.group(0).lower() for m in _LEAD_PREFERRED.finditer(text)]
    leading_modifiers = list(dict.fromkeys(leading_modifiers))

    compound_flags = [m.group(0).lower() for m in _COMPOUND.finditer(text)]
    compound_flags = list(dict.fromkeys(compound_flags))
    meta_flags = [m.group(0).lower() for m in _META.finditer(text)]

    flags: list[str] = []
    spans: list[BiasSpan] = []

    codes = set(validation_codes or ())

    if emotion_terms or "E_EMO" in codes or "!" in text:
        flags.append("emotion")
        for term in emotion_terms:
            for m in re.finditer(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                spans.append(
                    BiasSpan(
                        start=m.start(),
                        end=m.end(),
                        reason=f"affect lexicon token: {m.group(0).lower()}",
                    )
                )

    if leading_modifiers or "E_LEAD" in codes:
        flags.append("leading")
        spans.extend(
            _spans_for(_LEAD_OPENER, text, "presupposition opener")
        )
        spans.extend(
            _spans_for(_LEAD_PREFERRED, text, "embedded preferred answer")
        )

    if meta_flags or "E_META" in codes:
        flags.append("meta")
        spans.extend(_spans_for(_META, text, "meta/process pollution"))

    # compound: two openers with joiner, or E_ATOM
    openers = list(_OPENER.finditer(text))
    if "E_ATOM" in codes or (
        len(openers) >= 2 and any(j in text.lower() for j in (" and ", " or ", " also ", " plus "))
    ):
        flags.append("compound")
        for m in _COMPOUND.finditer(text):
            spans.append(
                BiasSpan(
                    start=m.start(),
                    end=m.end(),
                    reason="coordinating join of two interrogative clauses",
                )
            )

    if "E_LEN" in codes:
        flags.append("length")

    if "E_WH" in codes:
        flags.append("non_wh")

    if "E_FACT" in codes:
        flags.append("missing_fact_ref")

    flags = list(dict.fromkeys(flags))

    notes = freeform_affect
    return BiasQuarantine(
        flags=flags,
        spans=spans,
        notes=notes,
        emotion_terms=emotion_terms,
        leading_modifiers=leading_modifiers,
        compound_flags=compound_flags,
        meta_flags=meta_flags,
        freeform_affect=freeform_affect,
    )
