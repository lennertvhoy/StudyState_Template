#!/usr/bin/env python3
"""StudyState repo health and educational-drift validator.

Supports the agent workflow by checking that required files exist,
YAML parses, required keys are present, and common educational drift
is caught before it harms the learner.

If PyYAML is not installed, YAML parsing is skipped and a note is printed.
Install PyYAML for full validation:
    pip install pyyaml
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from check_source_freshness import classify_source

ROOT = Path(__file__).resolve().parent.parent

# Reference fixtures under EXAMPLES/ are historical snapshots. Their source
# timestamps are deterministic test metadata, not live freshness claims, so the
# wall-clock staleness gate does not apply to them (see
# protocols/SOURCE_FRESHNESS_POLICY.md and the demo fixture's SOURCE_STATE).
REFERENCE_SNAPSHOT_ROOT = "EXAMPLES"

REQUIRED_ROOT_FILES = [
    "README.md",
    "AGENTS.md",
    "NEXT_ACTIONS.md",
    "LICENSE.md",
    "CONTRIBUTING.md",
    "requirements.txt",
]

REQUIRED_DOC_FILES = [
    "docs/agent-native-quickstart.md",
    "docs/how-to-use-with-codex.md",
    "docs/how-to-use-with-kimi-code.md",
    "docs/how-to-use-with-claude-code.md",
    "docs/how-to-use-with-cursor.md",
    "docs/studydd-principles.md",
    "docs/inspect-and-override-state.md",
    "docs/question-bank-schema.md",
    "docs/demo-walkthrough.md",
    "docs/linkedin-product-blurb.md",
    "docs/setup.md",
    "docs/README.md",
    "docs/architecture.md",
    "docs/worked-state-update.md",
    "docs/UPGRADING.md",
]

REQUIRED_STATE_FILES = [
    "state/STUDYDD_MODE.yaml",
    "state/STUDYDD_TEMPLATE_VERSION.yaml",
    "state/STUDY_STATUS.md",
    "state/STUDY_STATE.yaml",
    "state/STUDY_BACKLOG.md",
    "state/EVIDENCE_LOG.md",
    "state/SKILL_MAP.yaml",
    "state/CURRENT_CONTEXT.md",
    "state/EVIDENCE_INDEX.yaml",
    "state/STATE_MANIFEST.yaml",
    "state/PERFORMANCE_BUDGET.yaml",
    "state/LEARNER_PROFILE.yaml",
    "state/ACTIVITY_STATE.yaml",
]

REQUIRED_TARGET_FILES = [
    "targets/README.md",
]

REQUIRED_REVIEW_FILES = [
    "reviews/README.md",
    "reviews/REVIEW_QUEUE.md",
    "reviews/REVIEW_STATE.yaml",
    "reviews/REVIEW_OVERRIDES.md",
]

REQUIRED_SESSION_FILES = [
    "sessions/README.md",
    "sessions/SESSION_LOG.md",
    "sessions/SESSION_SUMMARIES.md",
]

REQUIRED_SOURCE_FILES = [
    "sources/README.md",
    "sources/SOURCE_INDEX.md",
    "sources/SOURCE_STATE.yaml",
]

REQUIRED_ACTIVITY_FILES = [
    "activities/ACTIVITY_LOG.md",
    "activities/ACTIVITY_TEMPLATES.yaml",
]

REQUIRED_PROTOCOL_FILES = [
    "protocols/INSTANTIATE_TEMPLATE.md",
    "protocols/UPGRADE_INSTANCE_FROM_TEMPLATE.md",
    "protocols/GIT_PROVENANCE.md",
    "protocols/PRIVACY_REVIEW.md",
    "protocols/WRONG_REPO_RECOVERY.md",
    "protocols/SPACED_REPETITION_POLICY.md",
    "protocols/TUTOR_PROTOCOL.md",
    "protocols/SESSION_TEMPLATE.md",
    "protocols/START_SESSION.md",
    "protocols/SELECT_NEXT_ACTION.md",
    "protocols/ASK_QUESTION.md",
    "protocols/GRADE_ANSWER.md",
    "protocols/UPDATE_STATE.md",
    "protocols/SCHEDULE_REVIEW.md",
    "protocols/CLOSE_SESSION.md",
    "protocols/SOURCE_TRUST.md",
    "protocols/READINESS_POLICY.md",
    "protocols/QUESTION_QUALITY.md",
    "protocols/MISTAKE_TAXONOMY.md",
    "protocols/LOW_ENERGY_MODE.md",
    "protocols/STATE_LOADING_POLICY.md",
    "protocols/PERFORMANCE_POLICY.md",
    "protocols/STATE_WRITE_POLICY.md",
    "protocols/SOURCE_FRESHNESS_POLICY.md",
    "protocols/SOURCE_REFRESH_POLICY.md",
    "protocols/QUESTION_QUALITY_GOVERNOR.md",
    "protocols/LEARNER_ADAPTATION_POLICY.md",
    "protocols/LEARNER_FEEDBACK_POLICY.md",
    "protocols/LEARNING_ACTIVITY_POLICY.md",
    "protocols/EVIDENCE_INTAKE_POLICY.md",
    "protocols/EXTERNAL_RESOURCE_POLICY.md",
    "protocols/VOICE_NOTE_REVIEW_POLICY.md",
    "protocols/INTERVIEW_PREP_POLICY.md",
    "protocols/PRESENTATION_PREP_POLICY.md",
    "protocols/RECORD_SOURCE_CHECK.md",
    "protocols/README.md",
    "protocols/TEMPLATE_INSTANCE_BOUNDARY.md",
]

REQUIRED_PROMPT_FILES = [
    "PROMPTS/create_new_instance_from_template.md",
    "PROMPTS/coding_agent_start_prompt.md",
    "PROMPTS/ai_tutor_prompt.md",
    "PROMPTS/study_session_prompt.md",
    "PROMPTS/exam_drill_prompt.md",
    "PROMPTS/reflection_prompt.md",
    "PROMPTS/update_state_prompt.md",
    "PROMPTS/interview_prep_prompt.md",
    "PROMPTS/grade_and_update_state_prompt.md",
    "PROMPTS/repair_state_prompt.md",
    "PROMPTS/add_target_prompt.md",
    "PROMPTS/refresh_source_map_prompt.md",
    "PROMPTS/checkpoint_session_prompt.md",
    "PROMPTS/close_session_prompt.md",
]

REQUIRED_SCRIPT_FILES = [
    "scripts/check_studydd.py",
    "scripts/agent_preflight.py",
    "scripts/agent_consistency_check.py",
    "scripts/agent_evidence_check.py",
    "scripts/create_instance.py",
    "scripts/agent_privacy_check.py",
    "scripts/schedule_review.py",
    "scripts/select_next_study_action.py",
    "scripts/run_demo_replay.py",
    "scripts/compact_state.py",
    "scripts/build_context_pack.py",
    "scripts/validate_touched_state.py",
    "scripts/plan_state_update.py",
    "scripts/check_source_freshness.py",
    "scripts/test_source_freshness.py",
    "scripts/lint_questions.py",
    "scripts/test_question_quality.py",
    "scripts/suggest_study_adjustment.py",
    "scripts/test_learner_adaptation.py",
    "scripts/plan_learning_activity.py",
    "scripts/record_activity_result.py",
    "scripts/record_source_check.py",
    "scripts/review_state.py",
    "scripts/state_io.py",
    "scripts/template_ownership.py",
    "scripts/run_tests.py",
    "scripts/analyze_voice_note.py",
    "scripts/analyze_presentation_rehearsal.py",
    "scripts/check_environment.py",
    "scripts/setup_studydd.py",
]

REQUIRED_AI103_EXAMPLE_FILES = [
    "EXAMPLES/ai-103-example/NEXT_ACTIONS.md",
    "EXAMPLES/ai-103-example/state/STUDY_STATUS.md",
    "EXAMPLES/ai-103-example/state/STUDY_STATE.yaml",
    "EXAMPLES/ai-103-example/state/SKILL_MAP.yaml",
    "EXAMPLES/ai-103-example/reviews/REVIEW_QUEUE.md",
    "EXAMPLES/ai-103-example/sessions/SESSION_LOG.md",
    "EXAMPLES/ai-103-example/sources/SOURCE_INDEX.md",
    "EXAMPLES/ai-103-example/targets/ai-103/TARGET.yaml",
]

REQUIRED_MS102_EXAMPLE_FILES = [
    "EXAMPLES/ms-102-example/NEXT_ACTIONS.md",
    "EXAMPLES/ms-102-example/state/STUDY_STATUS.md",
    "EXAMPLES/ms-102-example/state/STUDY_STATE.yaml",
    "EXAMPLES/ms-102-example/state/SKILL_MAP.yaml",
    "EXAMPLES/ms-102-example/reviews/REVIEW_QUEUE.md",
    "EXAMPLES/ms-102-example/sessions/SESSION_LOG.md",
    "EXAMPLES/ms-102-example/sources/SOURCE_INDEX.md",
    "EXAMPLES/ms-102-example/targets/ms-102/TARGET.yaml",
]

REQUIRED_DEMO_EXAMPLE_FILES = [
    "EXAMPLES/demo_ai_search_exam/README.md",
    "EXAMPLES/demo_ai_search_exam/NEXT_ACTIONS.md",
    "EXAMPLES/demo_ai_search_exam/state/STUDY_STATUS.md",
    "EXAMPLES/demo_ai_search_exam/state/STUDY_STATE.yaml",
    "EXAMPLES/demo_ai_search_exam/state/SKILL_MAP.yaml",
    "EXAMPLES/demo_ai_search_exam/state/EVIDENCE_LOG.md",
    "EXAMPLES/demo_ai_search_exam/reviews/REVIEW_QUEUE.md",
    "EXAMPLES/demo_ai_search_exam/reviews/REVIEW_STATE.yaml",
    "EXAMPLES/demo_ai_search_exam/reviews/REVIEW_OVERRIDES.md",
    "EXAMPLES/demo_ai_search_exam/sessions/SESSION_LOG.md",
    "EXAMPLES/demo_ai_search_exam/sources/SOURCE_INDEX.md",
    "EXAMPLES/demo_ai_search_exam/targets/demo-ai-search-exam/TARGET.yaml",
    "EXAMPLES/demo_ai_search_exam/targets/demo-ai-search-exam/questions/Q-DEMO-001.yaml",
]

REQUIRED_GITHUB_TEMPLATES = [
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/pull_request_template.md",
]

REQUIRED_FILES = (
    REQUIRED_ROOT_FILES
    + REQUIRED_DOC_FILES
    + REQUIRED_STATE_FILES
    + REQUIRED_TARGET_FILES
    + REQUIRED_REVIEW_FILES
    + REQUIRED_SESSION_FILES
    + REQUIRED_SOURCE_FILES
    + REQUIRED_ACTIVITY_FILES
    + REQUIRED_PROTOCOL_FILES
    + REQUIRED_PROMPT_FILES
    + REQUIRED_SCRIPT_FILES
    + REQUIRED_AI103_EXAMPLE_FILES
    + REQUIRED_MS102_EXAMPLE_FILES
    + REQUIRED_DEMO_EXAMPLE_FILES
    + REQUIRED_GITHUB_TEMPLATES
)

YAML_FILES = [
    "state/STUDYDD_MODE.yaml",
    "state/STUDYDD_TEMPLATE_VERSION.yaml",
    "state/STUDY_STATE.yaml",
    "state/SKILL_MAP.yaml",
    "state/STATE_MANIFEST.yaml",
    "state/EVIDENCE_INDEX.yaml",
    "state/PERFORMANCE_BUDGET.yaml",
    "state/LEARNER_PROFILE.yaml",
    "state/ACTIVITY_STATE.yaml",
    "sources/SOURCE_STATE.yaml",
    "reviews/REVIEW_STATE.yaml",
    "activities/ACTIVITY_TEMPLATES.yaml",
    "EXAMPLES/ai-103-example/state/STUDY_STATE.yaml",
    "EXAMPLES/ai-103-example/state/SKILL_MAP.yaml",
    "EXAMPLES/ai-103-example/targets/ai-103/TARGET.yaml",
    "EXAMPLES/ms-102-example/state/STUDY_STATE.yaml",
    "EXAMPLES/ms-102-example/state/SKILL_MAP.yaml",
    "EXAMPLES/ms-102-example/targets/ms-102/TARGET.yaml",
    "EXAMPLES/demo_ai_search_exam/state/STUDY_STATE.yaml",
    "EXAMPLES/demo_ai_search_exam/state/SKILL_MAP.yaml",
    "EXAMPLES/demo_ai_search_exam/reviews/REVIEW_STATE.yaml",
    "EXAMPLES/demo_ai_search_exam/targets/demo-ai-search-exam/TARGET.yaml",
    "EXAMPLES/demo_ai_search_exam/targets/demo-ai-search-exam/questions/Q-DEMO-001.yaml",
]

REQUIRED_STUDY_STATE_KEYS = [
    "learner",
    "active_target_id",
    "targets",
    "study_target",
    "skills",
    "active_focus",
    "review",
    "sources",
    "session_history",
    "workflow",
    "rules",
    "metadata",
]

REQUIRED_SKILL_MAP_KEYS = [
    "skills",
    "metadata",
]

# Constructed from parts so the literal forbidden string does not appear in source.
FORBIDDEN_BRAND_RE = re.compile("Skill" + "Signal", re.IGNORECASE)

SOURCE_AUTHORITY_VALUES = {
    "official",
    "high_authority",
    "instructor",
    "textbook",
    "learner_notes",
    "unverified",
}

SOURCE_VOLATILITY_VALUES = {
    "stable",
    "slow_changing",
    "moderate",
    "volatile",
    "live",
}

SOURCE_OUTCOMES = {
    "fresh",
    "stale",
    "missing",
    "unverified",
    "unknown",
}

QUESTION_MODES = {
    "authoritative_current",
    "conceptual_practice",
    "stale_practice",
    "exam_sim",
    "remediation",
}

BOUNDARY_VALUES = {"template", "instance", "generated"}



def check_files() -> list[str]:
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"Missing required file: {rel}")
    return errors


def check_target_folders() -> list[str]:
    errors: list[str] = []
    targets_dir = ROOT / "targets"
    if not targets_dir.is_dir():
        errors.append("Missing required directory: targets")
        return errors

    for child in sorted(targets_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not (child / "TARGET.yaml").is_file():
            errors.append(f"Target folder missing TARGET.yaml: targets/{child.name}")
    return errors


def check_yaml() -> list[str]:
    errors: list[str] = []
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Note: PyYAML not installed. Skipping YAML parse checks.")
        print("      Install with: pip install pyyaml")
        return errors

    for rel in YAML_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"Missing YAML file: {rel}")
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:  # pragma: no cover
            errors.append(f"YAML parse error in {rel}: {exc}")
            continue

        if data is None:
            errors.append(f"YAML file is empty or invalid: {rel}")
            continue

        if rel.endswith("STUDY_STATE.yaml"):
            for key in REQUIRED_STUDY_STATE_KEYS:
                if key not in data:
                    errors.append(f"Missing key '{key}' in {rel}")
        elif rel.endswith("SKILL_MAP.yaml"):
            for key in REQUIRED_SKILL_MAP_KEYS:
                if key not in data:
                    errors.append(f"Missing key '{key}' in {rel}")

    return errors


def check_no_forbidden_brand() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if path.is_dir():
            if path.name in {".git", ".venv", "node_modules", "__pycache__"}:
                continue
            continue
        # Skip the enforcement script itself and other agent scripts.
        try:
            if path.relative_to(ROOT).parts[0] == "scripts":
                continue
        except (ValueError, IndexError):
            pass
        if path.suffix not in {".md", ".yaml", ".yml", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if FORBIDDEN_BRAND_RE.search(text):
            rel = path.relative_to(ROOT)
            errors.append(f"Forbidden external brand mention in {rel}")
    return errors


def get_git_remotes() -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "remote", "-v"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout
    except Exception:
        return ""


def _load_yaml(path: Path, yaml: object) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def check_mode(yaml: object, warnings: list[str]) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    mode_path = ROOT / "state/STUDYDD_MODE.yaml"
    try:
        mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not read state/STUDYDD_MODE.yaml: {exc}")
        return errors

    mode = mode_data.get("mode")
    allowed_modes = ("template", "bootstrap", "learner_instance")
    if mode not in allowed_modes:
        errors.append(
            f"state/STUDYDD_MODE.yaml mode must be one of {allowed_modes}, got {mode!r}"
        )
        return errors

    remotes = get_git_remotes()
    # The public template repo is StudyState_Template. The legacy
    # StudyDD_Template remote name remains accepted as a compatibility alias:
    # GitHub redirects the old URL, and older checkouts may still carry it.
    is_template_remote = (
        "StudyState_Template" in remotes or "StudyDD_Template" in remotes
    )
    has_remote = bool(remotes.strip())

    study_state_path = ROOT / "state/STUDY_STATE.yaml"
    study_state = _load_yaml(study_state_path, yaml)
    learner = study_state.get("learner") or {}
    active_target_id = study_state.get("active_target_id")

    skill_map_path = ROOT / "state/SKILL_MAP.yaml"
    skill_map = _load_yaml(skill_map_path, yaml)
    has_skills = bool(skill_map.get("skills"))

    if mode == "template":
        if has_remote and not is_template_remote:
            # The mode marker is the authority. A fork, or a copy made with GitHub's
            # "Use this template" button under another name, is still the mold.
            warnings.append(
                "Template mode with a remote that is not StudyState_Template: fine for a fork or a copy "
                "of the template. If this is a learner's repository, run scripts/create_instance.py "
                "instead of studying here."
            )
        if is_template_remote and not mode_data.get("public_safe", True):
            errors.append("Template mode requires public_safe: true")
        if mode_data.get("personalized", False):
            errors.append("Template mode must have personalized: false")

        if active_target_id:
            errors.append(
                f"Template mode should not have an active_target_id ({active_target_id}). "
                "Learner state belongs in a learner instance."
            )

        if learner.get("name"):
            errors.append(
                f"Template mode should not have a learner name ({learner.get('name')}). "
                "Learner state belongs in a learner instance."
            )

        if has_skills:
            errors.append("Template mode should not have populated skills in state/SKILL_MAP.yaml")

    elif mode == "bootstrap":
        if is_template_remote:
            errors.append(
                "Bootstrap mode cannot use the StudyState_Template remote. "
                "Set the learner's remote before leaving bootstrap."
            )
        if mode_data.get("personalized", False):
            errors.append(
                "Bootstrap mode must have personalized: false until learner initialization is complete."
            )

        warnings.append(
            "Bootstrap mode: learner profile and first target are not initialized yet. "
            "Complete personalization and then switch mode to learner_instance."
        )

        # A bootstrap repo is expected to have empty learner state. Do not enforce
        # active target or learner name here; that happens in learner_instance mode.

    elif mode == "learner_instance":
        if is_template_remote:
            errors.append(
                "Learner instance mode cannot use the StudyState_Template remote. "
                "Set a new remote for the learner instance."
            )
        if not mode_data.get("personalized", False):
            errors.append("Learner instance mode should have personalized: true")
        if mode_data.get("public_safe", False) is True:
            errors.append("Learner instance mode should not be public_safe: true")

        if not learner.get("name"):
            errors.append("Learner instance mode requires a learner name in state/STUDY_STATE.yaml")
        if not active_target_id:
            errors.append("Learner instance mode requires an active_target_id in state/STUDY_STATE.yaml")

        # Learner-instance surfaces must be present and structured.
        evidence_path = ROOT / "state/EVIDENCE_LOG.md"
        if not evidence_path.is_file():
            errors.append("Learner instance mode requires state/EVIDENCE_LOG.md")
        else:
            ev_text = evidence_path.read_text(encoding="utf-8")
            if "## Evidence" not in ev_text and "## Evidence items" not in ev_text:
                errors.append("state/EVIDENCE_LOG.md missing '## Evidence' or '## Evidence items' section")

        session_log_path = ROOT / "sessions/SESSION_LOG.md"
        if not session_log_path.is_file():
            errors.append("Learner instance mode requires sessions/SESSION_LOG.md")
        else:
            session_text = session_log_path.read_text(encoding="utf-8")
            if "## Format" not in session_text and "## Sessions" not in session_text:
                errors.append("sessions/SESSION_LOG.md missing expected structure")

        review_queue_path = ROOT / "reviews/REVIEW_QUEUE.md"
        if not review_queue_path.is_file():
            errors.append("Learner instance mode requires reviews/REVIEW_QUEUE.md")
        elif "## Due now" not in review_queue_path.read_text(encoding="utf-8"):
            errors.append("reviews/REVIEW_QUEUE.md missing '## Due now' section")

    return errors


def check_active_target(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    study_state_path = ROOT / "state/STUDY_STATE.yaml"
    try:
        data = yaml.safe_load(study_state_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not read state/STUDY_STATE.yaml for active target check: {exc}")
        return errors

    active_target_id = data.get("active_target_id")
    if not active_target_id:
        # Public template and bootstrap instances are allowed to have no active target.
        return errors

    target_dir = ROOT / "targets" / active_target_id
    target_yaml = target_dir / "TARGET.yaml"
    if not target_yaml.is_file():
        errors.append(
            f"Active target '{active_target_id}' missing TARGET.yaml at targets/{active_target_id}/TARGET.yaml"
        )

    return errors


def check_next_actions() -> list[str]:
    errors: list[str] = []
    next_actions_path = ROOT / "NEXT_ACTIONS.md"
    if not next_actions_path.is_file():
        errors.append("Missing NEXT_ACTIONS.md")
        return errors

    text = next_actions_path.read_text(encoding="utf-8")
    if "## Current next action" not in text:
        errors.append("NEXT_ACTIONS.md missing '## Current next action' section")
    return errors


def check_review_queue() -> list[str]:
    errors: list[str] = []
    queue_path = ROOT / "reviews/REVIEW_QUEUE.md"
    if not queue_path.is_file():
        errors.append("Missing reviews/REVIEW_QUEUE.md")
        return errors

    text = queue_path.read_text(encoding="utf-8")
    for section in ("## Due now", "## Scheduled", "## Review item format"):
        if section not in text:
            errors.append(f"reviews/REVIEW_QUEUE.md missing section '{section}'")
    return errors


def check_session_log() -> list[str]:
    errors: list[str] = []
    log_path = ROOT / "sessions/SESSION_LOG.md"
    if not log_path.is_file():
        errors.append("Missing sessions/SESSION_LOG.md")
        return errors

    text = log_path.read_text(encoding="utf-8")
    if "## Format" not in text and "## Sessions" not in text:
        errors.append("sessions/SESSION_LOG.md missing expected structure")
    return errors


def check_readiness_and_evidence(yaml: object, warnings: list[str]) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    skill_map_path = ROOT / "state/SKILL_MAP.yaml"
    try:
        data = yaml.safe_load(skill_map_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not read state/SKILL_MAP.yaml for readiness check: {exc}")
        return errors

    skills = data.get("skills") or []
    for skill in skills:
        sid = skill.get("id", "<unknown>")
        readiness = skill.get("readiness")
        status = skill.get("status")
        evidence = skill.get("evidence") or []

        if readiness is not None:
            try:
                readiness_val = int(readiness)
            except (TypeError, ValueError):
                errors.append(
                    f"Skill '{sid}' has non-integer readiness value: {readiness}"
                )
                continue
            if not 0 <= readiness_val <= 100:
                errors.append(
                    f"Skill '{sid}' readiness out of range (0-100): {readiness_val}"
                )

        if status in ("practiced", "confirmed", "demonstrated") and not evidence:
            errors.append(
                f"Skill '{sid}' status '{status}' has no evidence references"
            )

        if readiness is not None:
            try:
                readiness_val = int(readiness)
                if readiness_val >= 70 and not evidence:
                    errors.append(
                        f"Skill '{sid}' readiness {readiness} has no evidence references"
                    )
                if readiness_val >= 70 and len(evidence) < 2:
                    warnings.append(
                        f"Skill '{sid}' readiness {readiness} has fewer than 2 evidence references; "
                        "varied/repeated evidence cannot be verified from the current schema."
                    )
            except (TypeError, ValueError):
                pass

    return errors


def check_active_target_source(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    study_state_path = ROOT / "state/STUDY_STATE.yaml"
    source_index_path = ROOT / "sources/SOURCE_INDEX.md"

    try:
        data = yaml.safe_load(study_state_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not read state/STUDY_STATE.yaml for source check: {exc}")
        return errors

    active_target_id = data.get("active_target_id")
    if not active_target_id:
        return errors

    target_yaml_path = ROOT / "targets" / active_target_id / "TARGET.yaml"
    try:
        target_data = yaml.safe_load(target_yaml_path.read_text(encoding="utf-8")) or {}
    except Exception:
        # Missing target file is reported by check_active_target.
        return errors

    target_type = target_data.get("type", "").lower()
    if target_type != "certification":
        return errors

    if not source_index_path.is_file():
        errors.append("Active certification target requires sources/SOURCE_INDEX.md")
        return errors

    text = source_index_path.read_text(encoding="utf-8")
    has_official = bool(re.search(r"\*\*Type:\*\*\s*official", text, re.IGNORECASE))
    has_high = bool(re.search(r"\*\*Authority:\*\*\s*high", text, re.IGNORECASE))
    if not (has_official or has_high):
        errors.append(
            f"Active certification target '{active_target_id}' requires at least one official or high-authority source in sources/SOURCE_INDEX.md"
        )

    return errors


def check_source_freshness() -> list[str]:
    errors: list[str] = []
    source_index_path = ROOT / "sources/SOURCE_INDEX.md"
    if not source_index_path.is_file():
        return errors

    text = source_index_path.read_text(encoding="utf-8")
    entries = re.split(r"\n- \*\*Source ID:\*\*", text)
    for entry in entries[1:]:
        if "**Type:**" not in entry:
            continue
        source_id_match = re.search(r"^\s*(\S+)", entry)
        source_id = source_id_match.group(1) if source_id_match else "<unknown>"
        if "**Last checked:**" not in entry:
            errors.append(
                f"Source '{source_id}' in sources/SOURCE_INDEX.md missing 'Last checked'"
            )

    return errors


def check_state_target_consistency(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    root_skill_path = ROOT / "state/SKILL_MAP.yaml"
    try:
        root_data = yaml.safe_load(root_skill_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return errors

    root_skills = {s.get("id"): s for s in (root_data.get("skills") or []) if s.get("id")}

    for target_dir in (ROOT / "targets").iterdir():
        if not target_dir.is_dir() or target_dir.name.startswith("."):
            continue
        target_state_path = target_dir / "state/SKILL_MAP.yaml"
        if not target_state_path.is_file():
            continue
        try:
            target_data = yaml.safe_load(target_state_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(
                f"Could not parse {target_state_path.relative_to(ROOT)}: {exc}"
            )
            continue

        target_skills = {s.get("id"): s for s in (target_data.get("skills") or []) if s.get("id")}
        for sid in set(root_skills) & set(target_skills):
            root_status = root_skills[sid].get("status")
            target_status = target_skills[sid].get("status")
            root_readiness = root_skills[sid].get("readiness")
            target_readiness = target_skills[sid].get("readiness")
            if root_status and target_status and root_status != target_status:
                errors.append(
                    f"Skill '{sid}' status differs between root ({root_status}) and target/{target_dir.name} ({target_status})"
                )
            if root_readiness is not None and target_readiness is not None:
                try:
                    if int(root_readiness) != int(target_readiness):
                        errors.append(
                            f"Skill '{sid}' readiness differs between root ({root_readiness}) and target/{target_dir.name} ({target_readiness})"
                        )
                except (TypeError, ValueError):
                    pass

    return errors


def check_template_version(yaml: object, warnings: list[str]) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    version_path = ROOT / "state/STUDYDD_TEMPLATE_VERSION.yaml"
    try:
        data = yaml.safe_load(version_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not read state/STUDYDD_TEMPLATE_VERSION.yaml: {exc}")
        return errors

    if "template_version" not in data:
        errors.append("state/STUDYDD_TEMPLATE_VERSION.yaml missing 'template_version'")

    mode_path = ROOT / "state/STUDYDD_MODE.yaml"
    try:
        mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    except Exception:
        mode_data = {}

    if mode_data.get("mode") == "learner_instance":
        if not data.get("instance_created_from_template_version"):
            warnings.append(
                "Learner instance has empty 'instance_created_from_template_version'. "
                "Run the upgrade protocol or recreate the instance from a known template version."
            )
        if not data.get("instance_created_from_template_commit"):
            warnings.append(
                "Learner instance has empty 'instance_created_from_template_commit'."
            )

    return errors


def _load_evidence_log_text() -> str:
    evidence_path = ROOT / "state/EVIDENCE_LOG.md"
    if not evidence_path.is_file():
        return ""
    try:
        return evidence_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def check_evidence_references(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    evidence_text = _load_evidence_log_text()

    skill_map_path = ROOT / "state/SKILL_MAP.yaml"
    try:
        skill_data = yaml.safe_load(skill_map_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return errors

    for skill in skill_data.get("skills") or []:
        sid = skill.get("id", "<unknown>")
        for ref in skill.get("evidence") or []:
            if ref and ref not in evidence_text:
                errors.append(
                    f"Skill '{sid}' evidence reference '{ref}' not found in state/EVIDENCE_LOG.md"
                )

    review_queue_path = ROOT / "reviews/REVIEW_QUEUE.md"
    if review_queue_path.is_file():
        review_text = review_queue_path.read_text(encoding="utf-8")
        for match in re.finditer(r"\*\*Evidence ID:\*\*[ \t]+(\S+)", review_text):
            ref = match.group(1)
            if ref and ref not in evidence_text:
                errors.append(
                    f"Review item evidence reference '{ref}' not found in state/EVIDENCE_LOG.md"
                )

    session_log_path = ROOT / "sessions/SESSION_LOG.md"
    if session_log_path.is_file():
        session_text = session_log_path.read_text(encoding="utf-8")
        # Require evidence IDs to contain at least one digit or hyphen so the
        # format-line placeholder "references to ..." is not treated as a ref.
        id_token = r"[\w\-]*[\d\-][\w\-]*"
        for match in re.finditer(
            rf"\*\*Evidence added:\*\*[ \t]+({id_token}(?:,\s*{id_token})*)", session_text
        ):
            refs = [r.strip() for r in match.group(1).split(",") if r.strip()]
            for ref in refs:
                if ref and ref not in evidence_text:
                    errors.append(
                        f"Session log evidence reference '{ref}' not found in state/EVIDENCE_LOG.md"
                    )

    return errors


def check_review_queue_skills(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    skill_map_path = ROOT / "state/SKILL_MAP.yaml"
    try:
        skill_data = yaml.safe_load(skill_map_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return errors

    skill_ids = {s.get("id") for s in skill_data.get("skills") or [] if s.get("id")}

    review_queue_path = ROOT / "reviews/REVIEW_QUEUE.md"
    if not review_queue_path.is_file():
        return errors

    review_text = review_queue_path.read_text(encoding="utf-8")
    for match in re.finditer(r"\*\*Skill ID:\*\*[ \t]+(\S+)", review_text):
        sid = match.group(1)
        if sid and sid not in skill_ids:
            errors.append(
                f"Review item references unknown skill ID '{sid}' in state/SKILL_MAP.yaml"
            )

    return errors


def check_active_question_consistency(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    study_state_path = ROOT / "state/STUDY_STATE.yaml"
    try:
        study_state = yaml.safe_load(study_state_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return errors

    active_focus = study_state.get("active_focus") or {}
    state_question = active_focus.get("next_question")
    if not state_question:
        return errors

    next_actions_path = ROOT / "NEXT_ACTIONS.md"
    if not next_actions_path.is_file():
        return errors

    next_text = next_actions_path.read_text(encoding="utf-8")
    if state_question not in next_text:
        errors.append(
            f"Active question ID '{state_question}' from state/STUDY_STATE.yaml "
            "does not appear in NEXT_ACTIONS.md"
        )

    return errors


LEAKAGE_PATTERNS = [
    "correct answer",
    "answer_key",
    "[correct]",
    "private answer key",
    "expected answer",
    "rubric",
]
LEAKAGE_RE = re.compile("|".join(re.escape(p) for p in LEAKAGE_PATTERNS), re.IGNORECASE)


def check_answer_key_leakage() -> list[str]:
    """Heuristic scan for pre-answer leakage on learner-facing target surfaces."""
    errors: list[str] = []
    targets_dir = ROOT / "targets"
    if not targets_dir.is_dir():
        return errors

    skip_dir_names = {
        "questions",
        "__pycache__",
        ".pytest_cache",
    }

    for path in targets_dir.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(targets_dir).parts
        if any(part in skip_dir_names for part in rel_parts):
            continue
        if path.name == "README.md":
            continue
        if path.suffix.lower() not in {".md", ".yaml", ".yml", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if LEAKAGE_RE.search(text):
            rel = path.relative_to(ROOT)
            errors.append(
                f"Possible answer-key leakage in learner-facing file: {rel}"
            )

    return errors


QUESTION_BANK_REQUIRED_FIELDS = [
    "id",
    "target_id",
    "skill_id",
    "cognitive_level",
    "difficulty",
    "source_ref",
    "public_prompt",
    "private_answer_key",
    "rubric",
    "common_traps",
    "last_used",
    "cooldown_days",
]


def check_question_bank(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    targets_dir = ROOT / "targets"
    if not targets_dir.is_dir():
        return errors

    for path in targets_dir.rglob("questions/*.yaml"):
        if not path.is_file():
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(f"Could not parse question file {path.relative_to(ROOT)}: {exc}")
            continue

        for field in QUESTION_BANK_REQUIRED_FIELDS:
            if field == "source_ref":
                # Accept either a legacy source_ref or a non-empty source_ids list.
                has_source_ref = "source_ref" in data and data["source_ref"] not in (None, "")
                source_ids = data.get("source_ids")
                has_source_ids = isinstance(source_ids, list) and bool(source_ids)
                if not (has_source_ref or has_source_ids):
                    errors.append(
                        f"Question file {path.relative_to(ROOT)} missing or empty source reference ('source_ref' or 'source_ids')"
                    )
                continue
            if field not in data or data[field] in (None, ""):
                errors.append(
                    f"Question file {path.relative_to(ROOT)} missing or empty field '{field}'"
                )

        # Optional transfer_probe: if present, must not be empty.
        if "transfer_probe" in data and data["transfer_probe"] in (None, ""):
            errors.append(
                f"Question file {path.relative_to(ROOT)} has empty optional field 'transfer_probe'"
            )

    return errors


REVIEW_STATUSES = {"scheduled", "due", "overdue", "completed", "suspended"}
ACTIVITY_STATUSES = {"proposed", "accepted", "modified", "overridden", "completed", "insufficient_evidence"}


def _parse_iso_timestamp(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def check_review_state(yaml: object, warnings: list[str]) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    mode_path = ROOT / "state/STUDYDD_MODE.yaml"
    try:
        mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    except Exception:
        mode_data = {}
    mode = mode_data.get("mode")

    review_state_path = ROOT / "reviews/REVIEW_STATE.yaml"
    try:
        review_state = yaml.safe_load(review_state_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        if mode == "learner_instance":
            errors.append(f"Could not read reviews/REVIEW_STATE.yaml: {exc}")
        return errors

    items = review_state.get("review_items") or []

    if mode != "learner_instance":
        # Template and bootstrap may have empty review state.
        return errors

    if not isinstance(items, list):
        errors.append("reviews/REVIEW_STATE.yaml 'review_items' must be a list")
        return errors

    skill_map = _load_yaml(ROOT / "state/SKILL_MAP.yaml", yaml)
    skill_ids = {s.get("id") for s in skill_map.get("skills") or [] if s.get("id")}
    evidence_text = _load_evidence_log_text()

    queue_text = ""
    queue_path = ROOT / "reviews/REVIEW_QUEUE.md"
    if queue_path.is_file():
        queue_text = queue_path.read_text(encoding="utf-8")

    next_actions_text = ""
    next_actions_path = ROOT / "NEXT_ACTIONS.md"
    if next_actions_path.is_file():
        next_actions_text = next_actions_path.read_text(encoding="utf-8")

    for item in items:
        rid = item.get("id") or "<unknown>"
        status = item.get("status")
        if status not in REVIEW_STATUSES:
            errors.append(
                f"Review '{rid}' has invalid status {status!r}; must be one of {sorted(REVIEW_STATUSES)}"
            )

        interval = item.get("interval_days")
        # 0 is valid: a wrong, low-confidence answer is due again the same day.
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval < 0:
            errors.append(
                f"Review '{rid}' must have a non-negative interval_days value (0 means due the same day)"
            )

        skill_id = item.get("skill_id")
        if skill_id and skill_id not in skill_ids:
            errors.append(f"Review '{rid}' references unknown skill ID '{skill_id}'")

        evidence_id = item.get("evidence_id")
        if evidence_id and evidence_id not in evidence_text:
            errors.append(
                f"Review '{rid}' evidence reference '{evidence_id}' not found in state/EVIDENCE_LOG.md"
            )

        for field in ("due_at", "last_reviewed_at"):
            value = item.get(field)
            if not value:
                continue
            dt = _parse_iso_timestamp(value)
            if dt is None:
                errors.append(
                    f"Review '{rid}' field '{field}' is not a valid timezone-aware ISO 8601 timestamp: {value!r}"
                )

        override_count = item.get("override_count") or 0
        if override_count >= 2 and status in ("due", "overdue"):
            warnings.append(
                f"Review '{rid}' has been overridden {override_count} times and is still due/overdue. "
                "Consider reviewing it soon or discussing the block with the learner."
            )

        # Warn if an overdue item is not surfaced in the human-readable queue or next actions.
        due_at_str = item.get("due_at")
        if due_at_str and status == "overdue":
            if rid not in queue_text and rid not in next_actions_text:
                warnings.append(
                    f"Overdue review '{rid}' is not visible in reviews/REVIEW_QUEUE.md or NEXT_ACTIONS.md"
                )

    return errors


def check_activity_state(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    activity_state_path = ROOT / "state" / "ACTIVITY_STATE.yaml"
    if not activity_state_path.is_file():
        errors.append("Missing state/ACTIVITY_STATE.yaml")
        return errors

    try:
        data = yaml.safe_load(activity_state_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not parse state/ACTIVITY_STATE.yaml: {exc}")
        return errors

    active = data.get("active_activity") or {}
    if active.get("id"):
        if active.get("type") == "":
            errors.append("Active activity has an id but no type")
        if active.get("status") and active.get("status") not in ACTIVITY_STATUSES:
            errors.append(
                f"Active activity '{active.get('id')}' has invalid status {active.get('status')!r}; "
                f"must be one of {sorted(ACTIVITY_STATUSES)}"
            )

    # In template mode, activity state must stay generic/empty.
    mode_path = ROOT / "state" / "STUDYDD_MODE.yaml"
    try:
        mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    except Exception:
        mode_data = {}
    if mode_data.get("mode") == "template":
        if active.get("id"):
            errors.append("Template mode should not have an active activity id")
        recent = data.get("recent_activities") or []
        if recent:
            errors.append("Template mode should not have recent_activities entries")
        prefs = data.get("activity_preferences") or {}
        for key, value in prefs.items():
            if isinstance(value, list) and value:
                errors.append(
                    f"Template mode: state/ACTIVITY_STATE.yaml activity_preferences.{key} must be empty"
                )

    return errors


def check_activity_templates(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    templates_path = ROOT / "activities" / "ACTIVITY_TEMPLATES.yaml"
    if not templates_path.is_file():
        errors.append("Missing activities/ACTIVITY_TEMPLATES.yaml")
        return errors

    try:
        data = yaml.safe_load(templates_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not parse activities/ACTIVITY_TEMPLATES.yaml: {exc}")
        return errors

    templates = data.get("templates") or []
    if not isinstance(templates, list):
        errors.append("activities/ACTIVITY_TEMPLATES.yaml 'templates' must be a list")
        return errors

    activity_types = data.get("activity_types") or {}
    known_types = set(activity_types.keys())

    for template in templates:
        if not isinstance(template, dict):
            errors.append("activities/ACTIVITY_TEMPLATES.yaml contains a non-mapping template entry")
            continue
        tid = template.get("id") or "<unknown>"
        ttype = template.get("activity_type")
        if not ttype:
            errors.append(f"Activity template '{tid}' missing 'activity_type'")
        elif ttype not in known_types:
            errors.append(f"Activity template '{tid}' has unknown activity_type '{ttype}'")
        expected = template.get("expected_evidence")
        if not isinstance(expected, list) or not expected:
            errors.append(f"Activity template '{tid}' missing or empty 'expected_evidence'")

    return errors


def check_activity_log() -> list[str]:
    errors: list[str] = []
    log_path = ROOT / "activities" / "ACTIVITY_LOG.md"
    if not log_path.is_file():
        errors.append("Missing activities/ACTIVITY_LOG.md")
        return errors

    text = log_path.read_text(encoding="utf-8")
    for section in ("## Purpose", "## Activity entry format", "## Activities"):
        if section not in text:
            errors.append(f"activities/ACTIVITY_LOG.md missing section '{section}'")
    return errors


def check_activity_state_target_skill(yaml: object) -> list[str]:
    """Check that learner-instance activity entries reference valid target/skill."""
    errors: list[str] = []
    if yaml is None:
        return errors

    activity_state_path = ROOT / "state" / "ACTIVITY_STATE.yaml"
    if not activity_state_path.is_file():
        return errors

    try:
        data = yaml.safe_load(activity_state_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return errors

    skill_map = _load_yaml(ROOT / "state" / "SKILL_MAP.yaml", yaml)
    skill_ids = {s.get("id") for s in skill_map.get("skills") or [] if s.get("id")}

    recent = data.get("recent_activities") or []
    if not isinstance(recent, list):
        return errors

    for activity in recent:
        if not isinstance(activity, dict):
            continue
        target_id = activity.get("target_id")
        skill_id = activity.get("skill_id")
        activity_id = activity.get("id") or "<unknown>"
        if target_id and not (ROOT / "targets" / target_id / "TARGET.yaml").is_file():
            errors.append(
                f"Recent activity '{activity_id}' references unknown target '{target_id}'"
            )
        if skill_id and skill_id not in skill_ids:
            errors.append(
                f"Recent activity '{activity_id}' references unknown skill '{skill_id}'"
            )

    return errors


def check_state_manifest(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    manifest_path = ROOT / "state" / "STATE_MANIFEST.yaml"
    if not manifest_path.is_file():
        errors.append("Missing state/STATE_MANIFEST.yaml")
        return errors

    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not parse state/STATE_MANIFEST.yaml: {exc}")
        return errors

    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        errors.append("state/STATE_MANIFEST.yaml 'files' must be a mapping")
        return errors

    required_roles = {"canonical", "append_only_audit", "derived_summary", "derived_index"}
    seen_roles = set()
    for rel, meta in files.items():
        if not isinstance(meta, dict):
            errors.append(f"state/STATE_MANIFEST.yaml entry '{rel}' must be a mapping")
            continue
        role = meta.get("role")
        if role:
            seen_roles.add(role)
        if meta.get("protected") and role != "canonical":
            errors.append(f"state/STATE_MANIFEST.yaml '{rel}' is protected but role is not canonical")
        rel_path = ROOT / rel
        if meta.get("load_default") and not rel_path.is_file():
            errors.append(f"state/STATE_MANIFEST.yaml '{rel}' is load_default but missing")
        boundary = meta.get("boundary")
        if boundary not in BOUNDARY_VALUES:
            errors.append(
                f"state/STATE_MANIFEST.yaml '{rel}' has missing or invalid boundary {boundary!r}; "
                f"must be one of {sorted(BOUNDARY_VALUES)}"
            )

    missing_roles = required_roles - seen_roles
    for role in sorted(missing_roles):
        errors.append(f"state/STATE_MANIFEST.yaml missing at least one file with role '{role}'")

    return errors


def _audit_log_has_entries(text: str, content_header: str) -> bool:
    """Return True if an append-only audit log section contains real entries."""
    section = text.split(content_header, 1)[1] if content_header in text else text
    entry_markers = ("- **Date:**", "- **Activity ID:**", "- **Timestamp:**")
    has_placeholder = "None yet." in section
    has_entry = any(marker in section for marker in entry_markers)
    return has_entry or not has_placeholder


def check_template_boundary(yaml: object) -> list[str]:
    """Fail when instance-boundary files contain learner data in template mode."""
    errors: list[str] = []
    if yaml is None:
        return errors

    mode_path = ROOT / "state" / "STUDYDD_MODE.yaml"
    mode_data = _load_yaml(mode_path, yaml)
    if mode_data.get("mode") != "template":
        return errors

    manifest_path = ROOT / "state" / "STATE_MANIFEST.yaml"
    manifest = _load_yaml(manifest_path, yaml)
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        return errors

    instance_checks: dict[str, object] = {
        "state/STUDY_STATE.yaml": lambda d: (
            (d.get("learner") or {}).get("name")
            or d.get("active_target_id")
            or d.get("targets")
            or d.get("skills")
            or d.get("session_history")
        ),
        "state/SKILL_MAP.yaml": lambda d: d.get("skills"),
        "reviews/REVIEW_STATE.yaml": lambda d: d.get("review_items"),
        "state/LEARNER_PROFILE.yaml": lambda d: (
            (d.get("adaptation_state") or {}).get("methods_tried")
            or (d.get("control") or {}).get("learner_overrides")
            or (d.get("control") or {}).get("agent_recommendations_declined")
        ),
        "sources/SOURCE_STATE.yaml": lambda d: d.get("sources"),
        "state/ACTIVITY_STATE.yaml": lambda d: (
            (d.get("active_activity") or {}).get("id")
            or d.get("recent_activities")
        ),
    }

    log_headers = {
        "state/EVIDENCE_LOG.md": "## Evidence items",
        "sessions/SESSION_LOG.md": "## Sessions",
        "reviews/REVIEW_OVERRIDES.md": "## Overrides",
        "activities/ACTIVITY_LOG.md": "## Activities",
    }

    for rel, meta in files.items():
        if meta.get("boundary") != "instance":
            continue
        if rel in instance_checks:
            path = ROOT / rel
            if not path.is_file():
                continue
            data = _load_yaml(path, yaml)
            if instance_checks[rel](data):
                errors.append(
                    f"Template boundary violation: {rel} contains learner-specific data. "
                    "Create a learner instance with scripts/create_instance.py instead."
                )
        elif rel in log_headers:
            path = ROOT / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if _audit_log_has_entries(text, log_headers[rel]):
                errors.append(
                    f"Template boundary violation: {rel} contains learner-specific data. "
                    "Create a learner instance with scripts/create_instance.py instead."
                )

    return errors


def check_context_pack_gitignored() -> list[str]:
    errors: list[str] = []
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        errors.append("Missing .gitignore; .studydd/ must be ignored")
        return errors

    text = gitignore.read_text(encoding="utf-8")
    if ".studydd/" not in text and ".studydd" not in text:
        errors.append(".studydd/ is not ignored in .gitignore")
    return errors


def check_state_cache_gitignored() -> list[str]:
    errors: list[str] = []
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        errors.append("Missing .gitignore; .studydd/state_cache.json must be ignored")
        return errors

    text = gitignore.read_text(encoding="utf-8")
    if ".studydd/state_cache.json" not in text and ".studydd/" not in text and ".studydd" not in text:
        errors.append(".studydd/state_cache.json is not ignored in .gitignore")
    return errors


def check_evidence_index(yaml: object) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    index_path = ROOT / "state" / "EVIDENCE_INDEX.yaml"
    log_path = ROOT / "state" / "EVIDENCE_LOG.md"
    if not index_path.is_file():
        errors.append("Missing state/EVIDENCE_INDEX.yaml")
        return errors

    try:
        index_data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"Could not parse state/EVIDENCE_INDEX.yaml: {exc}")
        return errors

    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    items = index_data.get("items") or []
    for item in items:
        eid = item.get("evidence_id")
        if eid and eid not in log_text:
            errors.append(
                f"state/EVIDENCE_INDEX.yaml evidence_id '{eid}' not found in state/EVIDENCE_LOG.md"
            )
    return errors


def check_session_summaries() -> list[str]:
    errors: list[str] = []
    log_path = ROOT / "sessions" / "SESSION_LOG.md"
    summaries_path = ROOT / "sessions" / "SESSION_SUMMARIES.md"

    if not summaries_path.is_file():
        errors.append("Missing sessions/SESSION_SUMMARIES.md")
        return errors

    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    summaries_text = summaries_path.read_text(encoding="utf-8")

    # Heuristic: if log contains a real date-like entry, summaries should list >0 sessions.
    has_real_sessions = bool(
        re.search(r"\*\*Date:\*\*\s*\d{4}-\d{2}-\d{2}", log_text)
    )
    count_match = re.search(r"\*\*Total sessions:\*\*\s*(\d+)", summaries_text)
    count = int(count_match.group(1)) if count_match else 0

    if has_real_sessions and count == 0:
        errors.append("sessions/SESSION_SUMMARIES.md reports 0 sessions but SESSION_LOG.md has real sessions")

    if "No sessions recorded yet." in summaries_text and has_real_sessions:
        errors.append("sessions/SESSION_SUMMARIES.md is empty but SESSION_LOG.md has real sessions")

    return errors


def check_current_context() -> list[str]:
    errors: list[str] = []
    path = ROOT / "state" / "CURRENT_CONTEXT.md"
    if not path.is_file():
        errors.append("Missing state/CURRENT_CONTEXT.md")
        return errors

    text = path.read_text(encoding="utf-8")
    for section in ("## Active target", "## Reviews", "## Weak skills", "## Next action"):
        if section not in text:
            errors.append(f"state/CURRENT_CONTEXT.md missing section '{section}'")
    return errors


def check_generated_freshness(warnings: list[str]) -> list[str]:
    errors: list[str] = []
    pairs = [
        ("state/EVIDENCE_INDEX.yaml", "state/EVIDENCE_LOG.md"),
        ("sessions/SESSION_SUMMARIES.md", "sessions/SESSION_LOG.md"),
        ("state/CURRENT_CONTEXT.md", "state/STUDY_STATE.yaml"),
    ]
    for generated, source in pairs:
        gen_path = ROOT / generated
        src_path = ROOT / source
        if not gen_path.is_file() or not src_path.is_file():
            continue
        try:
            gen_mtime = gen_path.stat().st_mtime
            src_mtime = src_path.stat().st_mtime
            if src_mtime > gen_mtime:
                warnings.append(
                    f"{generated} appears older than {source}. Run scripts/compact_state.py."
                )
        except Exception:
            pass
    return errors


def check_study_skills(yaml: object, warnings: list[str]) -> list[str]:
    errors: list[str] = []
    if yaml is None:
        return errors

    skills_dir = ROOT / "study_skills"
    if not skills_dir.is_dir():
        errors.append("Missing study_skills/ directory")
        return errors

    required_skills = [
        "generic",
        "it_certification",
        "philosophy",
        "primary_math",
        "language_learning",
        "interview_prep",
        "practical_lab",
    ]
    for skill_id in required_skills:
        skill_file = skills_dir / skill_id / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"Missing study skill file: study_skills/{skill_id}/SKILL.md")

    mode_path = ROOT / "state" / "STUDYDD_MODE.yaml"
    mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    mode = mode_data.get("mode")

    if mode in ("bootstrap", "learner_instance"):
        study_state = yaml.safe_load((ROOT / "state" / "STUDY_STATE.yaml").read_text(encoding="utf-8")) or {}
        active_target = study_state.get("active_target_id")
        if active_target:
            target_yaml = ROOT / "targets" / active_target / "TARGET.yaml"
            if target_yaml.is_file():
                target_data = yaml.safe_load(target_yaml.read_text(encoding="utf-8")) or {}
                declared_skill = target_data.get("study_skill")
                if declared_skill:
                    skill_file = skills_dir / declared_skill / "SKILL.md"
                    if not skill_file.is_file():
                        errors.append(
                            f"Active target '{active_target}' declares unknown study_skill '{declared_skill}'"
                        )
                else:
                    warnings.append(
                        f"Active target '{active_target}' does not declare a study_skill; generic tutoring will be used."
                    )

    return errors


def check_option_position_randomization() -> list[str]:
    """Lightweight warning when example session logs show obvious answer-position patterns.

    This is a heuristic. It scans EXAMPLES/*/sessions/SESSION_LOG.md for lines that
    record a final option order and a correct label. If every recorded example uses
    the same correct label, it warns that the examples may teach answer-position habits.
    """
    errors: list[str] = []
    label_pattern = re.compile(r"correct label\s+([A-D])", re.IGNORECASE)
    labels: list[str] = []

    examples_dir = ROOT / "EXAMPLES"
    if not examples_dir.is_dir():
        return errors

    for session_log in examples_dir.rglob("sessions/SESSION_LOG.md"):
        try:
            text = session_log.read_text(encoding="utf-8")
        except Exception:
            continue
        for match in label_pattern.finditer(text):
            labels.append(match.group(1).upper())

    if len(labels) >= 3 and len(set(labels)) == 1:
        errors.append(
            f"All {len(labels)} recorded example option questions have the same correct label "
            f"({labels[0]}). Randomize example correct labels so the template does not teach "
            "answer-position habits."
        )

    return errors


def _discover_question_files() -> list[Path]:
    """Return all question YAML files under targets/ and EXAMPLES/."""
    found: list[Path] = []
    targets_dir = ROOT / "targets"
    examples_dir = ROOT / "EXAMPLES"

    if targets_dir.is_dir():
        found.extend(targets_dir.rglob("questions/*.yaml"))
    if examples_dir.is_dir():
        for example_dir in examples_dir.iterdir():
            if not example_dir.is_dir() or example_dir.name.startswith("."):
                continue
            example_targets = example_dir / "targets"
            if example_targets.is_dir():
                found.extend(example_targets.rglob("questions/*.yaml"))
    return found


def check_source_state(yaml: object) -> list[str]:
    """Validate sources/SOURCE_STATE.yaml structure."""
    errors: list[str] = []
    if yaml is None:
        return errors

    source_state_path = ROOT / "sources" / "SOURCE_STATE.yaml"
    if not source_state_path.is_file():
        errors.append("Missing sources/SOURCE_STATE.yaml")
        return errors

    data = _load_yaml(source_state_path, yaml)
    sources = data.get("sources") or []
    if not isinstance(sources, list):
        errors.append("sources/SOURCE_STATE.yaml 'sources' must be a list")
        return errors

    for source in sources:
        if not isinstance(source, dict):
            errors.append("sources/SOURCE_STATE.yaml contains a non-mapping source entry")
            continue

        sid = source.get("id")
        if not isinstance(sid, str) or not sid:
            errors.append("Source entry missing or invalid 'id'")
            sid = "<unknown>"

        authority = source.get("authority")
        if authority not in SOURCE_AUTHORITY_VALUES:
            errors.append(
                f"Source '{sid}' has invalid authority {authority!r}; "
                f"must be one of {sorted(SOURCE_AUTHORITY_VALUES)}"
            )

        target_ids = source.get("target_ids")
        if not isinstance(target_ids, list) or not all(isinstance(t, str) for t in target_ids):
            errors.append(f"Source '{sid}' target_ids must be a list of strings")

        volatility = source.get("volatility")
        if volatility not in SOURCE_VOLATILITY_VALUES:
            errors.append(
                f"Source '{sid}' has invalid volatility {volatility!r}; "
                f"must be one of {sorted(SOURCE_VOLATILITY_VALUES)}"
            )

        for field in ("last_checked_at", "expires_at"):
            value = source.get(field)
            if value is not None and _parse_iso_timestamp(value) is None:
                errors.append(
                    f"Source '{sid}' field '{field}' is not a valid timezone-aware ISO 8601 timestamp"
                )

        usable = source.get("usable_for_questions", True)
        if not isinstance(usable, bool):
            errors.append(f"Source '{sid}' usable_for_questions must be a boolean")

        last_check = source.get("last_check")
        if last_check is not None:
            if not isinstance(last_check, dict):
                errors.append(f"Source '{sid}' last_check must be a mapping")
            else:
                outcome = last_check.get("outcome")
                if outcome is not None and outcome not in SOURCE_OUTCOMES:
                    errors.append(
                        f"Source '{sid}' last_check.outcome {outcome!r} is invalid; "
                        f"must be one of {sorted(SOURCE_OUTCOMES)}"
                    )
                checked_at = last_check.get("checked_at")
                if checked_at is not None and _parse_iso_timestamp(checked_at) is None:
                    errors.append(
                        f"Source '{sid}' last_check.checked_at is not a valid timezone-aware ISO 8601 timestamp"
                    )
                checked_by = last_check.get("checked_by")
                if checked_by is not None and checked_by not in ("agent", "learner"):
                    errors.append(
                        f"Source '{sid}' last_check.checked_by must be 'agent' or 'learner'"
                    )

    return errors


def check_learner_profile(yaml: object) -> list[str]:
    """Validate state/LEARNER_PROFILE.yaml. In template mode it must stay generic."""
    errors: list[str] = []
    if yaml is None:
        return errors

    mode_path = ROOT / "state" / "STUDYDD_MODE.yaml"
    mode_data = _load_yaml(mode_path, yaml)
    mode = mode_data.get("mode")

    profile_path = ROOT / "state" / "LEARNER_PROFILE.yaml"
    if not profile_path.is_file():
        errors.append("Missing state/LEARNER_PROFILE.yaml")
        return errors

    data = _load_yaml(profile_path, yaml)
    if mode != "template":
        # Learner-instance and bootstrap modes may contain personalized values.
        return errors

    preferences = data.get("learner_preferences") or {}
    if isinstance(preferences, dict):
        for key, value in preferences.items():
            if value not in (None, ""):
                errors.append(
                    f"Template mode: state/LEARNER_PROFILE.yaml learner_preferences.{key} "
                    f"must be empty or null, got {value!r}"
                )

    adaptation = data.get("adaptation_state") or {}
    if isinstance(adaptation, dict):
        for key, value in adaptation.items():
            if isinstance(value, list) and value:
                errors.append(
                    f"Template mode: state/LEARNER_PROFILE.yaml adaptation_state.{key} must be empty"
                )

    control = data.get("control") or {}
    if isinstance(control, dict):
        for key, value in control.items():
            if isinstance(value, list) and value:
                errors.append(
                    f"Template mode: state/LEARNER_PROFILE.yaml control.{key} must be empty"
                )

    return errors


def check_volatile_target_freshness(
    yaml: object, warnings: list[str], now: datetime | None = None
) -> list[str]:
    """Ensure volatile/live targets have a fresh authoritative usable source.

    Hard error in learner_instance mode; warning only in template/bootstrap modes.
    """
    errors: list[str] = []
    if yaml is None:
        return errors

    mode_path = ROOT / "state" / "STUDYDD_MODE.yaml"
    mode_data = _load_yaml(mode_path, yaml)
    mode = mode_data.get("mode")

    source_state = _load_yaml(ROOT / "sources" / "SOURCE_STATE.yaml", yaml)
    sources = source_state.get("sources") or []

    targets_dir = ROOT / "targets"
    if not targets_dir.is_dir():
        return errors

    if now is None:
        now = datetime.now(timezone.utc)

    for target_dir in targets_dir.iterdir():
        if not target_dir.is_dir() or target_dir.name.startswith("."):
            continue
        target_data = _load_yaml(target_dir / "TARGET.yaml", yaml)
        volatility = target_data.get("volatility")
        if volatility not in ("volatile", "live"):
            continue

        target_id = target_dir.name
        target_sources = [s for s in sources if target_id in (s.get("target_ids") or [])]
        has_fresh_authoritative = False
        for source in target_sources:
            if source.get("authority") not in ("official", "high_authority"):
                continue
            if source.get("usable_for_questions") is False:
                continue
            status, _ = classify_source(source, now, volatility)
            if status == "fresh":
                has_fresh_authoritative = True
                break

        if not has_fresh_authoritative:
            msg = (
                f"Target '{target_id}' has volatility '{volatility}' but no fresh "
                "official/high_authority usable source in sources/SOURCE_STATE.yaml"
            )
            if mode == "learner_instance":
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors


def _is_reference_snapshot(path: Path) -> bool:
    """Return True when path is a fixture under the EXAMPLES/ snapshot root."""
    try:
        rel_parts = path.relative_to(ROOT).parts
    except ValueError:
        return False
    return len(rel_parts) >= 1 and rel_parts[0] == REFERENCE_SNAPSHOT_ROOT


def _source_state_for_question(path: Path, yaml: object) -> tuple[list[dict[str, Any]], set[str]]:
    """Return (sources, known_source_ids) for the repo root that contains the question.

    Example fixtures use their own sources/SOURCE_STATE.yaml; the main repo uses ROOT.
    """
    rel_parts = path.relative_to(ROOT).parts
    if len(rel_parts) >= 2 and rel_parts[0] == "EXAMPLES":
        source_state_path = ROOT / "EXAMPLES" / rel_parts[1] / "sources" / "SOURCE_STATE.yaml"
    else:
        source_state_path = ROOT / "sources" / "SOURCE_STATE.yaml"

    source_state = _load_yaml(source_state_path, yaml)
    sources = source_state.get("sources") or []
    known_source_ids = {s.get("id") for s in sources if s.get("id")}
    return sources, known_source_ids


def check_question_quality_records(
    yaml: object, now: datetime | None = None, snapshot_clock_explicit: bool = False
) -> list[str]:
    """Validate question-quality metadata and source grounding for question banks.

    ``now`` defaults to the wall clock. When ``snapshot_clock_explicit`` is True
    (an --now override was provided), reference fixtures under EXAMPLES/ are
    evaluated with that clock too; otherwise their timestamps are treated as
    deterministic test metadata and only time-independent structure is enforced.
    """
    errors: list[str] = []
    if yaml is None:
        return errors

    if now is None:
        now = datetime.now(timezone.utc)

    for path in _discover_question_files():
        data = _load_yaml(path, yaml)
        if not isinstance(data, dict):
            continue

        sources, known_source_ids = _source_state_for_question(path, yaml)

        qid = data.get("id") or path.stem
        rel = path.relative_to(ROOT)

        target_data = _load_yaml(path.parent.parent / "TARGET.yaml", yaml)
        target_volatility = target_data.get("volatility") or "moderate"
        volatility = data.get("volatility") or target_volatility
        if volatility not in SOURCE_VOLATILITY_VALUES:
            volatility = "moderate"

        question_mode = data.get("question_mode")
        if question_mode is not None and question_mode not in QUESTION_MODES:
            errors.append(
                f"Question {qid} ({rel}) has invalid question_mode {question_mode!r}"
            )

        quality = data.get("question_quality")
        if isinstance(quality, dict):
            gate = quality.get("quality_gate")
            if gate is not None and gate not in ("pass", "warn", "fail"):
                errors.append(
                    f"Question {qid} ({rel}) has invalid question_quality.quality_gate {gate!r}"
                )
            if gate in ("warn", "fail"):
                reason = quality.get("quality_gate_reason")
                if not reason:
                    errors.append(
                        f"Question {qid} ({rel}) has quality_gate '{gate}' but missing "
                        "question_quality.quality_gate_reason"
                    )

        has_source_ref = isinstance(data.get("source_ref"), str) and bool(data["source_ref"])
        source_ids = data.get("source_ids")
        has_source_ids = isinstance(source_ids, list) and bool(source_ids)

        if volatility in ("moderate", "volatile", "live"):
            if not (has_source_ref or has_source_ids):
                errors.append(
                    f"Question {qid} ({rel}) has volatility '{volatility}' but missing "
                    "source_ref or source_ids"
                )

        if has_source_ids:
            for sid in source_ids:
                if sid not in known_source_ids:
                    errors.append(
                        f"Question {qid} ({rel}) references unknown source_id '{sid}'"
                    )

        if (
            volatility in ("volatile", "live")
            and question_mode == "authoritative_current"
        ):
            if not has_source_ids:
                errors.append(
                    f"Question {qid} ({rel}) is authoritative_current with volatility "
                    f"'{volatility}' but has no source_ids"
                )
            else:
                for sid in source_ids:
                    source = next((s for s in sources if s.get("id") == sid), None)
                    if source is None:
                        # Unknown source_id is already reported above.
                        continue
                    status, reason = classify_source(source, now, volatility)
                    if status != "fresh":
                        if _is_reference_snapshot(path) and not snapshot_clock_explicit:
                            # Reference fixture: timestamps are deterministic test
                            # metadata, not a live freshness claim.
                            continue
                        detail = f" ({reason})" if reason else ""
                        errors.append(
                            f"Question {qid} ({rel}) authoritative_current source '{sid}' "
                            f"is {status}{detail}"
                        )
                        continue
                    if source.get("authority") not in ("official", "high_authority"):
                        errors.append(
                            f"Question {qid} ({rel}) authoritative_current source '{sid}' "
                            f"has authority {source.get('authority')!r}"
                        )
                    elif source.get("usable_for_questions") is False:
                        errors.append(
                            f"Question {qid} ({rel}) authoritative_current source '{sid}' "
                            "has usable_for_questions: false"
                        )

    return errors


def check_stale_practice_overrides(yaml: object) -> list[str]:
    """Heuristic check that stale_practice questions record an override rationale."""
    errors: list[str] = []
    if yaml is None:
        return errors

    overrides_path = ROOT / "reviews" / "REVIEW_OVERRIDES.md"
    overrides_text = overrides_path.read_text(encoding="utf-8") if overrides_path.is_file() else ""

    for path in _discover_question_files():
        data = _load_yaml(path, yaml)
        if not isinstance(data, dict):
            continue
        if data.get("question_mode") != "stale_practice":
            continue

        qid = data.get("id") or path.stem
        rel = path.relative_to(ROOT)
        quality = data.get("question_quality") or {}
        notes = quality.get("notes") or ""

        # Accept either per-question notes or any mention in the override log.
        has_evidence = bool(notes) or qid in overrides_text or "stale_practice" in overrides_text
        if not has_evidence:
            errors.append(
                f"Question {qid} ({rel}) has question_mode: stale_practice but no "
                "override evidence in question_quality.notes or reviews/REVIEW_OVERRIDES.md"
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="StudyState repo health and educational-drift validator."
    )
    parser.add_argument(
        "--now",
        help=(
            "Evaluate time-based checks (source freshness) as if it were this "
            "UTC ISO 8601 timestamp. Also applies the explicit clock to EXAMPLES/ "
            "reference fixtures instead of exempting them from wall-clock staleness."
        ),
        default=None,
    )
    args = parser.parse_args(argv)

    now_override: datetime | None = None
    if args.now is not None:
        try:
            parsed = datetime.fromisoformat(str(args.now))
        except ValueError:
            print(f"Invalid --now value: {args.now!r} (expected ISO 8601)")
            return 2
        now_override = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    print("StudyState validation")
    print("==================")
    if now_override is not None:
        print(f"Evaluation clock: {now_override.isoformat()}")

    errors = check_files()
    errors.extend(check_target_folders())
    errors.extend(check_yaml())
    errors.extend(check_no_forbidden_brand())
    errors.extend(check_next_actions())
    errors.extend(check_review_queue())
    errors.extend(check_session_log())
    errors.extend(check_option_position_randomization())

    warnings: list[str] = []

    try:
        import yaml
    except ImportError:  # pragma: no cover
        yaml = None

    if yaml is not None:
        errors.extend(check_mode(yaml, warnings))
        errors.extend(check_active_target(yaml))
        errors.extend(check_template_version(yaml, warnings))
        errors.extend(check_readiness_and_evidence(yaml, warnings))
        errors.extend(check_active_target_source(yaml))
        errors.extend(check_source_freshness())
        errors.extend(check_state_target_consistency(yaml))
        errors.extend(check_evidence_references(yaml))
        errors.extend(check_review_queue_skills(yaml))
        errors.extend(check_active_question_consistency(yaml))
        errors.extend(check_answer_key_leakage())
        errors.extend(check_question_bank(yaml))
        errors.extend(check_review_state(yaml, warnings))
        errors.extend(check_activity_state(yaml))
        errors.extend(check_activity_templates(yaml))
        errors.extend(check_activity_log())
        errors.extend(check_activity_state_target_skill(yaml))
        errors.extend(check_state_manifest(yaml))
        errors.extend(check_context_pack_gitignored())
        errors.extend(check_state_cache_gitignored())
        errors.extend(check_evidence_index(yaml))
        errors.extend(check_session_summaries())
        errors.extend(check_current_context())
        errors.extend(check_study_skills(yaml, warnings))
        errors.extend(check_generated_freshness(warnings))
        errors.extend(check_source_state(yaml))
        errors.extend(check_learner_profile(yaml))
        errors.extend(check_template_boundary(yaml))
        errors.extend(check_volatile_target_freshness(yaml, warnings, now=now_override))
        errors.extend(check_question_quality_records(
            yaml, now=now_override, snapshot_clock_explicit=now_override is not None
        ))
        errors.extend(check_stale_practice_overrides(yaml))
    else:
        print("\nNote: PyYAML not installed. Skipping state-aware checks.")
        print("      Install with: pip install pyyaml")

    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  - {warn}")

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")
        print("\nValidation failed.")
        return 1

    print("\nAll required files present.")
    print("YAML validation passed.")
    print("No forbidden mentions found.")
    print("StudyState state looks healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
