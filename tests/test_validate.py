"""Validation error-code coverage (SPEC §5)."""

from __future__ import annotations

from icp_middleware import validate_interrogative


def test_happy_path() -> None:
    result = validate_interrogative(
        "What service failed first during the outage?",
        information_access="identical_fact_sheet",
    )
    assert result.passed
    assert result.codes == ()
    assert result.status == "accepted"
    assert set(result.gates_passed) == {
        "E_ATOM",
        "E_WH",
        "E_EMO",
        "E_LEAD",
        "E_LEN",
        "E_META",
        "E_FACT",
    }


def test_e_atom_multiple_questions() -> None:
    result = validate_interrogative(
        "What failed? Who noticed?",
        information_access="identical_fact_sheet",
    )
    assert "E_ATOM" in result.codes


def test_e_atom_compound_and() -> None:
    result = validate_interrogative(
        "What failed and who approved the rollback?",
        information_access="identical_fact_sheet",
    )
    assert "E_ATOM" in result.codes


def test_e_atom_semicolon_stack() -> None:
    result = validate_interrogative(
        "What failed; who was on call?",
        information_access="identical_fact_sheet",
    )
    assert "E_ATOM" in result.codes


def test_e_wh() -> None:
    result = validate_interrogative(
        "Tell me about the outage timeline please?",
        information_access="identical_fact_sheet",
    )
    assert "E_WH" in result.codes


def test_e_emo() -> None:
    result = validate_interrogative(
        "Why was this terrible outage allowed to happen?",
        information_access="identical_fact_sheet",
    )
    assert "E_EMO" in result.codes


def test_e_emo_exclamation() -> None:
    result = validate_interrogative(
        "What happened during the outage window!",
        information_access="identical_fact_sheet",
    )
    assert "E_EMO" in result.codes


def test_e_lead() -> None:
    result = validate_interrogative(
        "Why didn't you stop the cover-up before publication?",
        information_access="identical_fact_sheet",
    )
    assert "E_LEAD" in result.codes


def test_e_len_short_fixture() -> None:
    """Protocol fixture 05: `What broke?` is 11 scalars → E_LEN."""
    text = "What broke?"
    assert len(text.strip()) == 11
    result = validate_interrogative(text, information_access="identical_fact_sheet")
    assert "E_LEN" in result.codes


def test_e_len_long() -> None:
    long_q = "What " + ("x" * 300) + "?"
    result = validate_interrogative(long_q, information_access="identical_fact_sheet")
    assert "E_LEN" in result.codes


def test_e_meta() -> None:
    result = validate_interrogative(
        "What are you looking for in this survey?",
        information_access="identical_fact_sheet",
    )
    assert "E_META" in result.codes


def test_e_fact_missing_refs() -> None:
    result = validate_interrogative(
        "When did the escalation meeting begin?",
        information_access="asymmetric_role_packs",
        fact_refs=[],
    )
    assert "E_FACT" in result.codes


def test_e_fact_bad_pattern() -> None:
    result = validate_interrogative(
        "When did the escalation meeting begin?",
        information_access="identical_fact_sheet",
        fact_refs=["FACT1"],
    )
    assert "E_FACT" in result.codes


def test_e_fact_happy() -> None:
    result = validate_interrogative(
        "What changed in the deployment pipeline today?",
        information_access="asymmetric_role_packs",
        fact_ids_allowed=["F-001", "F-002"],
        fact_refs=["F-001"],
    )
    assert result.passed
