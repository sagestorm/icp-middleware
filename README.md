# icp-middleware

Apache-2.0 reference middleware for the **Interrogative Collection Protocol (ICP)**.

- **Repository:** https://github.com/sagestorm/icp-middleware
- **Issues:** https://github.com/sagestorm/icp-middleware/issues
- **Protocol (source of truth):** https://github.com/sagestorm/interrogative-collection-protocol

Pipeline: **enforce → quarantine → normalize → blind_export**.

Attach to human web forms (Qualtrics-like), LLM persona loops, or hybrid collection stacks. Pure local library — no closed/paid APIs.

`PROTOCOL_VERSION = 1` (wire `protocol_version`: `"1.0"`)

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.10+. Dev extras install `pytest` for the test suite.

For conformance tests, clone the protocol repo as a sibling of this package:

```bash
# Expected layout:
#   ../interrogative-collection-protocol/
#   ./icp-middleware/   (this repo)
git clone https://github.com/sagestorm/interrogative-collection-protocol.git ../interrogative-collection-protocol
```

Alternatively set `ICP_PROTOCOL_PATH` to a local checkout of the protocol repo.

## Quickstart

```python
from icp_middleware import (
    validate_interrogative,
    quarantine_bias,
    normalize_interrogative,
    build_record,
    export_analysis_packet,
)

text = "What service failed first during the outage?"
result = validate_interrogative(text, information_access="identical_fact_sheet")
bias = quarantine_bias(text, validation_codes=result.codes)
normalized = normalize_interrogative(text)

record = build_record(
    interrogative_raw=text,
    event_id="evt-1",
    collection_config={
        "respondent_type": "human_web",
        "event_type": "technical_incident",
        "information_access": "identical_fact_sheet",
        "downstream": "manual_blind_review",
    },
    knowledge_condition_id="K-01",
    fact_refs=["F-001"],
)
packet = export_analysis_packet([record])
```

CLI:

```bash
python -m icp_middleware validate --text "What service failed first during the outage?"
python -m icp_middleware export -i records.json -o packet.json
```

See `examples/basic_pipeline.py`.

## Protocol relationship (source of truth)

Normative protocol: [sagestorm/interrogative-collection-protocol](https://github.com/sagestorm/interrogative-collection-protocol)

Local sibling checkout: [`../interrogative-collection-protocol/`](../interrogative-collection-protocol/)

Normative inputs:

- `SPEC.md` §5 (gates) and §7 (blind export)
- `schemas/*.json`
- `conformance/fixtures/`

Middleware implements the **runtime only** and must not diverge from the protocol.

Schemas are loaded from (in order): `ICP_PROTOCOL_PATH`, monorepo protocol repo, then vendored copies under `icp_middleware/schemas/`.

## Development / CI

```bash
pip install -e ".[dev]"
pytest -q
```

GitHub Actions checks out this repo and the protocol repo as siblings so relative fixture paths (`../interrogative-collection-protocol`) resolve, then runs `pytest` on Python 3.10–3.12.

### Sync status

Aligned to ICP v1 draft lock-ins:

| Topic | Value |
|-------|-------|
| `E_LEN` | `[12, 280]` Unicode scalars after trim |
| Blind unit id | `unit_id` |
| Blind time | `submitted_on_utc` (`YYYY-MM-DD`) |
| Blind config | `event_type` + `downstream` only |
| Wire version | `"1.0"` |

## Public API

- `validate_interrogative`
- `quarantine_bias`
- `normalize_interrogative`
- `build_record`
- `export_analysis_packet`
- `seal_coding_key`
- `export_and_seal`
- `PROTOCOL_VERSION` / `PROTOCOL_VERSION_STR`

## License

Apache License 2.0. See [LICENSE](LICENSE).
