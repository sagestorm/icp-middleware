"""Record assembly against interrogative.collection.v1 shape."""

from __future__ import annotations

from icp_middleware import PROTOCOL_VERSION_STR, build_record


def test_build_record_fields() -> None:
    record = build_record(
        interrogative_raw="What happened during the outage window?",
        event_id="E-42",
        collection_config={
            "respondent_type": "ai_persona",
            "event_type": "technical_incident",
            "information_access": "identical_fact_sheet",
            "downstream": "python_clustering",
        },
        knowledge_condition_id="K-02",
        respondent_token="R-C3D4E5F6A1B2",
        fact_refs=["F-002"],
    )
    assert record["protocol_version"] == PROTOCOL_VERSION_STR
    assert record["validation"]["status"] == "accepted"
    assert record["validation"]["errors"] == []
    assert "gates_passed" in record["validation"]
    assert set(record["bias_quarantine"].keys()) >= {"flags", "spans"}
    assert record["respondent_token"].startswith("R-")
    assert len(record["respondent_token"]) == 14
