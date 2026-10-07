#!/usr/bin/env python3
"""Compact StudyState append-only audit logs into derived summaries and indexes.

This script preserves the audit trail while producing compact working-memory
files that agents can load quickly:

- state/CURRENT_CONTEXT.md
- state/EVIDENCE_INDEX.yaml
- sessions/SESSION_SUMMARIES.md

It is deterministic enough for tests and safe to run repeatedly. With
`--check-stale` it reports whether compaction is needed without rewriting
files. With `--force` it ignores the state cache and rebuilds everything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STUDY_STATE_PATH = ROOT / "state" / "STUDY_STATE.yaml"
SKILL_MAP_PATH = ROOT / "state" / "SKILL_MAP.yaml"
REVIEW_STATE_PATH = ROOT / "reviews" / "REVIEW_STATE.yaml"
EVIDENCE_LOG_PATH = ROOT / "state" / "EVIDENCE_LOG.md"
SESSION_LOG_PATH = ROOT / "sessions" / "SESSION_LOG.md"
NEXT_ACTIONS_PATH = ROOT / "NEXT_ACTIONS.md"

CURRENT_CONTEXT_PATH = ROOT / "state" / "CURRENT_CONTEXT.md"
EVIDENCE_INDEX_PATH = ROOT / "state" / "EVIDENCE_INDEX.yaml"
SESSION_SUMMARIES_PATH = ROOT / "sessions" / "SESSION_SUMMARIES.md"

STATE_CACHE_DIR = ROOT / ".studydd"
STATE_CACHE_PATH = STATE_CACHE_DIR / "state_cache.json"

SOURCE_FILES = {
    "evidence_log": EVIDENCE_LOG_PATH,
    "session_log": SESSION_LOG_PATH,
    "study_state": STUDY_STATE_PATH,
    "skill_map": SKILL_MAP_PATH,
    "review_state": REVIEW_STATE_PATH,
    "next_actions": NEXT_ACTIONS_PATH,
}


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Warning: could not read {path}: {exc}")
        return {}


def save_yaml(path: Path, data: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def classify_review_status(item: dict, now: datetime) -> str:
    status = item.get("status")
    if status in ("completed", "suspended"):
        return status
    due_at = parse_iso(item.get("due_at"))
    if due_at is None:
        return "scheduled"
    if due_at <= now:
        if due_at < now - timedelta(days=1):
            return "overdue"
        return "due"
    return "scheduled"


def active_target_id(study_state: dict) -> str | None:
    return study_state.get("active_target_id") or None


def active_target_path(study_state: dict) -> Path | None:
    tid = active_target_id(study_state)
    if not tid:
        return None
    path = ROOT / "targets" / tid / "TARGET.yaml"
    if path.is_file():
        return path
    return None


def weak_skills(skill_map: dict) -> list[dict]:
    weak: list[dict] = []
    for skill in skill_map.get("skills") or []:
        if skill.get("status") in ("weak", "blocked"):
            weak.append(skill)
        elif isinstance(skill.get("readiness"), (int, float)) and skill.get("readiness", 101) <= 40:
            weak.append(skill)
    return weak


def due_reviews(review_state: dict, now: datetime) -> tuple[list[dict], list[dict]]:
    due: list[dict] = []
    overdue: list[dict] = []
    for item in review_state.get("review_items") or []:
        status = classify_review_status(item, now)
        if status == "due":
            due.append(item)
        elif status == "overdue":
            overdue.append(item)
    return due, overdue


def _looks_like_date(value: str) -> bool:
    if not value or value in ("-", "YYYY-MM-DD"):
        return False
    return parse_iso(value) is not None


def parse_evidence_items(text: str) -> list[dict]:
    items: list[dict] = []
    # Split by blank lines so each evidence item is one contiguous block.
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if "**Date:**" not in block and "**Evidence ID:**" not in block:
            continue
        item: dict = {"raw_excerpt": block}
        for field, pattern in [
            ("evidence_id", r"\*\*Evidence ID:\*\*\s*(\S+)"),
            ("date", r"\*\*Date:\*\*\s*(\S+)"),
            ("target_id", r"\*\*Target ID:\*\*\s*(\S+)"),
            ("skill_id", r"\*\*Skill ID:\*\*\s*(\S+)"),
            ("question_id", r"\*\*Question ID:\*\*\s*(\S+)"),
            ("verdict", r"\*\*Verdict:\*\*\s*(\S+)"),
            ("confidence", r"\*\*Confidence:\*\*\s*(\S+)"),
            ("mistake_type", r"\*\*Mistake type:\*\*\s*(\S+)"),
        ]:
            match = re.search(pattern, block)
            if match:
                item[field] = match.group(1).strip()
        # Skip format-documentation blocks that have not produced a real record.
        if not item.get("evidence_id") and not _looks_like_date(item.get("date", "")):
            continue
        # Skip blocks that are clearly template examples.
        if item.get("target_id") in ("target_example", "-") and not item.get("evidence_id"):
            continue
        items.append(item)
    return items


def parse_session_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        block = block.strip()
        if not block or "**Date:**" not in block:
            continue
        entry: dict = {"raw_excerpt": block}
        for field, pattern in [
            ("date", r"\*\*Date:\*\*\s*(\S+)"),
            ("target_id", r"\*\*Target ID:\*\*\s*(\S+)"),
            ("focus", r"\*\*Focus:\*\*\s*(.+?)(?:\n|$)"),
            ("questions_asked", r"\*\*Questions asked:\*\*\s*(.+?)(?:\n|$)"),
            ("result_summary", r"\*\*Result summary:\*\*\s*(.+?)(?:\n|$)"),
            ("evidence_added", r"\*\*Evidence added:\*\*\s*(.+?)(?:\n|$)"),
            ("reviews_added", r"\*\*Reviews added:\*\*\s*(.+?)(?:\n|$)"),
            ("next_action_proposed", r"\*\*Next action proposed:\*\*\s*(.+?)(?:\n|$)"),
        ]:
            match = re.search(pattern, block)
            if match:
                entry[field] = match.group(1).strip()
        # Skip format-documentation blocks.
        if not _looks_like_date(entry.get("date", "")):
            continue
        if entry.get("target_id") == "target folder ID":
            continue
        entries.append(entry)
    return entries


def file_fingerprint(path: Path) -> dict:
    """Return a stable fingerprint for a file, or empty dict if missing."""
    if not path.is_file():
        return {}
    try:
        data = path.read_bytes()
        return {
            "mtime": path.stat().st_mtime,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
    except Exception:
        return {}


def load_state_cache() -> dict:
    if not STATE_CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(STATE_CACHE_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def save_state_cache(cache: dict) -> None:
    STATE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def current_fingerprints() -> dict:
    return {
        name: file_fingerprint(path)
        for name, path in SOURCE_FILES.items()
    }


def is_stale(cache: dict) -> tuple[bool, dict]:
    """Return (stale, new_fingerprints). Stale means cache missing or any fingerprint changed."""
    new = current_fingerprints()
    old = cache.get("source_file_fingerprints") or {}
    if not old:
        return True, new
    for name, fingerprint in new.items():
        if old.get(name) != fingerprint:
            return True, new
    return False, new


def build_current_context(
    study_state: dict,
    skill_map: dict,
    review_state: dict,
    next_actions_text: str,
    now: datetime,
) -> str:
    learner = study_state.get("learner") or {}
    active_target = active_target_id(study_state)
    active_focus = study_state.get("active_focus") or {}

    due, overdue = due_reviews(review_state, now)
    weak = weak_skills(skill_map)

    target_path = active_target_path(study_state)
    target_type = ""
    study_skill = ""
    if target_path:
        target_data = load_yaml(target_path)
        target_type = target_data.get("type", "")
        study_skill = target_data.get("study_skill", "")

    lines: list[str] = [
        "# CURRENT_CONTEXT — Compact Learner State",
        "",
        "> **Auto-generated.** This is a compact working-memory summary. For the full audit trail, see state/EVIDENCE_LOG.md and sessions/SESSION_LOG.md.",
        "",
        "## Learner",
        "",
        f"- **Name:** {learner.get('name') or '(none)'}",
        f"- **Preferred language:** {learner.get('preferred_language') or '(not set)'}",
        f"- **Preferred tutoring style:** {learner.get('preferred_tutoring_style') or '(not set)'}",
        "",
        "## Active target",
        "",
        f"- **Target ID:** {active_target or '(none)'}",
    ]
    if target_type:
        lines.append(f"- **Target type:** {target_type}")
    if study_skill:
        lines.append(f"- **Study skill:** {study_skill}")
    lines.extend([
        f"- **Current topic:** {active_focus.get('current_topic') or '(none)'}",
        f"- **Next question:** {active_focus.get('next_question') or '(none)'}",
        f"- **Blocking confusions:** {active_focus.get('blocking_confusions') or []}",
        "",
        "## Reviews",
        "",
        f"- **Due now:** {len(due)}",
        f"- **Overdue:** {len(overdue)}",
    ])
    if due:
        lines.append(f"- **Next due review:** {due[0].get('id')} ({due[0].get('skill_id')})")
    if overdue:
        lines.append(f"- **Next overdue review:** {overdue[0].get('id')} ({overdue[0].get('skill_id')})")
    lines.extend([
        "",
        "## Weak skills",
        "",
    ])
    if weak:
        for skill in weak:
            lines.append(
                f"- **{skill.get('id')}** ({skill.get('label') or 'no label'}): "
                f"status {skill.get('status')}, readiness {skill.get('readiness')}"
            )
    else:
        lines.append("- None identified.")

    session_entries = parse_session_entries(
        SESSION_LOG_PATH.read_text(encoding="utf-8") if SESSION_LOG_PATH.is_file() else ""
    )
    lines.extend([
        "",
        "## Last session",
        "",
    ])
    if session_entries:
        last = session_entries[-1]
        lines.append(f"- **Date:** {last.get('date', '?')}")
        lines.append(f"- **Target ID:** {last.get('target_id', '?')}")
        lines.append(f"- **Focus:** {last.get('focus', '?')}")
        lines.append(f"- **Questions asked:** {last.get('questions_asked', '?')}")
        lines.append(f"- **Result summary:** {last.get('result_summary', '?')}")
        lines.append(f"- **Evidence added:** {last.get('evidence_added', '?')}")
        lines.append(f"- **Reviews added:** {last.get('reviews_added', '?')}")
        lines.append(f"- **Next action proposed:** {last.get('next_action_proposed', '?')}")
    else:
        lines.append("- No sessions recorded.")

    current_action = "(none)"
    if "## Current next action" in next_actions_text:
        action_section = next_actions_text.split("## Current next action", 1)[1]
        action_section = action_section.split("##", 1)[0]
        current_action = action_section.strip().replace("\n", " ")
    lines.extend([
        "",
        "## Next action",
        "",
        f"{current_action}",
        "",
    ])

    return "\n".join(lines)


def build_evidence_index() -> dict:
    text = EVIDENCE_LOG_PATH.read_text(encoding="utf-8") if EVIDENCE_LOG_PATH.is_file() else ""
    items = parse_evidence_items(text)
    return {
        "index_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": EVIDENCE_LOG_PATH.relative_to(ROOT).as_posix(),
        "count": len(items),
        "items": [
            {
                "evidence_id": item.get("evidence_id", ""),
                "date": item.get("date", ""),
                "target_id": item.get("target_id", ""),
                "skill_id": item.get("skill_id", ""),
                "question_id": item.get("question_id", ""),
                "verdict": item.get("verdict", ""),
                "confidence": item.get("confidence", ""),
                "mistake_type": item.get("mistake_type", ""),
                "source_file": "state/EVIDENCE_LOG.md",
                "line_hint": item.get("evidence_id", "") or item.get("date", ""),
            }
            for item in items
        ],
    }


def build_session_summaries() -> str:
    text = SESSION_LOG_PATH.read_text(encoding="utf-8") if SESSION_LOG_PATH.is_file() else ""
    entries = parse_session_entries(text)

    lines: list[str] = [
        "# SESSION_SUMMARIES — Compact Session History",
        "",
        "> **Auto-generated.** This file is a compact summary of sessions. For the full audit trail, see sessions/SESSION_LOG.md.",
        "",
        f"- **Total sessions:** {len(entries)}",
        f"- **Last generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    if not entries:
        lines.append("No sessions recorded yet.")
        return "\n".join(lines) + "\n"

    for entry in entries:
        lines.extend([
            f"## {entry.get('date', 'Unknown date')} — {entry.get('target_id', 'no target')}",
            "",
            f"- **Focus:** {entry.get('focus', '?')}",
            f"- **Questions asked:** {entry.get('questions_asked', '?')}",
            f"- **Result summary:** {entry.get('result_summary', '?')}",
            f"- **Evidence added:** {entry.get('evidence_added', '?')}",
            f"- **Reviews added:** {entry.get('reviews_added', '?')}",
            f"- **Next action proposed:** {entry.get('next_action_proposed', '?')}",
            "",
        ])

    return "\n".join(lines)


def compact(force: bool = False, dry_run: bool = False) -> tuple[bool, dict]:
    """Rebuild derived files as needed. Return (did_work, new_cache)."""
    cache = load_state_cache()
    stale, new_fingerprints = is_stale(cache)

    # Determine which derived files need rebuilding.
    evidence_fingerprint = new_fingerprints.get("evidence_log") or {}
    session_fingerprint = new_fingerprints.get("session_log") or {}
    old_fingerprints = cache.get("source_file_fingerprints") or {}

    rebuild_evidence = force or stale or (old_fingerprints.get("evidence_log") != evidence_fingerprint)
    rebuild_sessions = force or stale or (old_fingerprints.get("session_log") != session_fingerprint)
    # Current context depends on multiple source files; rebuild if anything changed.
    rebuild_context = force or stale

    if dry_run:
        return (rebuild_evidence or rebuild_sessions or rebuild_context, new_fingerprints)

    now = datetime.now(timezone.utc)
    study_state = load_yaml(STUDY_STATE_PATH)
    skill_map = load_yaml(SKILL_MAP_PATH)
    review_state = load_yaml(REVIEW_STATE_PATH)
    next_actions_text = NEXT_ACTIONS_PATH.read_text(encoding="utf-8") if NEXT_ACTIONS_PATH.is_file() else ""

    if rebuild_context:
        context = build_current_context(study_state, skill_map, review_state, next_actions_text, now)
        CURRENT_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CURRENT_CONTEXT_PATH.write_text(context + "\n", encoding="utf-8")
        print(f"Updated {CURRENT_CONTEXT_PATH.relative_to(ROOT).as_posix()}")

    if rebuild_evidence:
        evidence_index = build_evidence_index()
        save_yaml(EVIDENCE_INDEX_PATH, evidence_index)
        print(f"Updated {EVIDENCE_INDEX_PATH.relative_to(ROOT).as_posix()} ({evidence_index['count']} evidence items)")

    if rebuild_sessions:
        session_summaries = build_session_summaries()
        SESSION_SUMMARIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        SESSION_SUMMARIES_PATH.write_text(session_summaries, encoding="utf-8")
        print(f"Updated {SESSION_SUMMARIES_PATH.relative_to(ROOT).as_posix()}")

    if not (rebuild_context or rebuild_evidence or rebuild_sessions):
        print("No state changes detected. Derived summaries are up to date.")

    cache = {
        "last_compacted_at": now.isoformat(),
        "source_file_fingerprints": new_fingerprints,
    }
    save_state_cache(cache)
    return (rebuild_context or rebuild_evidence or rebuild_sessions, cache)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact StudyState state into derived summaries")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the state cache and rebuild all derived files",
    )
    parser.add_argument(
        "--check-stale",
        action="store_true",
        help="Report whether compaction is needed without rewriting files",
    )
    args = parser.parse_args()

    if args.check_stale:
        stale, _ = is_stale(load_state_cache())
        if stale:
            print("State is stale. Run scripts/compact_state.py to rebuild derived summaries.")
            return 0
        print("State is up to date. No compaction needed.")
        return 0

    print("Compacting StudyState state...")
    did_work, _ = compact(force=args.force)
    if not did_work:
        print("(Use --force to rebuild anyway.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
