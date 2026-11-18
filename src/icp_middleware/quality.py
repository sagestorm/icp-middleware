"""Acceptance helpers for ICP record quality (beyond gate plumbing)."""

from __future__ import annotations

from typing import Any, Mapping

from icp_middleware.constants import INFORMATION_ACCESS_ASYMMETRIC
from icp_middleware.validate import matches_banal_template, validate_interrogative


def assert_record_quality(
    record: Mapping[str, Any],
    fact_sheet_text: str | None = None,
) -> None:
    """Raise ``AssertionError`` when an accepted record fails the quality bar.

    Checks:
    - ``validation.status`` is ``accepted``
    - re-running ``E_SPEC`` (and sibling gates) would still pass
    - under asymmetric access, ``fact_refs`` is non-empty
    - interrogative is not a banal / generic template
    """
    validation = record.get("validation") or {}
    status = validation.get("status")
    if status != "accepted":
        raise AssertionError(f"expected accepted record, got status={status!r}")

    raw = str(record.get("interrogative_raw") or "")
    if matches_banal_template(raw):
        raise AssertionError(f"banal interrogative rejected by quality bar: {raw!r}")

    config = record.get("collection_config") or {}
    access = str(config.get("information_access") or "")
    refs = list(record.get("fact_refs") or [])
    if access == INFORMATION_ACCESS_ASYMMETRIC and not refs:
        raise AssertionError("asymmetric record missing non-empty fact_refs")

    result = validate_interrogative(
        raw,
        information_access=access,
        fact_refs=refs,
        fact_sheet_text=fact_sheet_text,
    )
    if not result.passed:
        raise AssertionError(
            f"record fails re-validation: codes={list(result.codes)}"
        )
    if "E_SPEC" in result.codes:
        raise AssertionError("E_SPEC failed on quality re-check")
