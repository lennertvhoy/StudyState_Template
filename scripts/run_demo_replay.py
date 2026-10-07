#!/usr/bin/env python3
"""Deterministic public demo replay for StudyState.

Creates a temporary learner instance, simulates one question/answer/grade
cycle, schedules a review, demonstrates review-first selection, records an
override, validates the result, and prints a human-readable transcript.

This script does not call AI. All learner data is fake and public-safe.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def load_yaml(path: Path) -> dict:
    import yaml

    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_instance(target: Path, remote: str) -> None:
    result = run(
        [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote],
        ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/create_instance.py"])


def switch_to_learner_instance(target: Path) -> None:
    mode_path = target / "state" / "STUDYDD_MODE.yaml"
    mode_data = load_yaml(mode_path)
    mode_data["mode"] = "learner_instance"
    mode_data["personalized"] = True
    mode_data["public_safe"] = "false_or_review_required"
    save_yaml(mode_path, mode_data)


def initialize_learner_profile(target: Path) -> None:
    study_state_path = target / "state" / "STUDY_STATE.yaml"
    study_state = load_yaml(study_state_path)
    study_state["learner"]["name"] = "Demo Learner"
    study_state["learner"]["target"] = "AI Search Fundamentals Demo"
    study_state["learner"]["current_context"] = "Public demo replay"
    study_state["active_target_id"] = "demo-ai-search-exam"
    study_state["active_focus"]["current_topic"] = "keyword vs vector search"
    study_state["active_focus"]["next_question"] = "Q-DEMO-001"
    study_state["study_target"]["title"] = "AI Search Fundamentals Demo"
    study_state["study_target"]["exam_or_goal"] = "Understand keyword, vector, and hybrid retrieval"
    study_state["study_target"]["deadline"] = "2026-12-31"
    study_state["study_target"]["current_readiness_estimate"] = "20%"
    study_state["study_target"]["readiness_confidence"] = "Low"
    study_state["workflow"]["happy_path_step"] = 5
    study_state["workflow"]["stage"] = "active_tutoring"
    save_yaml(study_state_path, study_state)


def initialize_sources(target: Path) -> None:
    source_index_path = target / "sources" / "SOURCE_INDEX.md"
    source_index_path.write_text(
        "# Source Index\n\n"
        "Trusted sources for the demo target.\n\n"
        "- **Source ID:** demo-official\n"
        "  - **Type:** official\n"
        "  - **Authority:** high\n"
        "  - **Title:** AI Search Fundamentals Official Guide\n"
        "  - **URL:** https://example.com/demo-source\n"
        "  - **Last checked:** 2026-06-24\n",
        encoding="utf-8",
    )

    source_state_path = target / "sources" / "SOURCE_STATE.yaml"
    source_state_path.write_text(
        "---\n"
        "sources:\n"
        "  - id: mslearn_ai_search_overview\n"
        "    title: \"Azure AI Search overview\"\n"
        "    url: \"https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search\"\n"
        "    authority: official\n"
        "    target_ids:\n"
        "      - demo-ai-search-exam\n"
        "    volatility: volatile\n"
        "    last_checked_at: \"2026-06-24T12:00:00+00:00\"\n"
        "    expires_at: \"2026-07-24T12:00:00+00:00\"\n"
        "    checked_by: \"demo_replay\"\n"
        "    notes: \"Demo fixture. Timestamp is deterministic test metadata, not a live source refresh.\"\n"
        "    usable_for_questions: true\n",
        encoding="utf-8",
    )


def initialize_target(target: Path) -> None:
    target_dir = target / "targets" / "demo-ai-search-exam"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "TARGET.yaml").write_text(
        "---\n"
        "id: demo-ai-search-exam\n"
        "type: skill\n"
        "title: AI Search Fundamentals Demo\n"
        "description: A fictional, public-safe demo target for showing the StudyState learning loop.\n"
        "volatility: volatile\n"
        "study_skill: it_certification\n",
        encoding="utf-8",
    )

    skill_map_path = target / "state" / "SKILL_MAP.yaml"
    skill_map = load_yaml(skill_map_path)
    skill_map["skills"] = [
        {
            "id": "demo-search-basics",
            "label": "Keyword vs vector search",
            "status": "weak",
            "readiness": 35,
            "confidence": "low",
            "evidence": ["ev_demo_001"],
            "next_validation_question": "Q-DEMO-001",
        },
        {
            "id": "demo-hybrid-retrieval",
            "label": "Hybrid retrieval design",
            "status": "pending",
            "readiness": 0,
            "confidence": "low",
            "evidence": [],
            "next_validation_question": "Q-DEMO-002",
        },
        {
            "id": "demo-eval-relevance",
            "label": "Retrieval relevance metrics",
            "status": "pending",
            "readiness": 0,
            "confidence": "low",
            "evidence": [],
            "next_validation_question": "Q-DEMO-003",
        },
    ]
    save_yaml(skill_map_path, skill_map)

    questions_dir = target_dir / "questions"
    questions_dir.mkdir(parents=True, exist_ok=True)
    (questions_dir / "Q-DEMO-001.yaml").write_text(
        "---\n"
        "id: Q-DEMO-001\n"
        "target_id: demo-ai-search-exam\n"
        "skill_id: demo-search-basics\n"
        "cognitive_level: explain\n"
        "difficulty: 2\n"
        "source_ids:\n"
        "  - mslearn_ai_search_overview\n"
        "volatility: volatile\n"
        "question_mode: authoritative_current\n"
        "question_quality:\n"
        "  generated_from_memory_allowed: false\n"
        "  quality_gate: pass\n"
        "  quality_gate_reason: \"Fresh official source available.\"\n"
        "public_prompt: >\n"
        "  Explain the difference between keyword search and vector search, and describe one situation\n"
        "  where you would combine them.\n"
        "private_answer_key: |\n"
        "  Keyword search matches exact terms. Vector search matches semantic similarity.\n"
        "  Combine them in hybrid retrieval when a query may miss exact terms but still describes intent.\n"
        "rubric:\n"
        "  - Distinguishes term matching from semantic similarity\n"
        "  - Gives a concrete hybrid-retrieval scenario\n"
        "common_traps:\n"
        "  - Calling keyword search dumb instead of explaining term matching\n"
        "  - Forgetting to mention a concrete scenario\n"
        "transfer_probe: When would you choose keyword-only, vector-only, and hybrid retrieval?\n"
        "last_used: 2026-06-24\n"
        "cooldown_days: 7\n",
        encoding="utf-8",
    )


def plan_and_record_activity(target: Path) -> None:
    print("StudyState is not only a question generator. It can assign activities and review evidence.")
    print("Planning the next learning activity based on current state...")
    result = run(
        [sys.executable, "scripts/plan_learning_activity.py", "--task", "start_session"],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/plan_learning_activity.py"])
    # Show the recommendation.
    for line in result.stdout.splitlines()[:12]:
        print(f"  {line}")

    activity_state = load_yaml(target / "state" / "ACTIVITY_STATE.yaml")
    active = activity_state.get("active_activity") or {}
    activity_id = active.get("id", "act_demo_unknown")

    print("The learner completed the activity outside the chat and submitted the result.")
    result = run(
        [
            sys.executable,
            "scripts/record_activity_result.py",
            "--activity-id",
            activity_id,
            "--result",
            "partial",
            "--evidence-id",
            "ev_demo_activity_001",
            "--mistake-tags",
            "correct-concept-weak-implementation",
        ],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/record_activity_result.py"])
    print("StudyState reviewed the submitted evidence, updated skill state, scheduled review, and recorded the next action.")


def record_evidence(target: Path) -> None:
    evidence_path = target / "state" / "EVIDENCE_LOG.md"
    evidence_text = evidence_path.read_text(encoding="utf-8")
    entry = (
        "\n- **Evidence ID:** ev_demo_001\n"
        "- **Date:** 2026-06-24\n"
        "- **Target ID:** demo-ai-search-exam\n"
        "- **Skill ID:** demo-search-basics\n"
        "- **Question ID:** Q-DEMO-001\n"
        "- **Question summary:** Explain keyword vs vector search and when to combine them.\n"
        "- **Learner answer summary:** Correctly distinguished keyword and vector search but omitted a concrete scenario.\n"
        "- **Verdict:** partial\n"
        "- **Mistake type:** correct-concept-weak-implementation\n"
        "- **Explanation:** Concept was right; answer lacked target-specific implementation detail.\n"
        "- **Confidence:** medium\n"
    )
    evidence_path.write_text(evidence_text + entry, encoding="utf-8")


def schedule_review(target: Path) -> str:
    result = run(
        [
            sys.executable,
            "scripts/schedule_review.py",
            "--skill-id",
            "demo-search-basics",
            "--evidence-id",
            "ev_demo_001",
            "--target-id",
            "demo-ai-search-exam",
            "--grade",
            "partial",
            "--confidence",
            "medium",
            "--now",
            "2026-06-24T10:00:00+00:00",
            "--prompt",
            "Describe a concrete hybrid-retrieval scenario and explain why it beats either search alone.",
            "--source",
            "partial_answer",
        ],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/schedule_review.py"])
    # Extract review id from stdout, e.g. "Scheduled review rev_demo-search-basics_20260624_100000"
    review_id = ""
    for line in result.stdout.splitlines():
        if line.startswith("Scheduled review "):
            review_id = line.split("Scheduled review ", 1)[1].strip()
            break
    return review_id


def select_next_action(target: Path, now: str) -> str:
    result = run(
        [sys.executable, "scripts/select_next_study_action.py", "--now", now],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/select_next_study_action.py"])
    return result.stdout


def print_source_freshness_check() -> None:
    print("StudyState checks source freshness before generating product-current questions.")
    print("The demo uses a demo official source marked fresh.")
    print("The agent does not search the web because the cached source is fresh enough.")
    print("If the source were stale, StudyState would ask to refresh or choose a stable review instead.")


def check_source_freshness(target: Path, now: str) -> None:
    print("Running source freshness check...")
    result = run(
        [
            sys.executable,
            "scripts/check_source_freshness.py",
            "--target-id",
            "demo-ai-search-exam",
            "--now",
            now,
        ],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/check_source_freshness.py"])


def print_learner_adaptation() -> None:
    print("StudyState suggestion:")
    print("You missed a scenario tradeoff. Next time, use a short comparison drill.")
    print("Learner control:")
    print("You can accept, modify, or override this.")


def build_and_show_context_pack(target: Path) -> None:
    print("Building StudyState context pack instead of loading every file...")
    result = run(
        [sys.executable, "scripts/build_context_pack.py", "--task", "start_session"],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/build_context_pack.py"])
    # Show the first few lines that prove intelligent loading.
    for line in result.stdout.splitlines()[:12]:
        print(f"  {line}")


def record_override(target: Path, review_id: str) -> None:
    review_state_path = target / "reviews" / "REVIEW_STATE.yaml"
    review_state = load_yaml(review_state_path)
    for item in review_state.get("review_items", []):
        if item.get("id") == review_id:
            item["override_count"] = 1
    save_yaml(review_state_path, review_state)

    overrides_path = target / "reviews" / "REVIEW_OVERRIDES.md"
    overrides_text = overrides_path.read_text(encoding="utf-8")
    entry = (
        "\n- **Timestamp:** 2026-06-25T12:05:00+00:00\n"
        f"- **Learner:** Demo Learner\n"
        f"- **Skipped review IDs:** {review_id}\n"
        "- **Reason:** learner wanted to see a new topic in the demo\n"
        "- **Chosen action:** continue with Q-DEMO-002 on hybrid retrieval\n"
        "- **Agent recommendation:** review demo-search-basics first\n"
        "- **Next review recommendation:** revisit the skipped review within 24 hours\n"
    )
    overrides_text = overrides_text.replace(
        "## Overrides\n\nNone yet.",
        "## Overrides" + entry,
    )
    overrides_path.write_text(overrides_text, encoding="utf-8")


def update_session_and_next_action(target: Path, review_id: str) -> None:
    session_path = target / "sessions" / "SESSION_LOG.md"
    session_text = session_path.read_text(encoding="utf-8")
    session_entry = (
        "\n- **Date:** 2026-06-24\n"
        "- **Target ID:** demo-ai-search-exam\n"
        "- **Focus:** keyword vs vector search\n"
        "- **Questions asked:** Q-DEMO-001\n"
        "- **Result summary:** Learner gave a partial answer; review scheduled.\n"
        "- **Evidence added:** ev_demo_001\n"
        f"- **Reviews added:** {review_id}\n"
        "- **State changes:** demo-search-basics marked weak, readiness 35, review scheduled.\n"
        "- **Next action proposed:** Review demo-search-basics or continue with Q-DEMO-002.\n"
    )
    session_text = session_text.replace(
        "## Sessions\n\nNone yet.",
        "## Sessions" + session_entry,
    )
    session_path.write_text(session_text, encoding="utf-8")

    next_path = target / "NEXT_ACTIONS.md"
    next_path.write_text(
        "# NEXT_ACTIONS — Active Queue\n\n"
        "> **Agent-maintained.** This is the single canonical next-action file for the repo.\n\n"
        "## Current next action\n\n"
        "Review demo-search-basics (Q-DEMO-001 follow-up) before moving to Q-DEMO-002.\n\n"
        "## Pending actions\n\n"
        "- Continue building varied evidence for demo-search-basics.\n"
        "- Introduce Q-DEMO-002 on hybrid retrieval design.\n\n"
        "## Recently completed\n\n"
        "- Q-DEMO-001 answered and graded partial.\n",
        encoding="utf-8",
    )

    status_path = target / "state" / "STUDY_STATUS.md"
    status_path.write_text(
        "# Study Status\n\n"
        "**Learner:** Demo Learner\n\n"
        "**Active target:** AI Search Fundamentals Demo\n\n"
        "**Current focus:** keyword vs vector search\n\n"
        "**Readiness snapshot:**\n\n"
        "- demo-search-basics: weak (35)\n"
        "- demo-hybrid-retrieval: pending (0)\n"
        "- demo-eval-relevance: pending (0)\n\n"
        "**Next action:** Review demo-search-basics before new material.\n",
        encoding="utf-8",
    )


def compact_state(target: Path) -> None:
    result = run([sys.executable, "scripts/compact_state.py"], target, check=False)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/compact_state.py"])


def validate(target: Path, now: str) -> None:
    result = run(
        [sys.executable, "scripts/check_studydd.py", "--now", now],
        target,
        check=False,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, ["scripts/check_studydd.py"])


def print_transcript(review_id: str, before_due: str, when_due: str) -> None:
    print("StudyState demo replay")
    print("===================")
    print("")
    print("1. Created learner instance from template.")
    print("2. Initialized learner profile: Demo Learner.")
    print("3. Initialized target: AI Search Fundamentals Demo.")
    print("4. Active study skill: it_certification.")
    print("5. Built a context pack instead of loading every file.")
    print("6. StudyState uses the fast path during ordinary tutoring turns.")
    print("7. Only relevant state is loaded.")
    print("8. Only touched files are updated.")
    print("9. Full validation runs at session boundary.")
    print("10. Agent asked one question: Q-DEMO-001.")
    print("11. Learner answered: distinguished keyword and vector search, no scenario.")
    print("12. Agent graded honestly: partial.")
    print("13. Evidence recorded: ev_demo_001.")
    print("14. StudyState planned a non-question activity based on the weak skill.")
    print("15. Learner completed the activity outside the chat and submitted evidence.")
    print("16. StudyState reviewed the submitted evidence and updated state.")
    print(f"17. Review scheduled: {review_id} due in 1 day.")
    print("18. Selector before due: new material is allowed.")
    print("   ", before_due.splitlines()[0])
    print("19. Selector when review is due: review first.")
    print("    ", when_due.splitlines()[0])
    print("20. Learner override recorded with reason.")
    print("21. Validation passed.")
    print("")
    print("The repo now contains evidence, a spaced-repetition review, an override log,")
    print("a compact context pack, and a clear next action. Raw logs remain available")
    print("for audit, but the agent loads only the relevant context by default.")
    print("Run `python3 scripts/check_studydd.py` in the instance to verify repo health.")


def copy_fixture(source: Path, destination: Path) -> None:
    """Copy the demo instance to EXAMPLES/, excluding Git history."""
    import shutil

    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"),
    )
    copied_git = destination / ".git"
    if copied_git.exists():
        shutil.rmtree(copied_git)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the StudyState public demo replay")
    parser.add_argument(
        "--dump-to",
        "--dump-fixture",
        dest="dump_fixture",
        default=None,
        help="Copy the final demo instance to this path (e.g. EXAMPLES/demo_ai_search_exam)",
    )
    args = parser.parse_args()

    try:
        import yaml  # noqa: F401
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        return 1

    with tempfile.TemporaryDirectory(prefix="studydd-demo-") as tmp:
        target = Path(tmp) / "StudyState_Demo"
        remote = "https://github.com/example/StudyState_Demo.git"

        create_instance(target, remote)
        switch_to_learner_instance(target)
        initialize_learner_profile(target)
        initialize_sources(target)
        initialize_target(target)
        print_source_freshness_check()
        check_source_freshness(target, "2026-06-24T12:00:00+00:00")
        build_and_show_context_pack(target)
        record_evidence(target)
        print_learner_adaptation()
        plan_and_record_activity(target)
        review_id = schedule_review(target)

        before_due = select_next_action(target, "2026-06-24T12:00:00+00:00")
        when_due = select_next_action(target, "2026-06-25T12:00:00+00:00")

        record_override(target, review_id)
        update_session_and_next_action(target, review_id)
        compact_state(target)
        validate(target, "2026-06-24T12:00:00+00:00")
        print_transcript(review_id, before_due, when_due)

        if args.dump_fixture:
            fixture_path = Path(args.dump_fixture).resolve()
            copy_fixture(target, fixture_path)
            print(f"\nDemo fixture copied to: {fixture_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
