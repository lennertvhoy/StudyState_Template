#!/usr/bin/env python3
"""Tests for the review lifecycle: schedule, review, reschedule.

Covers the interval rules, the REVIEW_QUEUE.md mirror, the validator's view of
scheduler output (a same-day review must be valid state), comment-preserving
YAML writes, and the selector's no-churn read.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_state as rs  # noqa: E402
import schedule_review as sr  # noqa: E402
import testkit  # noqa: E402

NOW = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)

QUEUE = (
    "# REVIEW_QUEUE\n\n## Due now\n\n- None.\n\n## Scheduled\n\n- None.\n\n"
    "## Rules\n\n- Keep this section.\n"
)


def test_first_schedule_intervals_match_policy() -> None:
    assert rs.compute_interval("wrong", "low") == 0
    assert rs.compute_interval("wrong", "high") == 1
    assert rs.compute_interval("partial", "high") == 1
    assert rs.compute_interval("correct", "low") == 2
    assert rs.compute_interval("correct", "medium") == 4
    assert rs.compute_interval("correct", "high") == 7
    assert rs.compute_interval("correct", "high", lapses=1) == 1


def test_correct_recall_doubles_up_to_the_cap() -> None:
    item = {"id": "r", "interval_days": 7, "lapses": 0}
    rs.record_review_result(item, "correct", "high", NOW)
    assert item["interval_days"] == 14
    rs.record_review_result(item, "correct", "high", NOW)
    assert item["interval_days"] == 28
    rs.record_review_result(item, "correct", "high", NOW)
    assert item["interval_days"] == 30, "expansion is capped at 30 days"
    rs.record_review_result(item, "correct", "high", NOW, max_interval_days=10)
    assert item["interval_days"] == 10, "a caller-supplied cap (for example a deadline) wins"
    assert item["last_result"] == "correct"
    assert item["due_at"] == (NOW + timedelta(days=10)).isoformat()


def test_same_day_review_becomes_at_least_one_day() -> None:
    item = {"id": "r", "interval_days": 0, "lapses": 0}
    rs.record_review_result(item, "correct", "medium", NOW)
    assert item["interval_days"] == 1


def test_shaky_correct_recall_repeats_instead_of_growing() -> None:
    item = {"id": "r", "interval_days": 4, "lapses": 0}
    rs.record_review_result(item, "correct", "low", NOW)
    assert item["interval_days"] == 4
    rs.record_review_result(item, "correct", "medium", NOW)
    assert item["interval_days"] == 8, "a confident recall resumes doubling"


def test_lapse_resets_interval_and_counts() -> None:
    item = {"id": "r", "interval_days": 14, "lapses": 0}
    rs.record_review_result(item, "partial", "medium", NOW)
    assert (item["interval_days"], item["lapses"]) == (1, 1)
    rs.record_review_result(item, "wrong", "low", NOW)
    assert (item["interval_days"], item["lapses"]) == (0, 2), "wrong + low confidence is due again today"
    rs.record_review_result(item, "correct", "high", NOW)
    assert item["interval_days"] == 1, "recovery climbs from the reset, not from the old 14 days"
    rs.record_review_result(item, "correct", "high", NOW)
    assert item["interval_days"] == 2, "past lapses do not cap later successes"
    assert item["lapses"] == 2, "a correct review does not erase the lapse history"


def test_queue_insertion_keeps_items_under_scheduled() -> None:
    text = sr.add_to_queue_text(QUEUE, "rev_a", "skill_a", "ev_1", "2026-10-08T10:00:00+00:00", 1, "Prompt A")
    text = sr.add_to_queue_text(text, "rev_b", "skill_b", None, "2026-10-09T10:00:00+00:00", 2, "Prompt B")
    scheduled = text.index("## Scheduled")
    rules = text.index("## Rules")
    assert scheduled < text.index("rev_a") < text.index("rev_b") < rules, "both items sit inside ## Scheduled"
    assert "- None." in text[: scheduled], "the Due now placeholder is untouched"
    assert text.count("- None.") == 1, "the Scheduled placeholder is replaced by the first item"
    assert "- Keep this section." in text[rules:]


def test_queue_mirror_updates_after_a_review() -> None:
    text = sr.add_to_queue_text(QUEUE, "rev_a", "skill_a", "ev_1", "2026-10-08T10:00:00+00:00", 1, "Prompt A")
    text = sr.add_to_queue_text(text, "rev_b", "skill_b", None, "2026-10-09T10:00:00+00:00", 2, "Prompt B")
    item = {"id": "rev_a", "interval_days": 1, "lapses": 0}
    rs.record_review_result(item, "correct", "high", NOW)
    updated = rs.update_queue_entry(text, item)
    block_a = updated[updated.index("rev_a"): updated.index("rev_b")]
    assert "- **Due date:** 2026-10-09" in block_a
    assert "- **Interval days:** 2" in block_a
    assert "- **Last result:** correct" in block_a
    block_b = updated[updated.index("rev_b"): updated.index("## Rules")]
    assert "- **Due date:** 2026-10-09" in block_b, "other items are untouched"
    assert "- **Last result:" not in block_b
    assert rs.update_queue_entry(text, {"id": "rev_missing", "interval_days": 1}) == text


def test_yaml_header_comments_survive_a_rewrite() -> None:
    with testkit.tempdir("studystate-yaml-") as tmp:
        path = Path(tmp) / "state.yaml"
        path.write_text("---\n# Header line one\n# Header line two\n\nreview_items: []\n", encoding="utf-8")
        rs.save_yaml(path, {"review_items": [{"id": "a"}]})
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# Header line one\n# Header line two\n")
        assert rs.load_yaml(path) == {"review_items": [{"id": "a"}]}


def test_zero_day_review_is_valid_state_end_to_end() -> None:
    """Regression: wrong + low confidence produced interval_days 0, which the validator rejected."""
    with testkit.tempdir("studystate-review-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        testkit.script("check_studydd.py", cwd=inst)

        out = testkit.script(
            "schedule_review.py", "--skill-id", testkit.SKILL_ID, "--evidence-id", testkit.EVIDENCE_ID,
            "--target-id", testkit.TARGET_ID, "--grade", "wrong", "--confidence", "low",
            "--now", "2026-10-07T10:00:00+00:00", cwd=inst,
        ).stdout
        assert "interval_days: 0" in out
        review_id = f"rev_{testkit.SKILL_ID}_20261007_100000"
        result = testkit.script("check_studydd.py", cwd=inst, check=False)
        assert result.returncode == 0, result.stdout + result.stderr

        # Same-day review: due immediately, and the selector says review first.
        selected = testkit.script("select_next_study_action.py", "--now", "2026-10-07T10:00:00+00:00", cwd=inst).stdout
        assert "review first" in selected and review_id in selected
        assert "--review-id " + review_id in selected, "the selector names the command that closes the loop"


def test_full_review_cycle_end_to_end() -> None:
    with testkit.tempdir("studystate-review-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        review_path = inst / "reviews" / "REVIEW_STATE.yaml"
        schema_doc = "# Machine-readable review state for StudyState."
        assert schema_doc in review_path.read_text(encoding="utf-8"), "the template documents its schema in the file"

        testkit.script(
            "schedule_review.py", "--skill-id", testkit.SKILL_ID, "--evidence-id", testkit.EVIDENCE_ID,
            "--grade", "partial", "--confidence", "medium", "--now", "2026-10-07T10:00:00+00:00", cwd=inst,
        )
        review_id = f"rev_{testkit.SKILL_ID}_20261007_100000"

        # A recommendation that changes nothing must not rewrite the file.
        before = review_path.read_bytes()
        testkit.script("select_next_study_action.py", "--now", "2026-10-07T12:00:00+00:00", cwd=inst)
        assert review_path.read_bytes() == before, "reading must not dirty the worktree"

        # Due tomorrow: the selector refreshes status once and the file then changes.
        testkit.script("select_next_study_action.py", "--now", "2026-10-08T10:30:00+00:00", cwd=inst)
        assert testkit.load_yaml(review_path)["review_items"][0]["status"] == "due"

        # Successive correct reviews expand the interval and keep the item valid.
        for expected in (2, 4, 8):
            testkit.script(
                "schedule_review.py", "--review-id", review_id, "--grade", "correct", "--confidence", "medium",
                "--now", "2026-10-08T10:30:00+00:00", cwd=inst,
            )
            item = testkit.load_yaml(review_path)["review_items"][0]
            assert item["interval_days"] == expected, item
        assert item["lapses"] == 0 and item["last_result"] == "correct" and item["status"] == "scheduled"

        queue = (inst / "reviews" / "REVIEW_QUEUE.md").read_text(encoding="utf-8")
        assert "- **Interval days:** 8" in queue and "- **Last result:** correct" in queue
        assert queue.index(review_id) < queue.index("## Review item format"), "the item stays under Scheduled"

        # A lapse resets, and the validator still accepts the state.
        testkit.script(
            "schedule_review.py", "--review-id", review_id, "--grade", "wrong", "--confidence", "high",
            "--now", "2026-10-20T10:00:00+00:00", cwd=inst,
        )
        item = testkit.load_yaml(review_path)["review_items"][0]
        assert (item["interval_days"], item["lapses"]) == (1, 1)
        assert schema_doc in review_path.read_text(encoding="utf-8"), "the schema documentation survives rewrites"
        result = testkit.script("check_studydd.py", cwd=inst, check=False)
        assert result.returncode == 0, result.stdout + result.stderr


def test_cli_rejects_ambiguous_and_unknown_requests() -> None:
    with testkit.tempdir("studystate-review-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        both = testkit.script(
            "schedule_review.py", "--skill-id", "a", "--review-id", "b", "--grade", "correct", "--confidence", "low",
            cwd=inst, check=False,
        )
        assert both.returncode == 2
        neither = testkit.script("schedule_review.py", "--grade", "correct", "--confidence", "low", cwd=inst, check=False)
        assert neither.returncode == 2
        missing = testkit.script(
            "schedule_review.py", "--review-id", "rev_nope", "--grade", "correct", "--confidence", "low",
            cwd=inst, check=False,
        )
        assert missing.returncode == 1 and "no review item" in missing.stdout


def main() -> int:
    tests = [
        test_first_schedule_intervals_match_policy,
        test_correct_recall_doubles_up_to_the_cap,
        test_same_day_review_becomes_at_least_one_day,
        test_shaky_correct_recall_repeats_instead_of_growing,
        test_lapse_resets_interval_and_counts,
        test_queue_insertion_keeps_items_under_scheduled,
        test_queue_mirror_updates_after_a_review,
        test_yaml_header_comments_survive_a_rewrite,
        test_zero_day_review_is_valid_state_end_to_end,
        test_full_review_cycle_end_to_end,
        test_cli_rejects_ambiguous_and_unknown_requests,
    ]
    failed: list[tuple[str, BaseException]] = []
    for test in tests:
        print(f"Running {test.__name__}...")
        try:
            test()
            print("  passed")
        except BaseException as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            print(f"  failed: {exc}")
            failed.append((test.__name__, exc))
    if failed:
        print("\nFailed tests:")
        for name, exc in failed:
            print(f"  - {name}: {exc}")
        return 1
    print("\nAll review lifecycle tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
