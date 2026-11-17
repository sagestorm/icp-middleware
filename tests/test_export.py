"""Blind export field stripping (SPEC §7 / analysis.packet.v1)."""

from __future__ import annotations

import random

from icp_middleware import build_record, export_analysis_packet, export_and_seal


def _record(text: str, token: str) -> dict:
    return build_record(
        interrogative_raw=text,
        event_id="E-1",
        collection_config={
            "respondent_type": "human_web",
            "event_type": "technical_incident",
            "information_access": "identical_fact_sheet",
            "downstream": "manual_blind_review",
        },
        knowledge_condition_id="K-01",
        respondent_token=token,
        respondent_channel="web",
        fact_refs=["F-001"],
    )


FORBIDDEN = {
    "interrogative_raw",
    "bias_quarantine",
    "respondent_token",
    "respondent_channel",
    "submitted_at_utc",
    "record_id",
    "validation",
}


def test_export_schema_fields_and_stripping() -> None:
    records = [
        _record("What happened during the outage window?", "R-A1B2C3D4E5F6"),
        _record("When did the first alert fire on call?", "R-B2C3D4E5F6A1"),
    ]
    packet = export_analysis_packet(records, rng=random.Random(0))
    data = packet.to_dict()
    assert data["protocol_version"] == "1.0"
    assert data["profile"] == "manual_blind_review"
    assert "review_packet_id" in data
    assert len(data["units"]) == 2

    allowed_unit = {
        "unit_id",
        "protocol_version",
        "event_id",
        "interrogative_normalized",
        "fact_refs",
        "knowledge_condition_id",
        "collection_config",
        "submitted_on_utc",
    }
    for unit in data["units"]:
        assert set(unit.keys()) == allowed_unit
        assert FORBIDDEN.isdisjoint(unit.keys())
        assert set(unit["collection_config"].keys()) == {"event_type", "downstream"}
        assert len(unit["submitted_on_utc"]) == 10  # YYYY-MM-DD


def test_export_and_seal_align() -> None:
    records = [
        _record("What happened during the outage window?", "R-A1B2C3D4E5F6"),
        _record("When did the first alert fire on call?", "R-B2C3D4E5F6A1"),
    ]
    packet, key = export_and_seal(
        records,
        persona_map={"R-A1B2C3D4E5F6": "persona-1"},
        knowledge_map={"K-01": "pack:identical"},
        fact_map={"F-001": "line one"},
        rng=random.Random(2),
    )
    assert len(packet.units) == len(key.record_map)
    key_dict = key.to_dict()
    assert key_dict["protocol_version"] == "1.0"
    assert "respondent_map" in key_dict
    assert "shuffle_seed" in key_dict
    for unit in packet.units:
        assert unit.unit_id in key.record_map
