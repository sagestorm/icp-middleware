"""Assemble full ICP collection records (interrogative.collection.v1)."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from icp_middleware.constants import PROTOCOL_VERSION_STR
from icp_middleware.normalize import normalize_surface
from icp_middleware.quarantine import quarantine_bias
from icp_middleware.types import BiasQuarantine, ValidationResult
from icp_middleware.validate import validate_interrogative


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def new_respondent_token() -> str:
    """Opaque ``R-[A-Z0-9]{12}`` token."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    body = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"R-{body}"


def build_record(
    *,
    interrogative_raw: str,
    event_id: str,
    collection_config: dict[str, Any],
    knowledge_condition_id: str,
    respondent_token: str | None = None,
    fact_refs: Sequence[str] | None = None,
    fact_ids_allowed: Sequence[str] | None = None,
    freeform_affect: str | None = None,
    respondent_channel: str | None = None,
    review_packet_id: str | None = None,
    record_id: str | None = None,
    submitted_at_utc: str | None = None,
    validation: ValidationResult | None = None,
    bias_quarantine: BiasQuarantine | None = None,
) -> dict[str, Any]:
    """Assemble a protocol-shaped ICP collection record."""
    information_access = str(
        collection_config.get("information_access", "identical_fact_sheet")
    )
    refs = list(fact_refs or ())

    if validation is None:
        validation = validate_interrogative(
            interrogative_raw,
            information_access=information_access,
            fact_ids_allowed=fact_ids_allowed,
            fact_refs=refs,
        )

    if bias_quarantine is None:
        bias_quarantine = quarantine_bias(
            interrogative_raw,
            freeform_affect=freeform_affect,
            validation_codes=validation.codes,
        )
    elif freeform_affect is not None and bias_quarantine.notes is None:
        bias_quarantine.notes = freeform_affect

    # SPEC: normalized is cleaning-only transform even on rejected records
    normalized = normalize_surface(interrogative_raw)

    token = respondent_token or new_respondent_token()
    record: dict[str, Any] = {
        "record_id": record_id or str(uuid.uuid4()),
        "event_id": event_id,
        "protocol_version": PROTOCOL_VERSION_STR,
        "collection_config": dict(collection_config),
        "knowledge_condition_id": knowledge_condition_id,
        "respondent_token": token,
        "interrogative_raw": interrogative_raw,
        "bias_quarantine": bias_quarantine.to_dict(),
        "interrogative_normalized": normalized,
        "validation": validation.to_dict(),
        "fact_refs": refs,
        "submitted_at_utc": submitted_at_utc or _utc_now_iso(),
    }
    if review_packet_id is not None:
        record["review_packet_id"] = review_packet_id
    if respondent_channel is not None:
        record["respondent_channel"] = respondent_channel
    return record
