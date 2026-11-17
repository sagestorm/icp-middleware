"""LLM persona intake: mock provider, retry, and blind export."""

from __future__ import annotations

import json
import random

from icp_middleware.llm_intake import (
    EventPack,
    MockProvider,
    PersonaSpec,
    collect_persona_interrogative,
    parse_interrogative_payload,
    run_llm_intake,
)


def _asymmetric_pack() -> EventPack:
    return EventPack(
        event_id="evt-test-1",
        event_type="technical_incident",
        shared_facts=("F-000: Checkout API elevated 5xx.",),
        information_access="asymmetric_role_packs",
        personas=(
            PersonaSpec(
                persona_id="sre",
                knowledge_condition_id="K-01",
                fact_ids=("F-001", "F-002"),
                fact_sheet_lines=(
                    "payments-api restart loop at 14:02 UTC.",
                    "First page at 14:04 UTC.",
                ),
                role_label_steward_only="SRE on-call",
            ),
            PersonaSpec(
                persona_id="product",
                knowledge_condition_id="K-02",
                fact_ids=("F-010",),
                fact_sheet_lines=(
                    "Checkout UI error rate rose above 8%.",
                ),
                role_label_steward_only="Product owner",
            ),
            PersonaSpec(
                persona_id="support",
                knowledge_condition_id="K-03",
                fact_ids=("F-020",),
                fact_sheet_lines=(
                    "Support logged login-failure tickets at 14:07 UTC.",
                ),
                role_label_steward_only="Support lead",
            ),
        ),
    )


FORBIDDEN_UNIT_FIELDS = {
    "interrogative_raw",
    "bias_quarantine",
    "respondent_token",
    "respondent_channel",
    "submitted_at_utc",
    "record_id",
    "validation",
}


def test_mock_provider_produces_accepted_records() -> None:
    pack = _asymmetric_pack()
    provider = MockProvider()
    records, packet, key = run_llm_intake(pack, provider, max_attempts=3)
    assert len(records) == 3
    assert all(r["validation"]["status"] == "accepted" for r in records)
    assert all(r["collection_config"]["respondent_type"] == "ai_persona" for r in records)
    assert all(r["fact_refs"] for r in records)
    assert packet is not None
    assert key is not None
    assert len(packet.units) == 3
    assert set(key.respondent_map.values()) == {
        "SRE on-call",
        "Product owner",
        "Support lead",
    }


def test_retry_polluted_then_clean() -> None:
    pack = EventPack(
        event_id="evt-retry",
        event_type="technical_incident",
        information_access="asymmetric_role_packs",
        personas=(
            PersonaSpec(
                persona_id="sre",
                knowledge_condition_id="K-01",
                fact_ids=("F-001",),
                fact_sheet_lines=("payments-api restart loop at 14:02 UTC.",),
                role_label_steward_only="SRE",
            ),
        ),
    )
    provider = MockProvider(
        polluted_then_clean=True,
        default_interrogative="What service failed first during the outage?",
    )
    record = collect_persona_interrogative(provider, pack, pack.personas[0])
    assert record is not None
    assert record["validation"]["status"] == "accepted"
    assert record["interrogative_raw"] == (
        "What service failed first during the outage?"
    )
    assert provider._attempt == 2


def test_blind_export_strips_respondent_identity() -> None:
    pack = _asymmetric_pack()
    provider = MockProvider()
    records, packet, key = run_llm_intake(pack, provider)
    assert packet is not None and key is not None
    # Re-seal with fixed rng for stable assertions on structure only
    from icp_middleware import export_and_seal

    packet2, _key2 = export_and_seal(
        records,
        persona_map={
            r["respondent_token"]: "label" for r in records
        },
        rng=random.Random(0),
    )
    for unit in packet2.to_dict()["units"]:
        assert FORBIDDEN_UNIT_FIELDS.isdisjoint(unit.keys())
        assert "respondent_token" not in unit
        assert "respondent_channel" not in unit
        assert set(unit["collection_config"].keys()) == {
            "event_type",
            "downstream",
        }
    # Coding key retains steward maps; blind packet does not
    assert key.respondent_map
    packet_blob = json.dumps(packet.to_dict())
    for token in key.respondent_map:
        assert token not in packet_blob


def test_parse_fenced_json() -> None:
    raw = '```json\n{"interrogative": "What failed first during the outage?"}\n```'
    text, err = parse_interrogative_payload(raw)
    assert err is None
    assert text == "What failed first during the outage?"


def test_parse_fail_retries_then_none() -> None:
    pack = EventPack(
        event_id="evt-parse",
        event_type="technical_incident",
        information_access="asymmetric_role_packs",
        personas=(
            PersonaSpec(
                persona_id="sre",
                knowledge_condition_id="K-01",
                fact_ids=("F-001",),
                fact_sheet_lines=("payments-api restart loop.",),
                role_label_steward_only="SRE",
            ),
        ),
    )
    provider = MockProvider(
        scripted={
            1: "not json at all",
            2: "still broken",
            3: '{"nope": true}',
        }
    )
    record = collect_persona_interrogative(
        provider, pack, pack.personas[0], max_attempts=3
    )
    assert record is None
