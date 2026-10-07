#!/usr/bin/env python3
"""Test StudyState learning activity and evidence intake orchestration.

Validates new files, helper scripts, demo output, and context-pack integration.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PROTOCOLS = [
    "protocols/LEARNING_ACTIVITY_POLICY.md",
    "protocols/EVIDENCE_INTAKE_POLICY.md",
    "protocols/EXTERNAL_RESOURCE_POLICY.md",
    "protocols/VOICE_NOTE_REVIEW_POLICY.md",
    "protocols/INTERVIEW_PREP_POLICY.md",
    "protocols/PRESENTATION_PREP_POLICY.md",
]
REQUIRED_ACTIVITY_TYPES = [
    "retrieval_question",
    "spaced_review",
    "paper_exercise",
    "external_platform_exercise",
    "video_or_reading_task",
    "practical_lab",
    "explain_back",
    "diagram_or_whiteboard",
    "interview_prep",
    "presentation_prep",
    "voice_note_review",
    "writing_or_essay_review",
    "upload_and_review",
    "recent_info_check",
]
REQUIRED_TEMPLATE_IDS = [
    "paper_drill_basic",
    "official_doc_reading",
    "lab_screenshot_review",
    "explain_back",
    "interview_star_answer",
    "presentation_rehearsal_transcript",
    "voice_note_review",
]


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(result.stdout)
        print(result.stderr)
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_temp_instance(tmp: str, name: str, target_id: str, target_yaml: str) -> Path:
    target = Path(tmp) / f"StudyState_{name}"
    remote = f"https://github.com/example/StudyState_{name}.git"
    run([sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote])

    mode_path = target / "state" / "STUDYDD_MODE.yaml"
    mode_data = load_yaml(mode_path)
    mode_data["mode"] = "learner_instance"
    mode_data["personalized"] = True
    save_yaml(mode_path, mode_data)

    study_state = load_yaml(target / "state" / "STUDY_STATE.yaml")
    study_state["learner"]["name"] = f"{name} Test Learner"
    study_state["active_target_id"] = target_id
    save_yaml(target / "state" / "STUDY_STATE.yaml", study_state)

    (target / "targets" / target_id).mkdir(parents=True, exist_ok=True)
    (target / "targets" / target_id / "TARGET.yaml").write_text(target_yaml, encoding="utf-8")

    return target


def test_required_files_exist() -> None:
    required = [
        "state/ACTIVITY_STATE.yaml",
        "activities/ACTIVITY_LOG.md",
        "activities/ACTIVITY_TEMPLATES.yaml",
        "scripts/plan_learning_activity.py",
        "scripts/record_activity_result.py",
        "scripts/analyze_voice_note.py",
        "scripts/analyze_presentation_rehearsal.py",
    ] + REQUIRED_PROTOCOLS
    missing = [p for p in required if not (ROOT / p).is_file()]
    assert not missing, f"Missing required files: {missing}"


def test_activity_state_is_generic_in_template_mode() -> None:
    data = load_yaml(ROOT / "state" / "ACTIVITY_STATE.yaml")
    active = data.get("active_activity") or {}
    assert active.get("id") == "", "Template mode active_activity.id must be empty"
    assert active.get("type") == "", "Template mode active_activity.type must be empty"
    assert not data.get("recent_activities"), "Template mode recent_activities must be empty"
    prefs = data.get("activity_preferences") or {}
    assert not prefs.get("learner_likes"), "Template mode learner_likes must be empty"


def test_activity_templates_parse() -> None:
    data = load_yaml(ROOT / "activities" / "ACTIVITY_TEMPLATES.yaml")
    activity_types = data.get("activity_types") or {}
    missing_types = [t for t in REQUIRED_ACTIVITY_TYPES if t not in activity_types]
    assert not missing_types, f"Missing activity types: {missing_types}"

    templates = data.get("templates") or []
    template_ids = {t.get("id") for t in templates}
    missing_ids = [t for t in REQUIRED_TEMPLATE_IDS if t not in template_ids]
    assert not missing_ids, f"Missing template IDs: {missing_ids}"

    for template in templates:
        assert template.get("activity_type") in activity_types, (
            f"Template {template.get('id')} has unknown activity_type {template.get('activity_type')}"
        )
        assert template.get("expected_evidence"), (
            f"Template {template.get('id')} missing expected_evidence"
        )


def test_recent_info_check_activity_type_exists() -> None:
    data = load_yaml(ROOT / "activities" / "ACTIVITY_TEMPLATES.yaml")
    activity_types = data.get("activity_types") or {}
    assert "recent_info_check" in activity_types, "recent_info_check activity type must exist"
    templates = data.get("templates") or []
    assert any(
        t.get("id") == "source_freshness_check" and t.get("activity_type") == "recent_info_check"
        for t in templates
    ), "source_freshness_check template must exist"


def test_plan_recommends_recent_info_check_for_volatile_target() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-volatile-test-") as tmp:
        target_yaml = "---\nid: volatile-target\ntype: certification\ntitle: Volatile Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "VolatileTest", "volatile-target", target_yaml)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "recent_info_check" in result.stdout, "Volatile target should route to recent_info_check"
        assert "source freshness" in result.stdout, "Reason should reference source freshness"
        assert "Rule:" in result.stdout, "Reason should start with Rule:"
        assert "Source freshness:" in result.stdout, "Output should surface source freshness status"
        assert "source_freshness_unavailable_recent_activity_fallback" in result.stdout, "Empty source state should use the fallback rule"


def test_plan_recommends_recent_info_check_for_stale_source() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-stale-source-test-") as tmp:
        target_yaml = "---\nid: stale-source-target\ntype: certification\ntitle: Stale Source Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "StaleSourceTest", "stale-source-target", target_yaml)

        source_state = {
            "metadata": {"template_version": "0.9.0", "last_updated": "2026-06-27"},
            "sources": [
                {
                    "id": "stale-docs",
                    "authority": "official",
                    "target_ids": ["stale-source-target"],
                    "last_checked_at": "2026-01-01T00:00:00+00:00",
                    "volatility": "volatile",
                }
            ],
        }
        save_yaml(target / "sources" / "SOURCE_STATE.yaml", source_state)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "recent_info_check" in result.stdout, "Stale source should route to recent_info_check"
        assert "Source freshness: stale" in result.stdout, "Output should report stale freshness"
        assert "source_freshness_stale" in result.stdout, "Rule ID should be source_freshness_stale"


def test_plan_recommends_lab_for_practical_skill() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lab-test-") as tmp:
        target_yaml = "---\nid: lab-target\ntype: skill\ntitle: Lab Target\nvolatility: stable\nstudy_skill: practical_lab\n"
        target = create_temp_instance(tmp, "LabTest", "lab-target", target_yaml)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "practical_lab" in result.stdout, "practical_lab study skill should route to practical_lab"
        assert "hands-on" in result.stdout, "Reason should mention hands-on study skill"


def test_plan_recommends_diagram_for_conceptual_skill() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-diagram-test-") as tmp:
        target_yaml = "---\nid: diagram-target\ntype: skill\ntitle: Diagram Target\nvolatility: stable\nstudy_skill: philosophy\n"
        target = create_temp_instance(tmp, "DiagramTest", "diagram-target", target_yaml)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "diagram_or_whiteboard" in result.stdout, "philosophy study skill should route to diagram_or_whiteboard"
        assert "visual explanation" in result.stdout, "Reason should mention visual explanation"


def test_plan_recommends_exam_question_for_certification_target() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-exam-test-") as tmp:
        target_yaml = "---\nid: exam-target\ntype: certification\ntitle: Exam Target\nvolatility: stable\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "ExamTest", "exam-target", target_yaml)

        # Add a practiced skill so the exam-style branch fires.
        skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
        skill_map["skills"] = [
            {
                "id": "exam-skill",
                "label": "Exam skill",
                "status": "practiced",
                "readiness": 55,
                "confidence": "medium",
                "evidence": [],
            }
        ]
        save_yaml(target / "state" / "SKILL_MAP.yaml", skill_map)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "retrieval_question" in result.stdout, "Certification target should route to exam-style retrieval question"
        assert "certification target" in result.stdout, "Reason should mention certification target"


def test_plan_includes_source_freshness_for_fresh_volatile_target() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-fresh-source-test-") as tmp:
        target_yaml = "---\nid: fresh-source-target\ntype: certification\ntitle: Fresh Source Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "FreshSourceTest", "fresh-source-target", target_yaml)

        source_state = {
            "metadata": {"template_version": "0.9.0", "last_updated": "2026-06-27"},
            "sources": [
                {
                    "id": "fresh-docs",
                    "authority": "official",
                    "target_ids": ["fresh-source-target"],
                    "last_checked_at": "2026-06-27T10:00:00+00:00",
                    "volatility": "volatile",
                }
            ],
        }
        save_yaml(target / "sources" / "SOURCE_STATE.yaml", source_state)

        result = run(
            [
                sys.executable,
                "scripts/plan_learning_activity.py",
                "--now",
                "2026-06-27T11:00:00+00:00",
            ],
            cwd=target,
        )
        assert "retrieval_question" in result.stdout, "Fresh volatile source should allow retrieval question"
        assert "Source freshness: fresh" in result.stdout, "Output should report fresh freshness"
        assert "source_freshness_satisfied" in result.stdout, "Rule ID should be source_freshness_satisfied"


def test_plan_learning_activity_demo() -> None:
    result = run([sys.executable, "scripts/plan_learning_activity.py", "--demo"])
    stdout = result.stdout
    assert "StudyState recommendation:" in stdout, "Demo must contain a recommendation"
    assert "Reason:" in stdout, "Demo must contain a reason"
    assert "Task:" in stdout, "Demo must contain a task"
    assert "Expected evidence:" in stdout, "Demo must contain expected evidence"
    assert "You can accept, modify, or override this." in stdout, "Demo must contain learner control phrase"


def test_voice_note_analyzer() -> None:
    transcript = "Um, so I think the answer is vector search. You know, it finds similar meanings."
    result = run([sys.executable, "scripts/analyze_voice_note.py", "--text", transcript])
    stdout = result.stdout
    assert "Word count:" in stdout
    assert "Filler word counts:" in stdout
    assert "Structure markers found:" in stdout
    assert "Likely strengths:" in stdout
    assert "Likely improvement areas:" in stdout
    assert "Suggested next practice activity:" in stdout


def test_presentation_analyzer() -> None:
    transcript = "Today I want to explain spaced repetition. First, it beats cramming. Next, it strengthens memory. In summary, spaced repetition works."
    result = run(
        [sys.executable, "scripts/analyze_presentation_rehearsal.py", "--text", transcript, "--target-minutes", "3"]
    )
    stdout = result.stdout
    assert "Word count:" in stdout
    assert "Estimated speaking time:" in stdout
    assert "Opening detected:" in stdout
    assert "Closing detected:" in stdout
    assert "Structure markers found:" in stdout
    assert "Jargon warnings (heuristic):" in stdout
    assert "Unsupported claim warnings (heuristic):" in stdout
    assert "Suggested improvement:" in stdout


def test_context_pack_includes_active_activity() -> None:
    run([sys.executable, "scripts/build_context_pack.py", "--task", "start_session"])
    pack_path = ROOT / ".studydd" / "context_pack.md"
    assert pack_path.is_file(), "Context pack was not built"
    text = pack_path.read_text(encoding="utf-8")
    assert "## Active activity" in text or "active_activity" in text, "Context pack should surface active activity"
    # Raw activity log is append-only audit; should not be loaded as file content by default.
    assert "### activities/ACTIVITY_LOG.md" not in text, "Context pack should not include full activity log contents"


def test_demo_replay_mentions_non_question_activity() -> None:
    result = run([sys.executable, "scripts/run_demo_replay.py"])
    stdout = result.stdout
    assert "not only a question generator" in stdout.lower(), "Demo must mention non-question activity"
    assert "outside the chat" in stdout.lower(), "Demo must mention evidence submitted outside chat"


def test_record_activity_result_on_temp_instance() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-activity-test-") as tmp:
        target = Path(tmp) / "StudyState_ActivityTest"
        remote = "https://github.com/example/StudyState_ActivityTest.git"
        run([sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote])

        # Switch to learner instance.
        mode_path = target / "state" / "STUDYDD_MODE.yaml"
        mode_data = load_yaml(mode_path)
        mode_data["mode"] = "learner_instance"
        mode_data["personalized"] = True
        mode_data["public_safe"] = "false_or_review_required"
        save_yaml(mode_path, mode_data)

        # Set a learner and active target.
        study_state = load_yaml(target / "state" / "STUDY_STATE.yaml")
        study_state["learner"]["name"] = "Activity Test Learner"
        study_state["active_target_id"] = "test-target"
        save_yaml(target / "state" / "STUDY_STATE.yaml", study_state)

        (target / "targets" / "test-target").mkdir(parents=True, exist_ok=True)
        (target / "targets" / "test-target" / "TARGET.yaml").write_text(
            "---\nid: test-target\ntype: skill\ntitle: Test target\n", encoding="utf-8"
        )

        # Set active activity.
        activity_state = load_yaml(target / "state" / "ACTIVITY_STATE.yaml")
        activity_state["active_activity"] = {
            "id": "act_test_001",
            "type": "paper_exercise",
            "target_id": "test-target",
            "skill_id": "test-skill",
            "assigned_at": "2026-06-24T12:00:00+00:00",
            "due_at": "",
            "status": "proposed",
            "reason": "Test activity.",
            "expected_evidence": ["photo", "typed_answers"],
            "learner_override_allowed": True,
        }
        save_yaml(target / "state" / "ACTIVITY_STATE.yaml", activity_state)

        # Add a skill.
        skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
        skill_map["skills"] = [
            {
                "id": "test-skill",
                "label": "Test skill",
                "status": "pending",
                "readiness": 0,
                "confidence": "low",
                "evidence": [],
            }
        ]
        save_yaml(target / "state" / "SKILL_MAP.yaml", skill_map)

        # Record a partial result.
        run(
            [
                sys.executable,
                "scripts/record_activity_result.py",
                "--activity-id",
                "act_test_001",
                "--result",
                "partial",
                "--evidence-id",
                "ev_test_001",
                "--mistake-tags",
                "vague-answer",
            ],
            cwd=target,
        )

        # Verify updates.
        updated_activity_state = load_yaml(target / "state" / "ACTIVITY_STATE.yaml")
        active = updated_activity_state["active_activity"]
        assert active["status"] == "completed", "Active activity should be marked completed"
        assert active["submitted_evidence_id"] == "ev_test_001"

        activity_log = (target / "activities" / "ACTIVITY_LOG.md").read_text(encoding="utf-8")
        assert "act_test_001" in activity_log, "Activity log should contain the activity ID"
        assert "partial" in activity_log, "Activity log should contain the verdict"

        evidence_log = (target / "state" / "EVIDENCE_LOG.md").read_text(encoding="utf-8")
        assert "ev_test_001" in evidence_log, "Evidence log should contain the evidence ID"
        assert "act_test_001" in evidence_log, "Evidence log should reference the activity ID"

        updated_skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
        skill = updated_skill_map["skills"][0]
        assert skill["status"] in ("weak", "practiced"), "Skill status should be updated conservatively"

        review_state = load_yaml(target / "reviews" / "REVIEW_STATE.yaml")
        assert review_state.get("review_items"), "A review should be scheduled for a partial result"

        # Validate the temp instance.
        run([sys.executable, "scripts/check_studydd.py"], cwd=target)


def test_record_recent_info_check_updates_source_state() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-recent-info-test-") as tmp:
        target_yaml = "---\nid: recent-info-target\ntype: certification\ntitle: Recent Info Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "RecentInfoTest", "recent-info-target", target_yaml)

        # Set active recent_info_check activity.
        activity_state = load_yaml(target / "state" / "ACTIVITY_STATE.yaml")
        activity_state["active_activity"] = {
            "id": "act_recent_info_001",
            "type": "recent_info_check",
            "target_id": "recent-info-target",
            "skill_id": "recent-info-skill",
            "assigned_at": "2026-06-27T12:00:00+00:00",
            "due_at": "",
            "status": "proposed",
            "reason": "Source freshness check for volatile cert.",
            "expected_evidence": ["source summary"],
            "learner_override_allowed": True,
        }
        save_yaml(target / "state" / "ACTIVITY_STATE.yaml", activity_state)

        # Add the referenced skill so the validator passes.
        skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
        skill_map["skills"] = [
            {
                "id": "recent-info-skill",
                "label": "Recent info skill",
                "status": "pending",
                "readiness": 0,
                "confidence": "low",
                "evidence": [],
            }
        ]
        save_yaml(target / "state" / "SKILL_MAP.yaml", skill_map)

        # Relative on purpose: freshness is evaluated on the real clock below.
        checked_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        run(
            [
                sys.executable,
                "scripts/record_activity_result.py",
                "--activity-id",
                "act_recent_info_001",
                "--result",
                "partial",
                "--evidence-id",
                "ev_recent_info_001",
                "--source-id",
                "recent-info-source",
                "--source-outcome",
                "fresh",
                "--source-summary",
                "Official docs verified; no exam changes.",
                "--source-authority",
                "official",
                "--source-volatility",
                "volatile",
                "--source-checked-at",
                checked_at,
            ],
            cwd=target,
        )

        source_state = load_yaml(target / "sources" / "SOURCE_STATE.yaml")
        sources = source_state.get("sources", [])
        assert len(sources) == 1, f"Expected one source, got {len(sources)}"
        source = sources[0]
        assert source["id"] == "recent-info-source"
        assert source["last_check"]["outcome"] == "fresh"
        assert source["last_check"]["checked_at"] == checked_at
        assert source["last_check"]["summary"] == "Official docs verified; no exam changes."
        assert source["last_check"]["activity_id"] == "act_recent_info_001"
        assert source["last_check"]["evidence_id"] == "ev_recent_info_001"

        # Next plan should see fresh source and not recommend recent_info_check.
        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target)
        assert "recent_info_check" not in result.stdout, "Fresh source should suppress recent_info_check"
        assert "Source freshness: fresh" in result.stdout
        assert "source_freshness_satisfied" in result.stdout

        run([sys.executable, "scripts/check_studydd.py"], cwd=target)


def test_full_validator_passes() -> None:
    run([sys.executable, "scripts/check_studydd.py"])


def main() -> int:
    tests = [
        test_required_files_exist,
        test_activity_state_is_generic_in_template_mode,
        test_activity_templates_parse,
        test_recent_info_check_activity_type_exists,
        test_plan_recommends_recent_info_check_for_volatile_target,
        test_plan_recommends_recent_info_check_for_stale_source,
        test_plan_recommends_lab_for_practical_skill,
        test_plan_recommends_diagram_for_conceptual_skill,
        test_plan_recommends_exam_question_for_certification_target,
        test_plan_includes_source_freshness_for_fresh_volatile_target,
        test_plan_learning_activity_demo,
        test_voice_note_analyzer,
        test_presentation_analyzer,
        test_context_pack_includes_active_activity,
        test_demo_replay_mentions_non_question_activity,
        test_record_activity_result_on_temp_instance,
        test_record_recent_info_check_updates_source_state,
        test_full_validator_passes,
    ]

    failed = []
    for test in tests:
        try:
            print(f"Running {test.__name__}...")
            test()
            print("  passed")
        except Exception as exc:
            print(f"  failed: {exc}")
            failed.append((test.__name__, exc))

    if failed:
        print("\nFailed tests:")
        for name, exc in failed:
            print(f"  - {name}: {exc}")
        return 1

    print("\nAll learning activity tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
