"""Quarantine and normalize behavior."""

from __future__ import annotations

from icp_middleware import normalize_interrogative, quarantine_bias


def test_quarantine_protocol_shape() -> None:
    q = quarantine_bias(
        "Why didn't you stop the cover-up before publication?",
        validation_codes=["E_LEAD"],
    )
    assert "leading" in q.flags
    assert q.to_dict()["flags"]
    assert "spans" in q.to_dict()


def test_normalize_happy() -> None:
    out = normalize_interrogative(
        "  How was the failover decision communicated to on-call?  "
    )
    assert out == "How was the failover decision communicated to on-call?"


def test_normalize_rejects_invalid() -> None:
    assert normalize_interrogative("What broke?") is None


def test_normalize_no_paraphrase() -> None:
    text = "What service failed first during the outage?"
    assert normalize_interrogative(text) == text
