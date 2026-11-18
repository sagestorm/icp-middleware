# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-11-17

### Fixed

- `E_WH` accepts prepositional fronts before wh-words (e.g. `At what time…?`),
  which live NIM intake produced and previously rejected.

### Added

- `E_SPEC` gate: rejects banal generics and ungrounded interrogatives when
  `fact_sheet_text` is supplied (`validate_interrogative` /
  `normalize_interrogative` / `build_record`).
- Model-emitted `fact_refs` in LLM intake JSON
  `{"interrogative","fact_refs"}` — no silent full-pack substitution.
- `LiveRetryProbeProvider` + CLI `--live --probe-retry` to prove code-only
  retry before hitting the network.
- `sample_event_policy.json` (`policy_change`, asymmetric, 3 personas).
- `assert_record_quality` acceptance helper; conformance fixtures 09–11.

### Changed

- `parse_interrogative_payload` now returns `(interrogative, fact_refs, err)`.
- `ERROR_CODES` includes `E_SPEC` (breaking wire/code set vs 0.1.0).
- Package version `0.2.0`; vendored schemas synced to protocol v0.2.0.

## [0.1.0] - 2026-11-17

### Added

- Initial Apache-2.0 reference middleware for ICP v1 (`PROTOCOL_VERSION = 1`).
- Pipeline: `validate_interrogative` → `quarantine_bias` → `normalize_interrogative` → `build_record` → `export_analysis_packet` / `seal_coding_key`.
- CLI entry point `icp-middleware` / `python -m icp_middleware`.
- Schema loader with protocol-repo preference and vendored fallbacks.
- Unit and conformance tests (fixtures 01–08 against the sibling protocol repo).
- LLM persona intake (`llm_intake`): `PersonaSpec` / `EventPack`, `MockProvider`,
  optional stdlib `OpenAICompatibleProvider`, `collect_persona_interrogative`,
  `run_llm_intake`, plus `examples/llm_intake/` mock/live demo.

[0.2.0]: https://github.com/sagestorm/icp-middleware/releases/tag/v0.2.0
[0.1.0]: https://github.com/sagestorm/icp-middleware/releases/tag/v0.1.0
