#!/usr/bin/env python3
"""Record the result of a source freshness check for a StudyState target.

Updates sources/SOURCE_STATE.yaml with a deterministic, public-safe record of
the checked source metadata so future next-activity decisions can suppress
unnecessary repeated recent_info_check recommendations.

Usage:
    python3 scripts/record_source_check.py <source_id> [flags]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from state_io import load_yaml, save_yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCE_STATE_PATH = ROOT / "sources" / "SOURCE_STATE.yaml"
MODE_PATH = ROOT / "state" / "STUDYDD_MODE.yaml"

SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

OUTCOMES = {"fresh", "stale", "missing", "unverified", "unknown"}

AUTHORITY_ORDER = [
    "official",
    "high_authority",
    "instructor",
    "textbook",
    "learner_notes",
    "unverified",
]

VOLATILITY_VALUES = {"stable", "slow_changing", "moderate", "volatile", "live"}

DEMO_OUTPUT = """Source check record (demo)
==========================

Command example:
  python3 scripts/record_source_check.py demo-official \
    --target-id demo-ai-search-exam \
    --outcome fresh \
    --authority official \
    --volatility volatile \
    --checked-at 2026-06-27T12:00:00+00:00 \
    --summary "Official docs verified; no exam objective changes."

Result written to sources/SOURCE_STATE.yaml would look like:

  - id: demo-official
    target_ids:
      - demo-ai-search-exam
    authority: official
    volatility: volatile
    usable_for_questions: true
    last_checked_at: "2026-06-27T12:00:00+00:00"
    last_check:
      checked_at: "2026-06-27T12:00:00+00:00"
      outcome: fresh
      summary: "Official docs verified; no exam objective changes."
      evidence_id: ""
      activity_id: ""
      checked_by: agent

This was a demo; no file was written.
"""


@dataclass
class SourceCheckArgs:
    """Container for source-check parameters used by the reusable function."""

    source_id: str
    target_id: str | None = None
    outcome: str = "fresh"
    summary: str = ""
    evidence_id: str = ""
    activity_id: str = ""
    checked_by: str = "agent"
    checked_at: str = ""
    expires_at: str | None = None
    authority: str = "official"
    volatility: str | None = None
    freshness_window_days: int | None = None
    usable_for_questions: bool | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def validate_source_id(source_id: str) -> None:
    if not source_id:
        raise ValueError("source_id must be non-empty")
    if not SOURCE_ID_RE.match(source_id):
        raise ValueError(
            f"source_id '{source_id}' is invalid; must match ^[A-Za-z0-9_-]+$"
        )


def validate_args(args: SourceCheckArgs) -> None:
    validate_source_id(args.source_id)

    if args.outcome not in OUTCOMES:
        raise ValueError(
            f"--outcome must be one of {sorted(OUTCOMES)}, got {args.outcome!r}"
        )

    if args.authority not in set(AUTHORITY_ORDER):
        raise ValueError(
            f"--authority must be one of {AUTHORITY_ORDER}, got {args.authority!r}"
        )

    if args.volatility is not None and args.volatility not in VOLATILITY_VALUES:
        raise ValueError(
            f"--volatility must be one of {sorted(VOLATILITY_VALUES)}, got {args.volatility!r}"
        )

    if args.checked_by not in {"agent", "learner"}:
        raise ValueError(
            f"--checked-by must be 'agent' or 'learner', got {args.checked_by!r}"
        )

    try:
        checked_at = parse_iso_timestamp(args.checked_at)
    except Exception as exc:
        raise ValueError(f"--checked-at is not a valid ISO 8601 timestamp: {exc}")

    if args.expires_at is not None:
        try:
            expires_at = parse_iso_timestamp(args.expires_at)
        except Exception as exc:
            raise ValueError(
                f"--expires-at is not a valid ISO 8601 timestamp: {exc}"
            )
        if expires_at < checked_at:
            raise ValueError("--expires-at must be >= --checked-at")

    if args.freshness_window_days is not None:
        if args.freshness_window_days <= 0:
            raise ValueError(
                "--freshness-window-days must be a positive integer"
            )


def find_source(state: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    for source in state.get("sources", []):
        if isinstance(source, dict) and source.get("id") == source_id:
            return source
    return None


def resolve_target_id(
    existing: dict[str, Any] | None, args_target_id: str | None
) -> tuple[str | None, str | None]:
    """Return (target_id, error_message) for the source entry being written."""
    if existing is not None:
        existing_target_ids = existing.get("target_ids", [])
        if existing_target_ids:
            return existing_target_ids[0], None
        if args_target_id:
            return args_target_id, None
        return None, (
            "existing source has empty target_ids; provide --target-id to set one"
        )
    if args_target_id:
        return args_target_id, None
    return None, "source_id not found and --target-id is required"


def build_source_entry(
    source_id: str,
    target_id: str,
    args: SourceCheckArgs,
    existing: dict[str, Any] | None,
) -> dict[str, Any]:
    checked_at = args.checked_at
    outcome = args.outcome

    if existing is not None:
        source = dict(existing)
        # Repair a source whose target_ids list is empty when the caller
        # explicitly supplies --target-id.
        if not source.get("target_ids") and args.target_id:
            source["target_ids"] = [args.target_id]
    else:
        volatility = args.volatility
        if volatility is None:
            volatility = "moderate"
        usable = args.usable_for_questions
        if usable is None:
            usable = True
        source = {
            "id": source_id,
            "target_ids": [target_id],
            "authority": args.authority,
            "volatility": volatility,
            "usable_for_questions": usable,
        }
        # freshness_window_days is only set from the CLI when creating a new
        # source; existing sources keep their stored value.
        if args.freshness_window_days is not None:
            source["freshness_window_days"] = args.freshness_window_days

    # Preserve explicit volatility unless caller supplies one.
    if args.volatility is not None:
        source["volatility"] = args.volatility

    # Preserve existing usable_for_questions unless caller explicitly overrides it.
    if args.usable_for_questions is not None:
        source["usable_for_questions"] = args.usable_for_questions

    # Only a fresh outcome bumps the source-level freshness signal.
    if outcome == "fresh":
        source["last_checked_at"] = checked_at
        if args.expires_at is not None:
            source["expires_at"] = args.expires_at
        else:
            # Drop any stale explicit expiry so freshness is computed from the
            # new last_checked_at and volatility/window.
            source.pop("expires_at", None)

    source["last_check"] = {
        "checked_at": checked_at,
        "outcome": outcome,
        "summary": args.summary,
        "evidence_id": args.evidence_id,
        "activity_id": args.activity_id,
        "checked_by": args.checked_by,
    }

    return source


def normalize_source_state(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"metadata": {}, "sources": []}
    if "sources" not in data:
        data["sources"] = []
    if "metadata" not in data:
        data["metadata"] = {}
    return data


def print_dry_run(source_id: str, target_id: str | None, source: dict[str, Any]) -> None:
    import yaml

    print("Dry-run: would record the following source check:")
    print("")
    if target_id:
        print(f"Source ID: {source_id}")
        print(f"Target ID: {target_id}")
    else:
        print(f"Source ID: {source_id} (existing source)")
    print("")
    print(yaml.safe_dump(source, sort_keys=False))


def record_source_check(
    source_id: str,
    *,
    target_id: str | None = None,
    outcome: str = "fresh",
    summary: str = "",
    evidence_id: str = "",
    activity_id: str = "",
    checked_by: str = "agent",
    checked_at: str | None = None,
    expires_at: str | None = None,
    authority: str = "official",
    volatility: str | None = None,
    freshness_window_days: int | None = None,
    usable_for_questions: bool | None = None,
    dry_run: bool = False,
    repo_root: str | Path | None = None,
) -> int:
    """Record a completed source freshness check.

    This is the reusable entry point. The CLI main() is a thin wrapper around
    this function.

    Parameters match the command-line flags. Returns an integer exit/status
    code (0 success, 1 validation/runtime error, 2 write refused, 3 missing
    source without target-id).
    """
    if checked_at is None:
        checked_at = now_iso()

    root = Path(repo_root).resolve() if repo_root else ROOT
    source_state_path = root / "sources" / "SOURCE_STATE.yaml"
    mode_path = root / "state" / "STUDYDD_MODE.yaml"

    args = SourceCheckArgs(
        source_id=source_id,
        target_id=target_id,
        outcome=outcome,
        summary=summary,
        evidence_id=evidence_id,
        activity_id=activity_id,
        checked_by=checked_by,
        checked_at=checked_at,
        expires_at=expires_at,
        authority=authority,
        volatility=volatility,
        freshness_window_days=freshness_window_days,
        usable_for_questions=usable_for_questions,
    )

    try:
        validate_args(args)
    except ValueError as exc:
        print(f"Validation error: {exc}")
        return 1

    mode = load_yaml(mode_path).get("mode", "unknown")

    if dry_run:
        state = normalize_source_state(load_yaml(source_state_path))
        existing = find_source(state, source_id)
        resolved_target_id, error = resolve_target_id(existing, target_id)
        if error:
            print(f"Dry-run error: {error}.")
            return 3
        source = build_source_entry(source_id, resolved_target_id, args, existing)
        print_dry_run(source_id, resolved_target_id, source)
        return 0

    if mode != "learner_instance":
        print(
            f"Error: write refused — repo mode is '{mode}', "
            "but source checks may only be recorded in learner_instance mode. "
            "Use --dry-run or --demo for read-only output."
        )
        return 2

    state = normalize_source_state(load_yaml(source_state_path))
    existing = find_source(state, source_id)

    resolved_target_id, error = resolve_target_id(existing, target_id)
    if error:
        print(f"Error: {error}.")
        if existing is not None:
            return 1
        return 3

    source = build_source_entry(source_id, resolved_target_id, args, existing)

    if existing is None:
        state["sources"].append(source)
    else:
        for idx, s in enumerate(state["sources"]):
            if isinstance(s, dict) and s.get("id") == source_id:
                state["sources"][idx] = source
                break

    metadata = state.setdefault("metadata", {})
    metadata["last_updated"] = now_iso()
    metadata["updated_by"] = "record_source_check.py"

    save_yaml(source_state_path, state)

    print(f"Recorded source check for {source_id}")
    print(f"  outcome: {outcome}")
    print(f"  checked_at: {checked_at}")
    if outcome == "fresh":
        print(f"  last_checked_at: {source.get('last_checked_at')}")
    print(f"  source_state: {source_state_path.relative_to(root)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a completed source freshness check"
    )
    parser.add_argument(
        "source_id",
        nargs="?",
        default=None,
        help="Unique source identifier (required unless --demo is used)",
    )
    parser.add_argument("--target-id", help="Target ID (required when creating a new source)")
    parser.add_argument(
        "--outcome",
        default="fresh",
        help=f"Freshness check outcome (one of {sorted(OUTCOMES)})",
    )
    parser.add_argument("--summary", default="", help="Short summary of the check")
    parser.add_argument("--evidence-id", default="", help="Evidence ID for the check")
    parser.add_argument("--activity-id", default="", help="Activity ID that produced the check")
    parser.add_argument(
        "--checked-by",
        default="agent",
        help="Who performed the check (agent or learner)",
    )
    parser.add_argument(
        "--checked-at",
        default=now_iso(),
        help="ISO 8601 timestamp when the check was performed",
    )
    parser.add_argument(
        "--expires-at",
        default=None,
        help="Optional ISO 8601 expiration timestamp (must be >= checked_at)",
    )
    parser.add_argument(
        "--authority",
        default="official",
        help=(
            f"Source authority level (one of {AUTHORITY_ORDER}). "
            "Used when creating a new source; ignored when updating an existing source (preserved)."
        ),
    )
    parser.add_argument(
        "--volatility",
        default=None,
        help=(
            f"Source volatility (defaults to moderate for new sources; one of {sorted(VOLATILITY_VALUES)}). "
            "Existing source volatility is preserved unless explicitly overridden."
        ),
    )
    parser.add_argument(
        "--freshness-window-days",
        type=int,
        default=None,
        help=(
            "Optional positive freshness window in days. "
            "Used when creating a new source; ignored when updating an existing source (preserved)."
        ),
    )
    parser.add_argument(
        "--usable-for-questions",
        dest="usable_for_questions",
        action="store_true",
        default=None,
        help="Mark the source as usable for questions. Default for new sources; existing value is preserved when updating unless this flag is explicitly provided.",
    )
    parser.add_argument(
        "--not-usable-for-questions",
        dest="usable_for_questions",
        action="store_false",
        help="Mark the source as not usable for questions. Existing value is preserved when updating unless this flag is explicitly provided.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying state",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Print a fake example and exit without writing",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to the StudyState repo root (default: parent of this script)",
    )
    args = parser.parse_args()

    if args.source_id is None and not args.demo:
        parser.error("source_id is required unless --demo is used")

    if args.demo:
        print(DEMO_OUTPUT, end="")
        return 0

    return record_source_check(
        source_id=args.source_id,
        target_id=args.target_id,
        outcome=args.outcome,
        summary=args.summary,
        evidence_id=args.evidence_id,
        activity_id=args.activity_id,
        checked_by=args.checked_by,
        checked_at=args.checked_at,
        expires_at=args.expires_at,
        authority=args.authority,
        volatility=args.volatility,
        freshness_window_days=args.freshness_window_days,
        usable_for_questions=args.usable_for_questions,
        dry_run=args.dry_run,
        repo_root=args.repo_root,
    )


if __name__ == "__main__":
    sys.exit(main())
