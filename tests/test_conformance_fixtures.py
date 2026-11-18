"""Conformance against protocol fixtures 01–11."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from icp_middleware import export_analysis_packet, validate_interrogative
from icp_middleware.schema_loader import load_schema

PROTOCOL_ROOT = Path(__file__).resolve().parents[2] / "interrogative-collection-protocol"
FIXTURES = PROTOCOL_ROOT / "conformance" / "fixtures"

FORBIDDEN_EXPORT = {
    "respondent_token",
    "respondent_channel",
    "interrogative_raw",
    "bias_quarantine",
    "validation",
    "record_id",
}


def _load_fixture(name: str) -> dict:
    path = FIXTURES / name
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="protocol fixtures not present")
@pytest.mark.parametrize(
    "filename",
    [
        "01-valid-atomic.json",
        "02-fail-compound-atom.json",
        "03-fail-emotion.json",
        "04-fail-leading.json",
        "05-fail-length.json",
        "06-fail-meta.json",
        "07-fail-missing-fact-ref-asymmetric.json",
        "09-fail-spec-generic.json",
        "10-fail-spec-ungrounded.json",
        "11-valid-spec-grounded.json",
    ],
)
def test_fixtures_gate_codes(filename: str) -> None:
    path = FIXTURES / filename
    if not path.is_file():
        pytest.skip(f"fixture {filename} not present")
    fixture = _load_fixture(filename)
    record = fixture["record"]
    expect = fixture["expect"]
    access = record["collection_config"]["information_access"]
    context = fixture.get("context") or {}
    fact_sheet_text = context.get("fact_sheet_text")
    result = validate_interrogative(
        record["interrogative_raw"],
        information_access=access,
        fact_refs=record.get("fact_refs") or [],
        fact_sheet_text=fact_sheet_text,
    )
    expected_codes = list(expect.get("error_codes") or [])
    assert list(result.codes) == expected_codes
    if expect.get("validation_status") == "accepted":
        assert result.passed and result.status == "accepted"
    else:
        assert not result.passed and result.status == "rejected"


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="protocol fixtures not present")
def test_fixture_08_export_shape() -> None:
    fixture = _load_fixture("08-valid-full-record-analysis-export.json")
    record = fixture["record"]
    # Ensure source interrogative validates accepted
    result = validate_interrogative(
        record["interrogative_raw"],
        information_access=record["collection_config"]["information_access"],
        fact_refs=record["fact_refs"],
    )
    assert result.passed

    packet = export_analysis_packet(
        [record],
        review_packet_id=record.get("review_packet_id"),
        created_at_utc=fixture["expected_analysis_packet"]["created_at_utc"],
    )
    data = packet.to_dict()
    expected = fixture["expected_analysis_packet"]

    assert data["protocol_version"] == expected["protocol_version"]
    assert data["profile"] == expected["profile"]
    assert data["review_packet_id"] == expected["review_packet_id"]
    assert len(data["units"]) == 1

    unit = data["units"][0]
    exp_unit = expected["units"][0]
    for key in (
        "protocol_version",
        "event_id",
        "interrogative_normalized",
        "fact_refs",
        "knowledge_condition_id",
        "submitted_on_utc",
    ):
        assert unit[key] == exp_unit[key]
    assert unit["collection_config"] == exp_unit["collection_config"]
    assert FORBIDDEN_EXPORT.isdisjoint(unit.keys())
    for forbidden in fixture["expect"]["export_must_omit"]:
        assert forbidden not in unit
        assert forbidden not in data


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="protocol fixtures not present")
def test_schemas_loadable() -> None:
    for name in (
        "interrogative.collection.v1",
        "analysis.packet.v1",
        "coding.key.v1",
    ):
        schema = load_schema(name)
        assert schema is not None
        assert "$id" in schema
