#!/usr/bin/env python3
"""Recommend the next StudyState action based on current time and review state.

Usage:
    python3 scripts/select_next_study_action.py \
        --now "2026-06-25T10:00:00+02:00"

Reading the review queue keeps each item's ``status`` current (scheduled, due,
overdue). The file is rewritten only when a status actually changed, so asking
for a recommendation does not dirty the worktree.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from review_state import classify_due, load_yaml, parse_now, parse_timestamp, priority_rank, save_yaml

ROOT = Path(__file__).resolve().parent.parent
REVIEW_STATE_PATH = ROOT / "reviews" / "REVIEW_STATE.yaml"
SKILL_MAP_PATH = ROOT / "state" / "SKILL_MAP.yaml"


def skill_label(skill_id: str, skill_map: dict) -> str:
    for skill in skill_map.get("skills") or []:
        if skill.get("id") == skill_id:
            return skill.get("label") or skill_id
    return skill_id


def sort_key(item: dict) -> tuple:
    """Earliest due first (by instant, not string), then higher priority."""
    due = parse_timestamp(item.get("due_at"))
    return (due.timestamp() if due else float("inf"), priority_rank(item))


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next StudyState study action")
    parser.add_argument("--now", default=None, help="ISO 8601 timestamp with timezone")
    args = parser.parse_args()

    now = parse_now(args.now)
    review_state = load_yaml(REVIEW_STATE_PATH)
    skill_map = load_yaml(SKILL_MAP_PATH)

    items = review_state.get("review_items") or []

    changed = False
    for item in items:
        status = classify_due(item, now)
        if item.get("status") != status:
            item["status"] = status
            changed = True
    if changed:
        save_yaml(REVIEW_STATE_PATH, review_state)

    due = [item for item in items if item.get("status") == "due"]
    overdue = [item for item in items if item.get("status") == "overdue"]
    total_due = len(due) + len(overdue)

    if total_due == 0:
        print("StudyState recommendation: new material is allowed.")
        print("")
        print("Due reviews: 0")
        print("Overdue reviews: 0")
        print("Recommended action: continue with the active target's next question.")
        print("Reason: no reviews are currently due or overdue.")
        return 0

    # Overdue first, then earliest due, then highest priority.
    candidates = sorted(overdue or due, key=sort_key)
    chosen = candidates[0]
    chosen_id = chosen.get("id", "<unknown>")
    chosen_skill = chosen.get("skill_id", "<unknown>")
    label = skill_label(chosen_skill, skill_map)

    print("StudyState recommendation: review first.")
    print("")
    print(f"Due reviews: {len(due)}")
    print(f"Overdue reviews: {len(overdue)}")
    print(f"Recommended action: review {chosen_id} ({label}) before new material.")

    if overdue:
        print("Reason: this review is overdue and has weak or stale evidence.")
    else:
        print("Reason: this review is due today and spaced retrieval is the highest-retention move.")

    print("")
    print('Override allowed:')
    print('Say "override review because <reason>" and the agent must record the override.')
    print("")
    print('Recommended by StudyState: review first. You can override, but this is the highest-retention move.')
    print("")
    print(
        "After the review, record the result with: python3 scripts/schedule_review.py "
        f"--review-id {chosen_id} --grade <wrong|partial|correct> --confidence <low|medium|high>"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
