#!/usr/bin/env python3
"""Targeted StudyState validator for fast-path state updates.

Validates only the IDs touched by an ordinary tutoring turn. This is the fast-path
gate after small updates. It is not a replacement for the full validator, which
runs at session boundaries, CI, audit, and repair.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKILL_MAP_PATH = ROOT / "state" / "SKILL_MAP.yaml"
EVIDENCE_INDEX_PATH = ROOT / "state" / "EVIDENCE_INDEX.yaml"
REVIEW_STATE_PATH = ROOT / "reviews" / "REVIEW_STATE.yaml"
STUDY_STATE_PATH = ROOT / "state" / "STUDY_STATE.yaml"
NEXT_ACTIONS_PATH = ROOT / "NEXT_ACTIONS.md"
SESSION_LOG_PATH = ROOT / "sessions" / "SESSION_LOG.md"
EVIDENCE_LOG_PATH = ROOT / "state" / "EVIDENCE_LOG.md"


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


def parse_iso(value: str | None) -> datetime | None:
    """Accept date-only or timezone-aware datetime strings."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        # Date-only values are valid for evidence/review timestamps in StudyState.
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0 and dt.tzinfo is None:
            return dt
        if dt.tzinfo is None:
            return None
        return dt
    except Exception:
        return None


def load_skill_map() -> dict:
    return load_yaml(SKILL_MAP_PATH)


def load_evidence_index() -> dict:
    return load_yaml(EVIDENCE_INDEX_PATH)


def load_review_state() -> dict:
    return load_yaml(REVIEW_STATE_PATH)


def load_study_state() -> dict:
    return load_yaml(STUDY_STATE_PATH)


def skill_by_id(skill_map: dict, skill_id: str) -> dict | None:
    for skill in skill_map.get("skills") or []:
        if skill.get("id") == skill_id:
            return skill
    return None


def evidence_by_id(evidence_index: dict, evidence_id: str) -> dict | None:
    for item in evidence_index.get("items") or []:
        if item.get("evidence_id") == evidence_id:
            return item
    return None


def find_evidence(evidence_id: str) -> tuple[dict | None, bool]:
    """Look an evidence ID up, returning the record and whether the index was stale.

    ``state/EVIDENCE_INDEX.yaml`` is derived by ``compact_state.py``, which the fast
    path deliberately does not run on every turn. Evidence appended since the last
    compaction is therefore missing from it. The audit log is the source of truth, so
    a miss falls back to one targeted parse of it instead of failing a fresh append.
    """
    item = evidence_by_id(load_evidence_index(), evidence_id)
    if item:
        return item, False
    if not EVIDENCE_LOG_PATH.is_file():
        return None, False
    from compact_state import parse_evidence_items

    text = EVIDENCE_LOG_PATH.read_text(encoding="utf-8")
    for candidate in parse_evidence_items(text):
        if candidate.get("evidence_id") == evidence_id:
            return candidate, True
    return None, False


def review_by_id(review_state: dict, review_id: str) -> dict | None:
    for item in review_state.get("review_items") or []:
        if item.get("id") == review_id:
            return item
    return None


def validate_skill(skill_id: str) -> list[str]:
    errors: list[str] = []
    skill_map = load_skill_map()
    skill = skill_by_id(skill_map, skill_id)
    if not skill:
        errors.append(f"Skill '{skill_id}' not found in state/SKILL_MAP.yaml")
        return errors

    readiness = skill.get("readiness")
    status = skill.get("status")
    evidence = skill.get("evidence") or []

    if readiness is not None:
        try:
            readiness_val = int(readiness)
            if not 0 <= readiness_val <= 100:
                errors.append(f"Skill '{skill_id}' readiness out of range (0-100): {readiness_val}")
        except (TypeError, ValueError):
            errors.append(f"Skill '{skill_id}' readiness is not an integer: {readiness}")

    if status in ("practiced", "confirmed", "demonstrated") and not evidence:
        errors.append(f"Skill '{skill_id}' status '{status}' has no evidence references")

    if readiness is not None:
        try:
            readiness_val = int(readiness)
            if readiness_val >= 70 and len(evidence) < 2:
                errors.append(
                    f"Skill '{skill_id}' readiness {readiness_val} has fewer than 2 evidence references; "
                    "varied evidence cannot be verified"
                )
        except (TypeError, ValueError):
            pass

    return errors


def validate_evidence(evidence_id: str) -> list[str]:
    errors: list[str] = []
    item, from_log = find_evidence(evidence_id)
    if not item:
        errors.append(f"Evidence '{evidence_id}' not found in state/EVIDENCE_INDEX.yaml or state/EVIDENCE_LOG.md")
        return errors
    if from_log:
        print(f"Note: '{evidence_id}' is in the evidence log but not yet in the index; compact_state.py refreshes it at the session boundary.")

    skill_id = item.get("skill_id")
    if skill_id and not skill_by_id(load_skill_map(), skill_id):
        errors.append(f"Evidence '{evidence_id}' references unknown skill '{skill_id}'")

    date = item.get("date")
    if date and not parse_iso(date):
        errors.append(f"Evidence '{evidence_id}' has malformed date '{date}'")

    return errors


def validate_review(review_id: str) -> list[str]:
    errors: list[str] = []
    review_state = load_review_state()
    item = review_by_id(review_state, review_id)
    if not item:
        errors.append(f"Review '{review_id}' not found in reviews/REVIEW_STATE.yaml")
        return errors

    skill_id = item.get("skill_id")
    evidence_id = item.get("evidence_id")

    if skill_id and not skill_by_id(load_skill_map(), skill_id):
        errors.append(f"Review '{review_id}' references unknown skill '{skill_id}'")

    if evidence_id and not find_evidence(evidence_id)[0]:
        errors.append(f"Review '{review_id}' references unknown evidence '{evidence_id}'")

    due_at = item.get("due_at")
    if due_at and not parse_iso(due_at):
        errors.append(f"Review '{review_id}' has malformed due_at timestamp '{due_at}'")

    last_reviewed = item.get("last_reviewed_at")
    if last_reviewed and not parse_iso(last_reviewed):
        errors.append(f"Review '{review_id}' has malformed last_reviewed_at timestamp '{last_reviewed}'")

    return errors


def validate_session(session_id: str) -> list[str]:
    errors: list[str] = []
    if not SESSION_LOG_PATH.is_file():
        errors.append("sessions/SESSION_LOG.md not found")
        return errors

    text = SESSION_LOG_PATH.read_text(encoding="utf-8")
    # session_id may be a date or an identifier mentioned in the session entry.
    if session_id not in text:
        errors.append(f"Session reference '{session_id}' not found in sessions/SESSION_LOG.md")
        return errors

    # Extract evidence references and validate them.
    id_token = r"[\w\-]*[\d\-][\w\-]*"
    for match in re.finditer(
        rf"\*\*Evidence added:\*\*[ \t]+({id_token}(?:,\s*{id_token})*)", text
    ):
        refs = [r.strip() for r in match.group(1).split(",") if r.strip()]
        for ref in refs:
            if ref.lower() in ("none", "n/a", "-", ""):
                continue
            if not find_evidence(ref)[0]:
                errors.append(f"Session log evidence reference '{ref}' not found in the index or the evidence log")

    return errors


def validate_active_question(question_id: str) -> list[str]:
    errors: list[str] = []
    study_state = load_study_state()
    active_focus = study_state.get("active_focus") or {}
    state_question = active_focus.get("next_question")

    if state_question and state_question != question_id:
        errors.append(
            f"Active question ID in state/STUDY_STATE.yaml is '{state_question}', "
            f"but validation requested '{question_id}'"
        )

    if NEXT_ACTIONS_PATH.is_file():
        next_text = NEXT_ACTIONS_PATH.read_text(encoding="utf-8")
        if question_id not in next_text:
            errors.append(f"Question ID '{question_id}' not found in NEXT_ACTIONS.md")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate only the StudyState IDs touched in a fast-path update")
    parser.add_argument("--skill-id", help="Skill ID to validate")
    parser.add_argument("--evidence-id", help="Evidence ID to validate")
    parser.add_argument("--review-id", help="Review ID to validate")
    parser.add_argument("--session-id", help="Session reference (e.g., date) to validate")
    parser.add_argument("--active-question", help="Active question ID to validate")
    args = parser.parse_args()

    errors: list[str] = []

    if args.skill_id:
        errors.extend(validate_skill(args.skill_id))
    if args.evidence_id:
        errors.extend(validate_evidence(args.evidence_id))
    if args.review_id:
        errors.extend(validate_review(args.review_id))
    if args.session_id:
        errors.extend(validate_session(args.session_id))
    if args.active_question:
        errors.extend(validate_active_question(args.active_question))

    if not any([args.skill_id, args.evidence_id, args.review_id, args.session_id, args.active_question]):
        print("No ID specified. Use --skill-id, --evidence-id, --review-id, --session-id, or --active-question.")
        return 0

    if errors:
        print("Targeted validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Targeted validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
