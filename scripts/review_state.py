"""Shared review-state helpers for the StudyState scheduler and selector.

``scripts/schedule_review.py`` writes review items and
``scripts/select_next_study_action.py`` reads them. Both need the same time
parsing, due classification, interval rules, and comment-preserving YAML
writes, so they live here once.

Interval rules (see protocols/SCHEDULE_REVIEW.md):

* A first schedule uses a transparent map from grade and confidence.
* A correct recall doubles the previous interval (at least one day) and never
  exceeds the cap: 30 days unless the caller lowers it, for example to stay
  before a target deadline.
* A correct but low-confidence recall is shaky: it repeats the interval
  instead of growing it.
* A partial or wrong answer is a lapse: the lapse count goes up and the
  interval resets to the shortest window.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from state_io import load_yaml, parse_now, parse_timestamp, save_yaml

__all__ = [
    "DEFAULT_MAX_INTERVAL_DAYS",
    "classify_due",
    "compute_interval",
    "load_yaml",
    "next_interval",
    "parse_now",
    "parse_timestamp",
    "priority_rank",
    "record_review_result",
    "save_yaml",
    "update_queue_entry",
]

DEFAULT_MAX_INTERVAL_DAYS = 30
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
LAPSE_GRADES = {"wrong", "incorrect", "partial"}


def classify_due(item: dict, now: datetime) -> str:
    """Return completed, suspended, scheduled, due, or overdue for one item."""
    status = item.get("status")
    if status in ("completed", "suspended"):
        return status
    due_at = parse_timestamp(item.get("due_at"))
    if due_at is None:
        return "scheduled"
    if due_at <= now:
        if due_at < now - timedelta(days=1):
            return "overdue"
        return "due"
    return "scheduled"


def priority_rank(item: dict) -> int:
    return PRIORITY_RANK.get(str(item.get("priority") or "normal").lower(), 1)


def compute_interval(grade: str, confidence: str, lapses: int = 0) -> int:
    """First-schedule interval in days for a grade and confidence."""
    grade = grade.lower()
    confidence = confidence.lower()

    if grade in ("wrong", "incorrect"):
        interval = 0 if confidence == "low" else 1
    elif grade == "partial":
        interval = 1
    elif grade == "correct":
        interval = {"low": 2, "medium": 4}.get(confidence, 7)
    else:
        interval = 1

    if lapses > 0:
        # A lapse resets the interval to the shortest meaningful window.
        interval = min(interval, 1)

    return interval


def next_interval(
    previous_interval: int | None,
    grade: str,
    confidence: str,
    lapses: int,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> int:
    """Interval after reviewing an existing item.

    ``lapses`` is the count *after* this review, so a lapse grade is always
    scored with at least one lapse and resets to the shortest window. A correct
    review is judged on its own: past lapses already reset the previous
    interval, so they are not applied a second time.
    """
    if grade.lower() in LAPSE_GRADES:
        return compute_interval(grade, confidence, max(lapses, 1))
    previous = max(int(previous_interval or 0), 0)
    if confidence.lower() == "low":
        grown = max(1, previous)
    else:
        grown = max(1, previous * 2)
    return min(max_interval_days, grown)


def record_review_result(
    item: dict,
    grade: str,
    confidence: str,
    now: datetime,
    max_interval_days: int = DEFAULT_MAX_INTERVAL_DAYS,
) -> dict:
    """Apply one completed review to ``item`` in place and return it."""
    grade = grade.lower()
    lapses = int(item.get("lapses") or 0)
    if grade in LAPSE_GRADES:
        lapses += 1
    interval = next_interval(item.get("interval_days"), grade, confidence, lapses, max_interval_days)

    item["lapses"] = lapses
    item["interval_days"] = interval
    item["last_reviewed_at"] = now.isoformat()
    item["due_at"] = (now + timedelta(days=interval)).isoformat()
    item["last_result"] = grade
    item["status"] = "scheduled"
    return item


def update_queue_entry(text: str, item: dict) -> str:
    """Refresh one item's block in the human-readable REVIEW_QUEUE.md mirror.

    The mirror is a courtesy view; the YAML is the source of truth. If the item
    has no block, the text is returned unchanged.
    """
    review_id = item["id"]
    pattern = re.compile(
        r"(^- \*\*Review ID:\*\* " + re.escape(review_id) + r"\n)(.*?)(?=^- \*\*Review ID:\*\*|^## |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return text

    fields = {
        "Due date": str(item.get("due_at") or "")[:10],
        "Interval days": str(item.get("interval_days")),
        "Lapse count": str(item.get("lapses") or 0),
        "Last result": str(item.get("last_result") or ""),
    }
    body = match.group(2)
    stripped = body.rstrip("\n")
    separator = body[len(stripped):]
    lines = stripped.split("\n") if stripped else []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        for label, value in fields.items():
            if line.startswith(f"- **{label}:**"):
                lines[index] = f"- **{label}:** {value}"
                seen.add(label)
    for label, value in fields.items():
        if label not in seen and value != "":
            lines.append(f"- **{label}:** {value}")
    new_body = "\n".join(lines) + (separator or "\n")
    return text[: match.start(2)] + new_body + text[match.end(2):]
