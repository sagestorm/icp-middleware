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
    LiveRetryProbeProvider,
    MockProvider,
    OpenAICompatibleProvider,
    event_pack_from_dict,
    persona_fact_sheet_text,
    run_llm_intake,
)
from icp_middleware.quality import assert_record_quality  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_EVENT = HERE / "sample_event.json"
DEFAULT_OUT = HERE / "out"
_NIM_BASE = "https://integrate.api.nvidia.com/v1"
_NIM_MODEL = "google/gemma-4-31b-it"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader; does not override existing process env."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _resolve_live_credentials() -> tuple[str, str, str]:
    """Map OpenAI or NVIDIA NIM env vars to (api_key, base_url, model)."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit(
            "Live mode needs OPENAI_API_KEY or NVIDIA_API_KEY "
            "(load from repo-root .env or the process environment)."
        )
    if os.environ.get("OPENAI_API_KEY"):
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        base_url = (
            os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("MASTERY_MODEL_BASE_URL")
            or _NIM_BASE
        )
        model = (
            os.environ.get("OPENAI_MODEL")
            or os.environ.get("MASTERY_MODEL_NAME")
            or _NIM_MODEL
        )
    return api_key, base_url, model


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
        "--probe-retry",
        action="store_true",
        help=(
            "With --live: wrap the provider so attempt 1 is local pollution "
            "and attempt 2+ hit the network (proves code-only retry)."
        ),
    )
    parser.add_argument(
        "--event",
        type=Path,
        default=DEFAULT_EVENT,
        help=(
            "Event pack JSON (default: sample_event.json). "
            "Also see sample_event_policy.json for policy_change."
        ),
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

    if args.probe_retry and not args.live:
        raise SystemExit("--probe-retry requires --live")

    # Prefer workspace .env (pipi/), then middleware package .env — never override
    # already-exported process variables.
    _load_dotenv(_ROOT.parent / ".env")
    _load_dotenv(_ROOT / ".env")

    use_live = bool(args.live)  # default path is mock when --live omitted
    data = json.loads(args.event.read_text(encoding="utf-8"))
    event_pack = event_pack_from_dict(data)

    probe: LiveRetryProbeProvider | None = None
    if use_live:
        api_key, base_url, model = _resolve_live_credentials()
        live = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        if args.probe_retry:
            probe = LiveRetryProbeProvider(inner=live)
            provider = probe
            print(
                f"LiveRetryProbeProvider → model={model} base_url={base_url}"
            )
        else:
            provider = live
            print(f"Live provider model={model} base_url={base_url}")
    else:
        provider = MockProvider()
        print("MockProvider (offline)")

    records, packet, key = run_llm_intake(
        event_pack,
        provider,
        max_attempts=args.max_attempts,
    )

    if probe is not None:
        summary = probe.summary()
        print(
            "Probe retry summary: "
            f"probe_calls={summary['probe_calls']} "
            f"network_calls={summary['network_calls']} "
            f"persona_attempts={summary['persona_attempts']}"
        )
        _write_json(args.out / "probe_retry_summary.json", summary)

    # Soft quality check on accepted records (does not fail the process alone).
    persona_by_kcid = {
        p.knowledge_condition_id: p for p in event_pack.personas
    }
    for rec in records:
        if rec.get("validation", {}).get("status") != "accepted":
            continue
        persona = persona_by_kcid.get(rec["knowledge_condition_id"])
        sheet = (
            persona_fact_sheet_text(event_pack, persona) if persona else None
        )
        try:
            assert_record_quality(rec, sheet)
        except AssertionError as exc:
            print(f"Quality warning ({rec.get('knowledge_condition_id')}): {exc}")

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
