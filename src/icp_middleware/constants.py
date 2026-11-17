"""Protocol version and normative constants for ICP middleware."""

from __future__ import annotations

# Integer product constant; wire format uses PROTOCOL_VERSION_STR.
PROTOCOL_VERSION = 1
PROTOCOL_VERSION_STR = "1.0"

ERROR_CODES = (
    "E_ATOM",
    "E_WH",
    "E_EMO",
    "E_LEAD",
    "E_LEN",
    "E_META",
    "E_FACT",
)

ERROR_MESSAGES = {
    "E_ATOM": (
        "Interrogative must contain exactly one atomic question; "
        "compound coordination detected."
    ),
    "E_WH": "Interrogative must open with an allowed wh- or auxiliary form.",
    "E_EMO": "Interrogative contains affective or insulting load forbidden by E_EMO.",
    "E_LEAD": "Interrogative embeds a leading presupposition forbidden by E_LEAD.",
    "E_LEN": (
        "Interrogative length must be between 12 and 280 Unicode scalars "
        "inclusive after trim."
    ),
    "E_META": (
        "Interrogative targets the collection instrument or process rather "
        "than the event."
    ),
    "E_FACT": (
        "fact_refs MUST be non-empty when information_access is "
        "asymmetric_role_packs."
    ),
}

WH_TOKENS = frozenset(
    {
        "who",
        "what",
        "when",
        "where",
        "why",
        "which",
        "how",
        "whose",
        "whom",
    }
)
AUX_TOKENS = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "do",
        "does",
        "did",
        "can",
        "could",
        "would",
        "should",
        "has",
        "have",
        "had",
        "will",
        "may",
        "might",
    }
)

EMO_LEXICON = frozenset(
    {
        "angry",
        "furious",
        "outrageous",
        "terrible",
        "awful",
        "horrible",
        "disgusting",
        "hate",
        "stupid",
        "idiot",
        "incompetent",
        "shocking",
        "appalling",
    }
)

EMO_EXTENDED = frozenset(
    {
        "upset",
        "frustrated",
        "unfair",
        "ridiculous",
        "hurt",
        "betrayed",
        "scared",
        "love",
        "clearly",
        "obviously",
        "surely",
        "frankly",
        "honestly",
    }
)

MIN_LEN = 12
MAX_LEN = 280

INFORMATION_ACCESS_IDENTICAL = "identical_fact_sheet"
INFORMATION_ACCESS_ASYMMETRIC = "asymmetric_role_packs"

FORBIDDEN_EXPORT_FIELDS = frozenset(
    {
        "interrogative_raw",
        "bias_quarantine",
        "respondent_token",
        "respondent_channel",
        "submitted_at_utc",
        "record_id",
        "validation",
        "freeform_affect",
        "notes",
    }
)
