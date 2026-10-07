#!/usr/bin/env python3
"""The template's primary journey: cast, study, review, check a source, update.

This is the smallest real run of the outcome in PROJECT.md. It uses the same scripts
a coding agent uses, in a throwaway directory, and prints what it proves:

1. Cast a learner instance from THIS checkout. It validates, carries its own
   ProjectState gate (honestly red), and holds none of the template's maintenance files.
2. Run a study loop: a weak answer becomes a review; the selector says review first
   when it is due; the learner's review result expands the interval; the validator
   accepts the state at every step.
3. A volatile target routes to a source check; recording the check ends the routing.
4. Release a change in a copy of the template, then update the instance from it:
   template-owned files and the contract block change, learner state, local rules,
   and the ProjectState files do not, and the instance still validates.

Exit 0 only if every step holds. A green unit-test suite is not this journey.
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402
import testkit  # noqa: E402

ROOT = testkit.ROOT
T0 = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)
LOCAL_RULE = "- Explain in plain Dutch; keep sessions under twenty minutes.\n"


def step(message: str) -> None:
    print(f"\n== {message}")


def check(condition: bool, message: str) -> None:
    print(f"   {'ok  ' if condition else 'FAIL'} {message}")
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    print("StudyState primary journey")
    print("==========================")
    with testkit.tempdir("studystate-journey-") as tmp:
        work = Path(tmp)

        step("1. Cast an instance from this checkout")
        inst = testkit.make_learner_instance(work)
        check(testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 0, "the instance passes check_studydd.py")
        gate = testkit.script("projectstate_gate.py", cwd=inst, check=False)
        check(gate.returncode == 1 and "WARN" not in gate.stdout, "its ProjectState gate is honestly red (exit 1), with no size warning")
        check(not (inst / "core").exists() and not (inst / "CHANGELOG.md").exists(), "no template maintenance files were copied")
        check((inst / own.LOCK_PATH).is_file(), "it recorded a lock of the template files it received")

        step("2. Study loop: weak answer, review due, review done")
        (inst / "targets" / testkit.TARGET_ID / "TARGET.yaml").write_text(
            f"---\nid: {testkit.TARGET_ID}\ntype: certification\ntitle: Journey target\nvolatility: stable\nstudy_skill: it_certification\n",
            encoding="utf-8",
        )
        plan = testkit.script("plan_learning_activity.py", cwd=inst).stdout
        check("StudyState recommendation:" in plan, "the planner recommends an activity")

        testkit.script(
            "schedule_review.py", "--skill-id", testkit.SKILL_ID, "--evidence-id", testkit.EVIDENCE_ID, "--target-id", testkit.TARGET_ID,
            "--grade", "partial", "--confidence", "low", "--now", T0.isoformat(), cwd=inst,
        )
        review_id = f"rev_{testkit.SKILL_ID}_20261007_100000"
        before_due = testkit.script("select_next_study_action.py", "--now", (T0 + timedelta(hours=12)).isoformat(), cwd=inst).stdout
        check("new material is allowed" in before_due, "before the due time the selector allows new material")
        due = testkit.script("select_next_study_action.py", "--now", (T0 + timedelta(hours=25)).isoformat(), cwd=inst).stdout
        check("review first" in due and review_id in due, "when the review is due the selector says review first, and names it")
        check(f"--review-id {review_id}" in due, "it prints the command that records the result")

        done_at = T0 + timedelta(hours=25)
        testkit.script("schedule_review.py", "--review-id", review_id, "--grade", "correct", "--confidence", "high", "--now", done_at.isoformat(), cwd=inst)
        item = testkit.load_yaml(inst / "reviews" / "REVIEW_STATE.yaml")["review_items"][0]
        check(item["interval_days"] == 2 and item["last_result"] == "correct", "a correct recall doubled the interval to 2 days")
        after = testkit.script("select_next_study_action.py", "--now", (done_at + timedelta(hours=1)).isoformat(), cwd=inst).stdout
        check("new material is allowed" in after, "the finished review is no longer due")
        testkit.script("schedule_review.py", "--review-id", review_id, "--grade", "wrong", "--confidence", "low", "--now", (done_at + timedelta(days=2)).isoformat(), cwd=inst)
        item = testkit.load_yaml(inst / "reviews" / "REVIEW_STATE.yaml")["review_items"][0]
        check((item["interval_days"], item["lapses"]) == (0, 1), "a lapse reset the interval to same-day and counted")
        check(testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 0, "a same-day review is valid state for the validator")
        testkit.script("validate_touched_state.py", "--skill-id", testkit.SKILL_ID, "--evidence-id", testkit.EVIDENCE_ID, cwd=inst)
        check(True, "the targeted validator accepts the touched records")

        step("3. A volatile target needs a source check, and recording it closes the loop")
        # Let the lapsed review stop competing with the activity router.
        state_path = inst / "reviews" / "REVIEW_STATE.yaml"
        reviews = testkit.load_yaml(state_path)
        reviews["review_items"][0]["due_at"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        testkit.save_yaml(state_path, reviews)
        (inst / "targets" / testkit.TARGET_ID / "TARGET.yaml").write_text(
            f"---\nid: {testkit.TARGET_ID}\ntype: certification\ntitle: Journey target\nvolatility: volatile\nstudy_skill: it_certification\n",
            encoding="utf-8",
        )
        routed = testkit.script("plan_learning_activity.py", cwd=inst).stdout
        check("recent_info_check" in routed, "the target turned volatile: with no source state the planner asks for a source check")
        check(testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 1, "and the validator refuses a volatile target with no fresh source")
        checked = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        testkit.script(
            "record_source_check.py", "journey-official", "--target-id", testkit.TARGET_ID, "--outcome", "fresh",
            "--authority", "official", "--volatility", "volatile", "--checked-at", checked, "--summary", "Official docs verified.",
            cwd=inst,
        )
        rerouted = testkit.script("plan_learning_activity.py", cwd=inst).stdout
        check("recent_info_check" not in rerouted, "once the check is recorded the planner moves on")
        text = (inst / "sources" / "SOURCE_STATE.yaml").read_text(encoding="utf-8")
        check(text.startswith("---") or text.startswith("#"), "SOURCE_STATE.yaml kept its header comments")
        testkit.script("compact_state.py", cwd=inst)
        check(testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 0, "the instance validates after compaction")

        step("4. Release a change in the template and update the instance")
        agents = inst / "AGENTS.md"
        agents.write_text(agents.read_text(encoding="utf-8").replace("## Local rules\n", "## Local rules\n\n" + LOCAL_RULE, 1), encoding="utf-8")
        testkit.commit_all(inst, "learner baseline")
        learner_files = [
            "state/STUDY_STATE.yaml", "state/SKILL_MAP.yaml", "state/EVIDENCE_LOG.md", "reviews/REVIEW_STATE.yaml",
            "sources/SOURCE_STATE.yaml", "targets/kit-target/TARGET.yaml", "PROJECT.md", "STATE.yaml",
            "scripts/projectstate_gate.py",
        ]
        before = {p: digest(inst / p) for p in learner_files}

        template = testkit.copy_template(work, "Template_Next")
        (template / "protocols" / "JOURNEY_NEW.md").write_text("# A new protocol\n", encoding="utf-8")
        ask = template / "protocols" / "ASK_QUESTION.md"
        ask.write_text(ask.read_text(encoding="utf-8") + "\nA refined rule.\n", encoding="utf-8")
        core = template / own.CORE_BLOCK_PATH
        core.write_text(core.read_text(encoding="utf-8") + "\n## Journey section\n\nNew contract text.\n", encoding="utf-8")
        version = template / own.VERSION_PATH
        version.write_text(version.read_text(encoding="utf-8").replace('template_version: "0.12.0"', 'template_version: "0.12.1"'), encoding="utf-8")
        testkit.script("template_release.py", "sync", cwd=template)
        testkit.commit_all(template, "release 0.12.1")

        dry = testkit.script("update_instance.py", "--target", str(inst), cwd=template, check=False)
        check(dry.returncode == 0 and "Dry run: nothing was written" in dry.stdout, "the dry run reports the plan and writes nothing")
        check(testkit.git(inst, "status", "--porcelain") == "", "the instance is untouched after the dry run")
        applied = testkit.script("update_instance.py", "--target", str(inst), "--apply", cwd=template, check=False)
        check(applied.returncode == 0, "the update applies")
        check((inst / "protocols" / "JOURNEY_NEW.md").is_file() and "A refined rule." in (inst / "protocols" / "ASK_QUESTION.md").read_text(encoding="utf-8"),
              "template-owned files changed")
        new_agents = agents.read_text(encoding="utf-8")
        check("New contract text." in new_agents and LOCAL_RULE in new_agents, "the contract block changed and the local rule survived")
        check({p: digest(inst / p) for p in learner_files} == before, "learner state, targets, and the ProjectState files are byte-identical")
        check(testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 0, "the updated instance still validates")
        check(testkit.script("update_instance.py", "--target", str(inst), "--check", cwd=template, check=False).returncode == 0, "a second check finds nothing left to do")

        print("\nJOURNEY PASSED: cast, study, review, source check, update.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"\nJOURNEY FAILED: {exc}")
        sys.exit(1)
