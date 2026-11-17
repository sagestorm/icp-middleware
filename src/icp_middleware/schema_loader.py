"""Load protocol JSON schemas from protocol repo or vendored copies."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from icp_middleware.constants import PROTOCOL_VERSION, PROTOCOL_VERSION_STR

_PACKAGE_SCHEMAS = Path(__file__).resolve().parent / "schemas"
_MONOREPO_PROTOCOL = (
    Path(__file__).resolve().parents[3] / "interrogative-collection-protocol"
)

SCHEMA_FILES = (
    "interrogative.collection.v1.json",
    "analysis.packet.v1.json",
    "coding.key.v1.json",
)


def protocol_schema_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("ICP_PROTOCOL_PATH")
    if env:
        roots.append(Path(env))
    roots.append(_MONOREPO_PROTOCOL)
    roots.append(_PACKAGE_SCHEMAS)
    return roots


def schemas_available() -> bool:
    for root in protocol_schema_roots():
        for name in SCHEMA_FILES:
            for candidate in (root / name, root / "schemas" / name):
                if candidate.is_file():
                    return True
    return False


def load_schema(name: str) -> dict[str, Any] | None:
    filename = name if name.endswith(".json") else f"{name}.json"
    for root in protocol_schema_roots():
        for candidate in (
            root / filename,
            root / "schemas" / filename,
            root / "schema" / filename,
        ):
            if candidate.is_file():
                with candidate.open(encoding="utf-8") as fh:
                    return json.load(fh)
    return None


def schema_sync_status() -> dict[str, Any]:
    available = schemas_available()
    return {
        "protocol_version": PROTOCOL_VERSION,
        "protocol_version_str": PROTOCOL_VERSION_STR,
        "schemas_available": available,
        "mode": "protocol_repo" if available else "embedded_fallback",
        "search_roots": [str(p) for p in protocol_schema_roots()],
        "schema_files": list(SCHEMA_FILES),
    }
