"""Minimal enforce → quarantine → normalize → blind_export pipeline."""

from __future__ import annotations

import json

from icp_middleware import (
    build_record,
    export_and_seal,
    normalize_interrogative,
    quarantine_bias,
    validate_interrogative,
)

TEXTS = [
    "What service failed first during the outage?",
    "When did the first alert fire on call?",
    "Why didn't you stop the cover-up before publication?",  # E_LEAD
]


def main() -> None:
    config = {
        "respondent_type": "hybrid",
        "event_type": "technical_incident",
        "information_access": "identical_fact_sheet",
        "downstream": "manual_blind_review",
    }
    records = []
    for i, text in enumerate(TEXTS):
        result = validate_interrogative(
            text, information_access=config["information_access"]
        )
        bias = quarantine_bias(text, validation_codes=result.codes)
        normalized = normalize_interrogative(text)
        print(f"[{i}] status={result.status} codes={result.codes} norm={normalized!r}")
        print(f"    bias={bias.to_dict()}")
        records.append(
            build_record(
                interrogative_raw=text,
                event_id="evt-demo",
                collection_config=config,
                knowledge_condition_id="K-01",
                respondent_token=f"R-DEMO{i:07d}".replace("R-DEMO", "R-A")[:14]
                if False
                else None,
                fact_refs=["F-001"],
            )
        )

    accepted = [r for r in records if r["validation"]["status"] == "accepted"]
    packet, key = export_and_seal(
        accepted,
        persona_map={
            r["respondent_token"]: f"persona-{i}" for i, r in enumerate(accepted)
        },
        knowledge_map={"K-01": "pack:identical"},
        fact_map={"F-001": "demo fact line"},
    )
    print("\nBlind packet:")
    print(json.dumps(packet.to_dict(), indent=2))
    print("\nCoding key (steward-only):")
    print(json.dumps(key.to_dict(), indent=2))


if __name__ == "__main__":
    main()
