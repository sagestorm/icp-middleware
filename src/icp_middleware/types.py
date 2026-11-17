"""Typed result and packet structures for ICP middleware."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of interrogative validation (Python + protocol shapes)."""

    passed: bool
    codes: tuple[str, ...] = ()
    status: str = "accepted"
    errors: tuple[dict[str, str], ...] = ()
    gates_passed: tuple[str, ...] = ()
    protocol_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        """Protocol validation object (SPEC §5.8)."""
        return {
            "status": self.status,
            "errors": [dict(e) for e in self.errors],
            "gates_passed": list(self.gates_passed),
        }


@dataclass
class BiasSpan:
    start: int
    end: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "reason": self.reason}


@dataclass
class BiasQuarantine:
    """Protocol bias_quarantine plus extraction convenience fields."""

    flags: list[str] = field(default_factory=list)
    spans: list[BiasSpan] = field(default_factory=list)
    notes: str | None = None
    # Convenience extraction (not serialized into protocol record by default)
    emotion_terms: list[str] = field(default_factory=list)
    leading_modifiers: list[str] = field(default_factory=list)
    compound_flags: list[str] = field(default_factory=list)
    meta_flags: list[str] = field(default_factory=list)
    freeform_affect: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "flags": list(self.flags),
            "spans": [s.to_dict() for s in self.spans],
        }
        if self.notes is not None:
            data["notes"] = self.notes
        return data


@dataclass
class AnalysisUnit:
    """One blinded review unit (analysis.packet.v1)."""

    unit_id: str
    protocol_version: str
    event_id: str
    interrogative_normalized: str
    fact_refs: list[str]
    knowledge_condition_id: str
    collection_config: dict[str, Any]
    submitted_on_utc: str
    ordinal: int | None = None  # steward helper; omitted from protocol dict

    @property
    def review_unit_id(self) -> str:
        """Alias for older call sites; schema field is ``unit_id``."""
        return self.unit_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "protocol_version": self.protocol_version,
            "event_id": self.event_id,
            "interrogative_normalized": self.interrogative_normalized,
            "fact_refs": list(self.fact_refs),
            "knowledge_condition_id": self.knowledge_condition_id,
            "collection_config": {
                "event_type": self.collection_config["event_type"],
                "downstream": self.collection_config["downstream"],
            },
            "submitted_on_utc": self.submitted_on_utc,
        }


@dataclass
class AnalysisPacket:
    """Blind-review export packet (analysis.packet.v1)."""

    review_packet_id: str
    protocol_version: str
    profile: str
    units: list[AnalysisUnit]
    created_at_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "review_packet_id": self.review_packet_id,
            "protocol_version": self.protocol_version,
            "profile": self.profile,
            "units": [u.to_dict() for u in self.units],
        }
        if self.created_at_utc is not None:
            data["created_at_utc"] = self.created_at_utc
        return data


@dataclass
class CodingKey:
    """Steward-only sealed coding key (coding.key.v1)."""

    review_packet_id: str
    protocol_version: str
    created_at_utc: str
    shuffle_seed: str | int
    respondent_map: dict[str, str]
    knowledge_map: dict[str, str]
    fact_map: dict[str, str]
    record_map: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "review_packet_id": self.review_packet_id,
            "protocol_version": self.protocol_version,
            "created_at_utc": self.created_at_utc,
            "shuffle_seed": self.shuffle_seed,
            "respondent_map": dict(self.respondent_map),
            "knowledge_map": dict(self.knowledge_map),
            "fact_map": dict(self.fact_map),
        }
        if self.record_map:
            data["record_map"] = dict(self.record_map)
        return data
