# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-17

### Added

- Initial Apache-2.0 reference middleware for ICP v1 (`PROTOCOL_VERSION = 1`).
- Pipeline: `validate_interrogative` → `quarantine_bias` → `normalize_interrogative` → `build_record` → `export_analysis_packet` / `seal_coding_key`.
- CLI entry point `icp-middleware` / `python -m icp_middleware`.
- Schema loader with protocol-repo preference and vendored fallbacks.
- Unit and conformance tests (fixtures 01–08 against the sibling protocol repo).

[0.1.0]: https://github.com/sagestorm/icp-middleware/releases/tag/v0.1.0
