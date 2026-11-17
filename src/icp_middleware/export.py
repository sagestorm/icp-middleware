"""Blind analysis packet export and steward coding-key seal (SPEC §7)."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Mapping, MutableSequence, Sequence
from datetime import datetime, timezone
from typing import Any

from icp_middleware.constants import PROTOCOL_VERSION_STR
from icp_middleware.types import AnalysisPacket, AnalysisUnit, CodingKey


def _csprng_fisher_yates(items: MutableSequence[Any], rng: Any | None = None) -> None:
    """In-place Fisher–Yates shuffle (CSPRNG by default)."""
    n = len(items)
    if rng is None:
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            items[i], items[j] = items[j], items[i]
        return
    for i in range(n - 1, 0, -1):
        j = rng.randrange(i + 1)
        items[i], items[j] = items[j], items[i]


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _date_round(submitted_at_utc: str | None) -> str:
    if not submitted_at_utc:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Accept ...Z or offset forms; take calendar date prefix
    return submitted_at_utc[:10]


def _is_accepted(record: Mapping[str, Any]) -> bool:
    validation = record.get("validation") or {}
    if isinstance(validation, Mapping):
        status = validation.get("status")
        if status is not None:
            return status == "accepted"
        if "passed" in validation:
            return bool(validation["passed"])
    return bool(record.get("interrogative_normalized"))


def _blind_collection_config(record: Mapping[str, Any]) -> dict[str, str]:
    cfg = record.get("collection_config") or {}
    return {
        "event_type": str(cfg.get("event_type", "other")),
        "downstream": str(cfg.get("downstream", "manual_blind_review")),
    }


def _build_blind_units(
    records: Sequence[Mapping[str, Any]],
    *,
    rng: Any | None = None,
) -> tuple[list[AnalysisUnit], list[dict[str, Any]], str | int]:
    eligible = [r for r in records if _is_accepted(r) and r.get("interrogative_normalized")]
    paired = list(eligible)
    shuffle_seed = getattr(rng, "seed_value", None)
    if shuffle_seed is None:
        shuffle_seed = secrets.token_hex(8)
    _csprng_fisher_yates(paired, rng=rng)

    units: list[AnalysisUnit] = []
    coding_meta: list[dict[str, Any]] = []
    for ordinal, record in enumerate(paired, start=1):
        unit_id = f"U-{uuid.uuid4().hex[:8].upper()}"
        cfg = _blind_collection_config(record)
        unit = AnalysisUnit(
            unit_id=unit_id,
            protocol_version=PROTOCOL_VERSION_STR,
            event_id=str(record["event_id"]),
            interrogative_normalized=str(record["interrogative_normalized"]),
            fact_refs=list(record.get("fact_refs") or []),
            knowledge_condition_id=str(record["knowledge_condition_id"]),
            collection_config=cfg,
            submitted_on_utc=_date_round(
                str(record["submitted_at_utc"])
                if record.get("submitted_at_utc")
                else None
            ),
            ordinal=ordinal,
        )
        units.append(unit)
        coding_meta.append(
            {
                "unit_id": unit_id,
                "ordinal": ordinal,
                "record_id": record.get("record_id"),
                "respondent_token": record.get("respondent_token"),
                "knowledge_condition_id": record.get("knowledge_condition_id"),
                "fact_refs": list(record.get("fact_refs") or []),
            }
        )
    return units, coding_meta, shuffle_seed


def export_analysis_packet(
    records: Sequence[Mapping[str, Any]],
    *,
    rng: Any | None = None,
    review_packet_id: str | None = None,
    profile: str = "manual_blind_review",
    created_at_utc: str | None = None,
) -> AnalysisPacket:
    """Build a blind analysis packet (analysis.packet.v1 field names)."""
    units, _, _ = _build_blind_units(records, rng=rng)
    return AnalysisPacket(
        review_packet_id=review_packet_id or f"pkt-{uuid.uuid4().hex[:12]}",
        protocol_version=PROTOCOL_VERSION_STR,
        profile=profile,
        units=units,
        created_at_utc=created_at_utc or _utc_now_iso(),
    )


def seal_coding_key(
    records: Sequence[Mapping[str, Any]],
    persona_map: Mapping[str, Any],
    *,
    rng: Any | None = None,
    review_packet_id: str | None = None,
    knowledge_map: Mapping[str, str] | None = None,
    fact_map: Mapping[str, str] | None = None,
    created_at_utc: str | None = None,
) -> CodingKey:
    """Seal a steward-only coding key (coding.key.v1).

    ``persona_map`` is treated as ``respondent_map`` (token → label).
    """
    packet, key = export_and_seal(
        records,
        persona_map,
        rng=rng,
        review_packet_id=review_packet_id,
        knowledge_map=knowledge_map,
        fact_map=fact_map,
        created_at_utc=created_at_utc,
    )
    _ = packet
    return key


def export_and_seal(
    records: Sequence[Mapping[str, Any]],
    persona_map: Mapping[str, Any],
    *,
    rng: Any | None = None,
    review_packet_id: str | None = None,
    knowledge_map: Mapping[str, str] | None = None,
    fact_map: Mapping[str, str] | None = None,
    created_at_utc: str | None = None,
) -> tuple[AnalysisPacket, CodingKey]:
    """Export a blind packet and matching steward coding key in one shuffle."""
    units, coding_meta, shuffle_seed = _build_blind_units(records, rng=rng)
    pkt_id = review_packet_id or f"pkt-{uuid.uuid4().hex[:12]}"
    created = created_at_utc or _utc_now_iso()
    packet = AnalysisPacket(
        review_packet_id=pkt_id,
        protocol_version=PROTOCOL_VERSION_STR,
        profile="manual_blind_review",
        units=units,
        created_at_utc=created,
    )

    respondent_map = {str(k): str(v) for k, v in persona_map.items()}
    # Fill maps from records when not supplied
    k_map: dict[str, str] = dict(knowledge_map or {})
    f_map: dict[str, str] = dict(fact_map or {})
    for meta in coding_meta:
        kid = meta.get("knowledge_condition_id")
        if kid and kid not in k_map:
            k_map[str(kid)] = f"pack:{kid}"
        for fr in meta.get("fact_refs") or []:
            if fr not in f_map:
                f_map[str(fr)] = f"fact:{fr}"

    # Schema requires minProperties: 1 on maps — ensure placeholders if empty
    if not respondent_map and coding_meta:
        tok = coding_meta[0].get("respondent_token")
        if tok:
            respondent_map[str(tok)] = "unlabeled"
    if not k_map:
        k_map["K-00"] = "unspecified"
    if not f_map:
        f_map["F-000"] = "unspecified"

    record_map = {
        str(m["unit_id"]): str(m["record_id"])
        for m in coding_meta
        if m.get("unit_id") and m.get("record_id")
    }

    key = CodingKey(
        review_packet_id=pkt_id,
        protocol_version=PROTOCOL_VERSION_STR,
        created_at_utc=created,
        shuffle_seed=shuffle_seed if isinstance(shuffle_seed, (str, int)) else str(shuffle_seed),
        respondent_map=respondent_map,
        knowledge_map=k_map,
        fact_map=f_map,
        record_map=record_map,
    )
    return packet, key
