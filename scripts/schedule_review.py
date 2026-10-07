#!/usr/bin/env python3
"""Create a StudyState review item, or record the result of reviewing one.

Create a review after a weak, partial, repaired, or shaky answer:

    python3 scripts/schedule_review.py \
        --skill-id skill_example \
        --evidence-id ev_001 \
        --target-id target_example \
        --grade partial \
        --confidence low \
        --now "2026-06-24T18:30:00+02:00"

Record the outcome when the learner has reviewed an existing item. A correct
recall doubles the interval (capped at 30 days, or --max-interval-days); a
partial or wrong answer counts as a lapse and resets the interval:

    python3 scripts/schedule_review.py \
        --review-id rev_skill_example_20260624_183000 \
        --grade correct \
        --confidence high

Grade: wrong | partial | correct
Confidence: low | medium | high
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import timedelta
from pathlib import Path

from review_state import (
    DEFAULT_MAX_INTERVAL_DAYS,
    compute_interval,
    load_yaml,
    parse_now,
    record_review_result,
    save_yaml,
    update_queue_entry,
)

ROOT = Path(__file__).resolve().parent.parent
REVIEW_STATE_PATH = ROOT / "reviews" / "REVIEW_STATE.yaml"
REVIEW_QUEUE_PATH = ROOT / "reviews" / "REVIEW_QUEUE.md"

SCHEDULED_HEADING = "## Scheduled"


def make_review_id(skill_id: str, now) -> str:
    stamp = now.strftime("%Y%m%d_%H%M%S")
    safe_skill = re.sub(r"[^a-zA-Z0-9_-]", "_", skill_id)
    return f"rev_{safe_skill}_{stamp}"


def add_to_queue_text(text: str, review_id: str, skill_id: str, evidence_id: str | None, due_at: str, interval: int, prompt: str) -> str:
    """Insert a review block at the end of the ``## Scheduled`` section."""
    entry = f"- **Review ID:** {review_id}\n- **Skill ID:** {skill_id}\n"
    if evidence_id:
        entry += f"- **Evidence ID:** {evidence_id}\n"
    entry += (
        f"- **Prompt:** {prompt}\n"
        f"- **Due date:** {due_at[:10]}\n"
        f"- **Interval days:** {interval}\n"
    )

    start = text.find(SCHEDULED_HEADING)
    if start == -1:
        return text.rstrip("\n") + f"\n\n{SCHEDULED_HEADING}\n\n{entry}"

    body_start = start + len(SCHEDULED_HEADING)
    next_heading = text.find("\n## ", body_start)
    section_end = len(text) if next_heading == -1 else next_heading + 1
    body = text[body_start:section_end]

    # The placeholder only holds the section open until the first real item.
    body = re.sub(r"^- None\.?[ \t]*\n", "", body.lstrip("\n"), flags=re.MULTILINE).rstrip("\n")
    pieces = [piece for piece in (body, entry.rstrip("\n")) if piece]
    new_body = "\n\n" + "\n\n".join(pieces) + "\n\n"
    return text[:body_start] + new_body + text[section_end:]


def add_to_queue(review_id: str, skill_id: str, evidence_id: str | None, due_at: str, interval: int, prompt: str) -> None:
    if not REVIEW_QUEUE_PATH.is_file():
        return
    text = REVIEW_QUEUE_PATH.read_text(encoding="utf-8")
    REVIEW_QUEUE_PATH.write_text(
        add_to_queue_text(text, review_id, skill_id, evidence_id, due_at, interval, prompt),
        encoding="utf-8",
        newline="\n",
    )


def create_review(args: argparse.Namespace) -> int:
    now = parse_now(args.now)
    interval = compute_interval(args.grade, args.confidence)
    due_at_str = (now + timedelta(days=interval)).isoformat()
    review_id = make_review_id(args.skill_id, now)

    state = load_yaml(REVIEW_STATE_PATH)
    items = state.setdefault("review_items", [])
    if any(item.get("id") == review_id for item in items):
        print(f"Error: review {review_id} already exists; use --now to change the timestamp.")
        return 1

    items.append(
        {
            "id": review_id,
            "skill_id": args.skill_id,
            "evidence_id": args.evidence_id,
            "target_id": args.target_id,
            "due_at": due_at_str,
            "last_reviewed_at": None,
            "interval_days": interval,
            "stability": None,
            "difficulty": None,
            "lapses": 0,
            "priority": "normal",
            "status": "scheduled",
            "source": args.source,
            "override_count": 0,
        }
    )
    save_yaml(REVIEW_STATE_PATH, state)
    add_to_queue(review_id, args.skill_id, args.evidence_id, due_at_str, interval, args.prompt)

    print(f"Scheduled review {review_id}")
    print(f"  skill_id: {args.skill_id}")
    print(f"  evidence_id: {args.evidence_id}")
    print(f"  grade: {args.grade}")
    print(f"  confidence: {args.confidence}")
    print(f"  interval_days: {interval}")
    print(f"  due_at: {due_at_str}")
    return 0


def record_review(args: argparse.Namespace) -> int:
    now = parse_now(args.now)
    state = load_yaml(REVIEW_STATE_PATH)
    items = state.get("review_items") or []
    item = next((entry for entry in items if entry.get("id") == args.review_id), None)
    if item is None:
        print(f"Error: no review item with id {args.review_id!r} in {REVIEW_STATE_PATH.relative_to(ROOT).as_posix()}.")
        return 1

    previous = item.get("interval_days")
    record_review_result(item, args.grade, args.confidence, now, args.max_interval_days)
    save_yaml(REVIEW_STATE_PATH, state)

    if REVIEW_QUEUE_PATH.is_file():
        text = REVIEW_QUEUE_PATH.read_text(encoding="utf-8")
        REVIEW_QUEUE_PATH.write_text(update_queue_entry(text, item), encoding="utf-8", newline="\n")

    print(f"Recorded review result for {args.review_id}")
    print(f"  grade: {args.grade}")
    print(f"  confidence: {args.confidence}")
    print(f"  interval_days: {previous} -> {item['interval_days']}")
    print(f"  lapses: {item['lapses']}")
    print(f"  due_at: {item['due_at']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Schedule a StudyState review item or record a review result")
    parser.add_argument("--skill-id", help="Create a new review item for this skill")
    parser.add_argument("--review-id", help="Record the result of reviewing this existing item")
    parser.add_argument("--evidence-id", default=None)
    parser.add_argument("--target-id", default=None)
    parser.add_argument("--grade", required=True, choices=["wrong", "incorrect", "partial", "correct"])
    parser.add_argument("--confidence", required=True, choices=["low", "medium", "high"])
    parser.add_argument("--now", default=None, help="ISO 8601 timestamp with timezone")
    parser.add_argument("--prompt", default="Review this skill using a question in a different mode than the original.")
    parser.add_argument("--source", default="missed_question", help="Why the review was scheduled")
    parser.add_argument(
        "--max-interval-days",
        type=int,
        default=DEFAULT_MAX_INTERVAL_DAYS,
        help="Upper bound for an expanded interval, for example to stay before a target deadline",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if bool(args.skill_id) == bool(args.review_id):
        parser.error("give exactly one of --skill-id (new review) or --review-id (record a result)")
    if args.max_interval_days < 1:
        parser.error("--max-interval-days must be at least 1")

    if args.review_id:
        return record_review(args)
    return create_review(args)


if __name__ == "__main__":
    sys.exit(main())
