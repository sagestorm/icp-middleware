"""File-based CLI: ``python -m icp_middleware validate|export``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from icp_middleware.export import export_analysis_packet
from icp_middleware.record import build_record
from icp_middleware.validate import validate_interrogative


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def cmd_validate(args: argparse.Namespace) -> int:
    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    if text is None:
        print("error: provide --text or --file", file=sys.stderr)
        return 2

    fact_refs = args.fact_ref or []
    fact_ids_allowed = args.fact_allowed or None
    result = validate_interrogative(
        text,
        information_access=args.information_access,
        fact_ids_allowed=fact_ids_allowed,
        fact_refs=fact_refs,
    )
    payload = {
        "passed": result.passed,
        "codes": list(result.codes),
        "validation": result.to_dict(),
    }
    if args.output:
        _write_json(Path(args.output), payload)
    else:
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0 if result.passed else 1


def cmd_export(args: argparse.Namespace) -> int:
    raw = _load_json(Path(args.input))
    if isinstance(raw, dict) and "records" in raw:
        records = raw["records"]
    elif isinstance(raw, list):
        records = raw
    else:
        print(
            'error: input must be a list of records or {"records": [...]}',
            file=sys.stderr,
        )
        return 2

    assembled: list[dict[str, Any]] = []
    for item in records:
        if "interrogative_normalized" in item and "validation" in item:
            assembled.append(item)
            continue
        if "interrogative_raw" not in item:
            print(
                "error: each item needs interrogative_raw or a full record",
                file=sys.stderr,
            )
            return 2
        assembled.append(
            build_record(
                interrogative_raw=item["interrogative_raw"],
                event_id=item.get("event_id", "evt-unknown"),
                collection_config=item.get(
                    "collection_config",
                    {
                        "respondent_type": "human_web",
                        "event_type": "other",
                        "information_access": "identical_fact_sheet",
                        "downstream": "manual_blind_review",
                    },
                ),
                knowledge_condition_id=item.get("knowledge_condition_id", "K-01"),
                respondent_token=item.get("respondent_token"),
                fact_refs=item.get("fact_refs"),
                fact_ids_allowed=item.get("fact_ids_allowed"),
                freeform_affect=item.get("freeform_affect"),
                respondent_channel=item.get("respondent_channel"),
            )
        )

    packet = export_analysis_packet(assembled)
    out = packet.to_dict()
    if args.output:
        _write_json(Path(args.output), out)
    else:
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="icp_middleware",
        description="ICP middleware: validate interrogatives and export blind packets",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate one interrogative")
    v.add_argument("--text", help="Interrogative text")
    v.add_argument("--file", help="Read interrogative text from file")
    v.add_argument(
        "--information-access",
        default="identical_fact_sheet",
        choices=("identical_fact_sheet", "asymmetric_role_packs"),
    )
    v.add_argument("--fact-ref", action="append", default=[], help="Fact ref id")
    v.add_argument(
        "--fact-allowed",
        action="append",
        default=[],
        help="Allowed fact id for asymmetric packs",
    )
    v.add_argument("--output", "-o", help="Write JSON result to path")
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("export", help="Export blind analysis packet from JSON records")
    e.add_argument("--input", "-i", required=True, help="Input JSON path")
    e.add_argument("--output", "-o", help="Output JSON path (default: stdout)")
    e.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
