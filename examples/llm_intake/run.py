#!/usr/bin/env python3
"""Run LLM persona intake (mock by default; optional OpenAI-compatible live)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running without install: repo root → src on path
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from icp_middleware.llm_intake import (  # noqa: E402
    MockProvider,
    OpenAICompatibleProvider,
    event_pack_from_dict,
    run_llm_intake,
)

HERE = Path(__file__).resolve().parent
DEFAULT_EVENT = HERE / "sample_event.json"
DEFAULT_OUT = HERE / "out"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ICP LLM intake: fact pack → one interrogative per persona"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--mock",
        action="store_true",
        help="Use MockProvider (default when neither flag is set; no API key)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Call OpenAI-compatible Chat Completions (needs OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--event",
        type=Path,
        default=DEFAULT_EVENT,
        help=f"Event pack JSON (default: {DEFAULT_EVENT.name})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory for records / packet / coding key",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Validation retries per persona (default: 3)",
    )
    args = parser.parse_args(argv)

    use_live = bool(args.live)  # default path is mock when --live omitted
    data = json.loads(args.event.read_text(encoding="utf-8"))
    event_pack = event_pack_from_dict(data)

    if use_live:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY is required for --live", file=sys.stderr)
            return 2
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        provider = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        print(f"Live provider model={model} base_url={base_url}")
    else:
        provider = MockProvider()
        print("MockProvider (offline)")

    records, packet, key = run_llm_intake(
        event_pack,
        provider,
        max_attempts=args.max_attempts,
    )

    out_dir = args.out
    _write_json(out_dir / "records.json", records)
    if packet is not None:
        _write_json(out_dir / "analysis_packet.json", packet.to_dict())
    else:
        _write_json(out_dir / "analysis_packet.json", None)

    coding_payload = {
        "_steward_only": True,
        "_warning": (
            "CODING KEY — steward-only. Do not share with blind reviewers. "
            "Contains respondent identity and shuffle seed."
        ),
        "coding_key": None if key is None else key.to_dict(),
    }
    _write_json(out_dir / "coding_key.json", coding_payload)

    accepted = sum(
        1 for r in records if r.get("validation", {}).get("status") == "accepted"
    )
    print(f"Wrote {len(records)} records ({accepted} accepted) → {out_dir}")
    if packet is not None:
        print(f"Blind units: {len(packet.units)}")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
