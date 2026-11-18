"""LLM persona intake: one fact pack → one interrogative → ICP record."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from icp_middleware.constants import (
    INFORMATION_ACCESS_ASYMMETRIC,
    INFORMATION_ACCESS_IDENTICAL,
)
from icp_middleware.export import export_and_seal
from icp_middleware.normalize import normalize_interrogative
from icp_middleware.quarantine import quarantine_bias
from icp_middleware.record import build_record
from icp_middleware.types import AnalysisPacket, CodingKey
from icp_middleware.validate import validate_interrogative

SYSTEM_PROMPT = """\
You are an ICP (Interrogative Collection Protocol) respondent.

Emit exactly one atomic interrogative about the single event described in the
user message. Rules:
- Exactly one question; no compound coordination (and/or/also joining clauses).
- Open with an allowed wh- or auxiliary form (who/what/when/where/why/which/
  how/whose/whom or is/are/was/were/do/does/did/can/…).
- No emotion, insults, or exclamation marks (E_EMO).
- No leading presuppositions or preferred answers (E_LEAD).
- No meta questions about the survey, prompt, AI, or process (E_META).
- Length after trim: 12–280 Unicode scalars.
- Seek concrete, fact-grounded information (E_SPEC). Do NOT ask generic
  questions like "What event is being described?" or "What happened?".
- Cite only facts listed in your pack via fact_refs; do not invent external
  knowledge. fact_refs MUST be a non-empty subset of your allowed F-### ids
  when information_access is asymmetric_role_packs.

Respond with JSON only — no prose, no markdown fences:
{"interrogative": "<your single question ending with ?>", "fact_refs": ["F-001"]}
"""

_RETRY_TAIL = "emit one clean interrogative as JSON with fact_refs"
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_JSON_OBJ_RE = re.compile(r"\{[\s\S]*\}")
_FACT_ID_LINE_RE = re.compile(r"^- (F-[0-9]{3})(?::|\s|$)", re.MULTILINE)
_FACT_LINE_RE = re.compile(r"^- (F-[0-9]{3}):\s*(.+)$", re.MULTILINE)
_FACT_REF_RE = re.compile(r"^F-[0-9]{3}$")
_ALLOWED_PACK_MARKER = "Your allowed fact pack"


@dataclass(frozen=True)
class PersonaSpec:
    """One AI persona and its allowed fact pack for a shared event."""

    persona_id: str
    knowledge_condition_id: str
    fact_ids: tuple[str, ...]
    fact_sheet_lines: tuple[str, ...]
    role_label_steward_only: str


@dataclass(frozen=True)
class EventPack:
    """Shared event plus per-persona knowledge conditions."""

    event_id: str
    event_type: str
    shared_facts: tuple[str, ...] = ()
    personas: tuple[PersonaSpec, ...] = ()
    information_access: str = INFORMATION_ACCESS_ASYMMETRIC
    downstream: str = "manual_blind_review"
    respondent_type: str = "ai_persona"

    def collection_config(self) -> dict[str, str]:
        return {
            "respondent_type": self.respondent_type,
            "event_type": self.event_type,
            "information_access": self.information_access,
            "downstream": self.downstream,
        }


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal chat completion surface (system + user → text)."""

    def complete(self, system: str, user: str) -> str: ...


_KCID_RE = re.compile(
    r"knowledge_condition_id:\s*(K-[0-9]{2})",
    re.IGNORECASE,
)

_DEFAULT_BY_KNOWLEDGE: dict[str, str] = {
    "K-01": "What caused the payments-api restart loop at 14:02 UTC?",
    "K-02": "When did the Checkout UI error rate rise above 8%?",
    "K-03": "When did Support first log the login-failure tickets?",
}


def _allowed_pack_section(user: str) -> str:
    idx = user.find(_ALLOWED_PACK_MARKER)
    return user[idx:] if idx >= 0 else user


def _fact_ids_from_user(user: str) -> list[str]:
    return _FACT_ID_LINE_RE.findall(_allowed_pack_section(user))


def _grounded_interrogative_from_user(user: str) -> str | None:
    """Build a fact-grounded question from the first allowed pack line."""
    lines = _FACT_LINE_RE.findall(_allowed_pack_section(user))
    if not lines:
        return None
    _fid, sheet = lines[0]
    sheet = sheet.strip().rstrip(".")
    if not sheet:
        return None
    return f"What is known about {sheet}?"


def _payload_json(interrogative: str, fact_refs: Sequence[str]) -> str:
    return json.dumps({"interrogative": interrogative, "fact_refs": list(fact_refs)})


@dataclass
class MockProvider:
    """Deterministic offline provider for demos and tests.

    ``scripted`` maps attempt index (1-based) to raw model text. When a key is
    missing, a clean interrogative is chosen from ``default_interrogative``,
    ``by_knowledge``, or a built-in map keyed by ``knowledge_condition_id`` in
    the user message. Pass ``polluted_then_clean=True`` to emit an
    E_EMO/E_LEAD question on attempt 1 and a clean question afterward.

    Clean responses include a **subset** of allowed ``fact_refs`` parsed from
    the user message (first id only) — never the full pack by default.
    """

    scripted: Mapping[int, str] = field(default_factory=dict)
    default_interrogative: str | None = None
    by_knowledge: Mapping[str, str] = field(default_factory=dict)
    polluted_then_clean: bool = False
    polluted_interrogative: str = (
        "Why didn't you stop this terrible cover-up before publication?"
    )
    polluted_fact_refs: tuple[str, ...] = ()
    _attempt: int = field(default=0, init=False, repr=False)

    def complete(self, system: str, user: str) -> str:
        _ = system
        self._attempt += 1
        attempt = self._attempt
        if attempt in self.scripted:
            return self.scripted[attempt]
        allowed = _fact_ids_from_user(user)
        if self.polluted_then_clean and attempt == 1:
            refs = list(self.polluted_fact_refs)
            return _payload_json(self.polluted_interrogative, refs)
        clean = self._clean_for_user(user)
        # Subset: first allowed id only (model-emitted, not full pack).
        refs = allowed[:1]
        return _payload_json(clean, refs)

    def _clean_for_user(self, user: str) -> str:
        if self.default_interrogative is not None:
            return self.default_interrogative
        match = _KCID_RE.search(user)
        if match:
            kid = match.group(1).upper()
            if kid in self.by_knowledge:
                return self.by_knowledge[kid]
        # Prefer pack-line grounding so non-outage events (e.g. policy) pass E_SPEC.
        grounded = _grounded_interrogative_from_user(user)
        if grounded is not None:
            return grounded
        if match:
            kid = match.group(1).upper()
            if kid in _DEFAULT_BY_KNOWLEDGE:
                return _DEFAULT_BY_KNOWLEDGE[kid]
        return "What caused the payments-api restart loop at 14:02 UTC?"

    def reset(self) -> None:
        self._attempt = 0


@dataclass
class OpenAICompatibleProvider:
    """Chat Completions client via stdlib ``urllib`` (optional live path)."""

    api_key: str
    base_url: str = "https://api.openai.com"
    model: str = "gpt-4o-mini"
    timeout_s: float = 60.0

    def complete(self, system: str, user: str) -> str:
        # Accept either host root or an OpenAI-style ".../v1" root (NVIDIA NIM).
        root = self.base_url.rstrip("/")
        if root.endswith("/v1"):
            url = f"{root}/chat/completions"
        else:
            url = f"{root}/v1/chat/completions"
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAI-compatible HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI-compatible request failed: {exc}") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected completions payload: {payload!r}"
            ) from exc
        if not isinstance(content, str):
            raise RuntimeError("message.content was not a string")
        return content


@dataclass
class LiveRetryProbeProvider:
    """Prove live retry: attempt 1 is local pollution; attempt 2+ hits ``inner``.

    Call :meth:`reset` between personas (``run_llm_intake`` does this). After a
    full run, inspect ``persona_attempts``, ``probe_calls``, and
    ``network_calls`` to confirm the first attempt never touched the network.
    """

    inner: LLMProvider
    polluted_interrogative: str = (
        "Why didn't you stop this terrible cover-up before publication?"
    )
    polluted_fact_refs: tuple[str, ...] = ("F-999",)
    _attempt: int = field(default=0, init=False, repr=False)
    probe_calls: int = field(default=0, init=False)
    network_calls: int = field(default=0, init=False)
    persona_attempts: list[int] = field(default_factory=list, init=False)

    def complete(self, system: str, user: str) -> str:
        self._attempt += 1
        if self._attempt == 1:
            self.probe_calls += 1
            return _payload_json(
                self.polluted_interrogative,
                self.polluted_fact_refs,
            )
        self.network_calls += 1
        return self.inner.complete(system, user)

    def reset(self) -> None:
        if self._attempt:
            self.persona_attempts.append(self._attempt)
        self._attempt = 0

    def summary(self) -> dict[str, Any]:
        attempts = list(self.persona_attempts)
        if self._attempt:
            attempts = attempts + [self._attempt]
        return {
            "probe_calls": self.probe_calls,
            "network_calls": self.network_calls,
            "persona_attempts": attempts,
        }


def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_interrogative_payload(
    raw: str,
) -> tuple[str | None, list[str] | None, str | None]:
    """Extract ``interrogative`` and ``fact_refs`` from model text.

    Returns ``(interrogative, fact_refs, None)`` on success or
    ``(None, None, "PARSE_FAIL")`` on failure.
    """
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        obj_match = _JSON_OBJ_RE.search(cleaned)
        if not obj_match:
            return None, None, "PARSE_FAIL"
        try:
            data = json.loads(obj_match.group(0))
        except json.JSONDecodeError:
            return None, None, "PARSE_FAIL"
    if not isinstance(data, dict):
        return None, None, "PARSE_FAIL"
    value = data.get("interrogative")
    if not isinstance(value, str) or not value.strip():
        return None, None, "PARSE_FAIL"
    refs_raw = data.get("fact_refs", [])
    if refs_raw is None:
        refs_raw = []
    if not isinstance(refs_raw, list):
        return None, None, "PARSE_FAIL"
    refs: list[str] = []
    for item in refs_raw:
        if not isinstance(item, str) or not _FACT_REF_RE.match(item):
            return None, None, "PARSE_FAIL"
        refs.append(item)
    return value.strip(), refs, None


def persona_fact_sheet_text(
    event_pack: EventPack,
    persona: PersonaSpec,
) -> str:
    """Join shared facts + persona fact lines for E_SPEC grounding."""
    parts = [line for line in event_pack.shared_facts if line]
    parts.extend(line for line in persona.fact_sheet_lines if line)
    return "\n".join(parts)


def _fact_sheet_user_message(
    event_pack: EventPack,
    persona: PersonaSpec,
) -> str:
    lines: list[str] = [
        f"event_id: {event_pack.event_id}",
        f"event_type: {event_pack.event_type}",
        f"knowledge_condition_id: {persona.knowledge_condition_id}",
        f"information_access: {event_pack.information_access}",
        "",
        "Shared facts:",
    ]
    if event_pack.shared_facts:
        lines.extend(f"- {line}" for line in event_pack.shared_facts)
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("Your allowed fact pack (cite only these F-### ids):")
    for fid, sheet in zip(persona.fact_ids, persona.fact_sheet_lines):
        lines.append(f"- {fid}: {sheet}")
    if len(persona.fact_ids) > len(persona.fact_sheet_lines):
        for fid in persona.fact_ids[len(persona.fact_sheet_lines) :]:
            lines.append(f"- {fid}")
    lines.append("")
    lines.append(
        'Return JSON only: {"interrogative": "...", "fact_refs": ["F-###", ...]}'
    )
    lines.append(
        "fact_refs MUST be a non-empty subset of your allowed ids under "
        "asymmetric_role_packs. Do not return the full pack unless every id "
        "is genuinely cited by the interrogative."
    )
    return "\n".join(lines)


def _retry_user_message(base_fact_sheet: str, codes: Sequence[str]) -> str:
    """Re-send the fact pack with codes only (no coaching / paraphrase)."""
    joined = ",".join(codes) if codes else "PARSE_FAIL"
    return f"{base_fact_sheet}\n\nValidation failed: {joined}\n{_RETRY_TAIL}"


def collect_persona_interrogative(
    provider: LLMProvider,
    event_pack: EventPack,
    persona: PersonaSpec,
    *,
    max_attempts: int = 3,
) -> dict[str, Any] | None:
    """Ask one persona for a single interrogative; validate with ≤ retries.

    On validation failure the next user message re-sends the fact pack plus
    error codes and a short emit instruction — no coaching or paraphrased
    rewrites. (Codes-only without the pack breaks single-turn providers that
    cannot recall prior ``fact_refs`` / sheet text.)

    ``fact_refs`` come from the model payload. Under asymmetric access they
    MUST be non-empty and ⊆ ``persona.fact_ids`` (enforced via ``E_FACT``).
    The pack is never silently substituted for model refs.
    """
    if max_attempts < 1:
        return None

    base_msg = _fact_sheet_user_message(event_pack, persona)
    user_msg = base_msg
    fact_ids_allowed = list(persona.fact_ids)
    fact_sheet_text = persona_fact_sheet_text(event_pack, persona)
    config = event_pack.collection_config()

    for _attempt in range(1, max_attempts + 1):
        raw = provider.complete(SYSTEM_PROMPT, user_msg)
        interrogative, fact_refs, parse_err = parse_interrogative_payload(raw)
        if parse_err is not None or interrogative is None or fact_refs is None:
            user_msg = _retry_user_message(base_msg, [parse_err or "PARSE_FAIL"])
            continue

        validation = validate_interrogative(
            interrogative,
            information_access=event_pack.information_access,
            fact_ids_allowed=fact_ids_allowed,
            fact_refs=fact_refs,
            fact_sheet_text=fact_sheet_text,
        )
        if not validation.passed:
            user_msg = _retry_user_message(base_msg, validation.codes)
            continue

        bias = quarantine_bias(
            interrogative,
            validation_codes=validation.codes,
        )
        _ = normalize_interrogative(
            interrogative,
            information_access=event_pack.information_access,
            fact_ids_allowed=fact_ids_allowed,
            fact_refs=fact_refs,
            fact_sheet_text=fact_sheet_text,
        )
        return build_record(
            interrogative_raw=interrogative,
            event_id=event_pack.event_id,
            collection_config=config,
            knowledge_condition_id=persona.knowledge_condition_id,
            fact_refs=fact_refs,
            fact_ids_allowed=fact_ids_allowed,
            fact_sheet_text=fact_sheet_text,
            validation=validation,
            bias_quarantine=bias,
            respondent_channel="llm_intake",
        )

    return None


def _maybe_reset_provider(provider: LLMProvider) -> None:
    reset = getattr(provider, "reset", None)
    if callable(reset):
        reset()


def run_llm_intake(
    event_pack: EventPack,
    provider: LLMProvider,
    *,
    max_attempts: int = 3,
) -> tuple[list[dict[str, Any]], AnalysisPacket | None, CodingKey | None]:
    """Collect interrogatives for all personas; blind-export accepted records."""
    records: list[dict[str, Any]] = []
    persona_map: dict[str, str] = {}
    knowledge_map: dict[str, str] = {}
    fact_map: dict[str, str] = {}

    for persona in event_pack.personas:
        _maybe_reset_provider(provider)
        record = collect_persona_interrogative(
            provider,
            event_pack,
            persona,
            max_attempts=max_attempts,
        )
        if record is None:
            continue
        records.append(record)
        persona_map[record["respondent_token"]] = persona.role_label_steward_only
        knowledge_map[persona.knowledge_condition_id] = (
            f"pack:{persona.persona_id}:{persona.role_label_steward_only}"
        )
        for fid, line in zip(persona.fact_ids, persona.fact_sheet_lines):
            fact_map.setdefault(fid, line)
        for fid in persona.fact_ids:
            fact_map.setdefault(fid, f"fact:{fid}")

    if not records:
        return [], None, None

    accepted = [
        r for r in records if r.get("validation", {}).get("status") == "accepted"
    ]
    if not accepted:
        return records, None, None

    packet, key = export_and_seal(
        accepted,
        persona_map=persona_map,
        knowledge_map=knowledge_map,
        fact_map=fact_map,
    )
    return records, packet, key


def event_pack_from_dict(data: Mapping[str, Any]) -> EventPack:
    """Load an :class:`EventPack` from a JSON-compatible mapping."""
    personas: list[PersonaSpec] = []
    for raw in data.get("personas") or ():
        personas.append(
            PersonaSpec(
                persona_id=str(raw["persona_id"]),
                knowledge_condition_id=str(raw["knowledge_condition_id"]),
                fact_ids=tuple(str(x) for x in raw.get("fact_ids") or ()),
                fact_sheet_lines=tuple(
                    str(x) for x in raw.get("fact_sheet_lines") or ()
                ),
                role_label_steward_only=str(raw["role_label_steward_only"]),
            )
        )
    access = str(
        data.get("information_access") or INFORMATION_ACCESS_ASYMMETRIC
    )
    if access not in (
        INFORMATION_ACCESS_IDENTICAL,
        INFORMATION_ACCESS_ASYMMETRIC,
    ):
        raise ValueError(f"unsupported information_access: {access!r}")
    return EventPack(
        event_id=str(data["event_id"]),
        event_type=str(data["event_type"]),
        shared_facts=tuple(str(x) for x in data.get("shared_facts") or ()),
        personas=tuple(personas),
        information_access=access,
        downstream=str(data.get("downstream") or "manual_blind_review"),
        respondent_type=str(data.get("respondent_type") or "ai_persona"),
    )


__all__ = [
    "SYSTEM_PROMPT",
    "EventPack",
    "LLMProvider",
    "LiveRetryProbeProvider",
    "MockProvider",
    "OpenAICompatibleProvider",
    "PersonaSpec",
    "collect_persona_interrogative",
    "event_pack_from_dict",
    "parse_interrogative_payload",
    "persona_fact_sheet_text",
    "run_llm_intake",
]
