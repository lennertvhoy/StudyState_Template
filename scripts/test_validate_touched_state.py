#!/usr/bin/env python3
"""Test StudyState targeted (fast-path) validator.

Creates a temporary learner instance, adds a skill/evidence/review, and checks
that validate_touched_state.py passes for valid IDs and fails for broken
references.
"""

from __future__ import annotations

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


def build_instance() -> Path:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    tmp = tempfile.mkdtemp(prefix="studydd-tv-")
    target = Path(tmp) / "Study_TV"
    remote = "https://github.com/example/Study_TV.git"

    result = run(
        [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote],
        ROOT,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    mode_path = target / "state" / "STUDYDD_MODE.yaml"
    mode_data = yaml.safe_load(mode_path.read_text(encoding="utf-8")) or {}
    mode_data["mode"] = "learner_instance"
    mode_data["personalized"] = True
    mode_data["public_safe"] = "false_or_review_required"
    mode_path.write_text(yaml.safe_dump(mode_data, sort_keys=False), encoding="utf-8")

    study_state_path = target / "state" / "STUDY_STATE.yaml"
    study_state = yaml.safe_load(study_state_path.read_text(encoding="utf-8")) or {}
    study_state["learner"]["name"] = "TV Test Learner"
    study_state["active_target_id"] = "tv-target"
    study_state["active_focus"]["next_question"] = "Q-TV-001"
    study_state_path.write_text(yaml.safe_dump(study_state, sort_keys=False), encoding="utf-8")

    target_dir = target / "targets" / "tv-target"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "TARGET.yaml").write_text(
        "---\n"
        "id: tv-target\n"
        "type: skill\n"
        "title: Targeted validator test target\n"
        "description: Temporary target for targeted validator test.\n",
        encoding="utf-8",
    )

    skill_map_path = target / "state" / "SKILL_MAP.yaml"
    skill_map = yaml.safe_load(skill_map_path.read_text(encoding="utf-8")) or {}
    skill_map["skills"] = [
        {
            "id": "tv-search-basics",
            "label": "Keyword vs vector search",
            "status": "weak",
            "readiness": 35,
            "confidence": "low",
            "evidence": ["ev_tv_001"],
            "next_validation_question": "Q-TV-001",
        },
    ]
    skill_map_path.write_text(yaml.safe_dump(skill_map, sort_keys=False), encoding="utf-8")

    evidence_path = target / "state" / "EVIDENCE_LOG.md"
    evidence_text = evidence_path.read_text(encoding="utf-8")
    evidence_entry = (
        "\n- **Evidence ID:** ev_tv_001\n"
        "- **Date:** 2026-06-24\n"
        "- **Target ID:** tv-target\n"
        "- **Skill ID:** tv-search-basics\n"
        "- **Question ID:** Q-TV-001\n"
        "- **Question summary:** Explain keyword vs vector search.\n"
        "- **Learner answer summary:** Partial answer.\n"
        "- **Verdict:** partial\n"
        "- **Explanation:** Missing scenario.\n"
        "- **Confidence:** low\n"
    )
    evidence_path.write_text(evidence_text + evidence_entry, encoding="utf-8")

    review_state_path = target / "reviews" / "REVIEW_STATE.yaml"
    review_state = yaml.safe_load(review_state_path.read_text(encoding="utf-8")) or {}
    review_state["review_items"] = [
        {
            "id": "rev_tv_001",
            "skill_id": "tv-search-basics",
            "evidence_id": "ev_tv_001",
            "target_id": "tv-target",
            "due_at": "2026-06-25T09:00:00+00:00",
            "last_reviewed_at": None,
            "interval_days": 1,
            "stability": None,
            "difficulty": None,
            "lapses": 0,
            "priority": "normal",
            "status": "scheduled",
            "source": "partial_answer",
            "override_count": 0,
        }
    ]
    review_state_path.write_text(yaml.safe_dump(review_state, sort_keys=False), encoding="utf-8")

    next_path = target / "NEXT_ACTIONS.md"
    next_path.write_text(
        "# NEXT_ACTIONS\n\n## Current next action\n\nAnswer Q-TV-001.\n",
        encoding="utf-8",
    )

    return target


def main() -> int:
    print("StudyState targeted validator test")
    print("===============================")

    target = build_instance()
    run([sys.executable, "scripts/compact_state.py"], target)

    print("\nTest: valid skill passes")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--skill-id", "tv-search-basics"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return 1
    assert "Targeted validation passed" in result.stdout

    print("\nTest: valid evidence passes")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--evidence-id", "ev_tv_001"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return 1
    assert "Targeted validation passed" in result.stdout

    print("\nTest: valid review passes")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--review-id", "rev_tv_001"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return 1
    assert "Targeted validation passed" in result.stdout

    print("\nTest: active question consistency passes")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--active-question", "Q-TV-001"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        return 1
    assert "Targeted validation passed" in result.stdout

    print("\nTest: unknown skill fails")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--skill-id", "nonexistent-skill"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode == 0:
        print("Expected validation failure for unknown skill")
        return 1
    assert "not found" in result.stdout

    print("\nTest: evidence appended after compaction validates from the audit log")
    evidence_log = target / "state" / "EVIDENCE_LOG.md"
    evidence_log.write_text(
        evidence_log.read_text(encoding="utf-8")
        + "\n- **Date:** 2026-06-25\n- **Target ID:** tv-target\n- **Skill ID:** tv-search-basics\n"
        "- **Evidence ID:** ev_tv_fresh\n- **Question ID:** Q-TV-002\n- **Verdict:** partial\n- **Confidence:** low\n",
        encoding="utf-8",
    )
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--evidence-id", "ev_tv_fresh"],
        target,
        check=False,
    )
    print(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "not yet in the index" in result.stdout, "the fallback says the index is stale"

    print("\nTest: unknown evidence fails")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--evidence-id", "ev_missing"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode == 0:
        print("Expected validation failure for unknown evidence")
        return 1
    assert "not found" in result.stdout

    print("\nTest: unknown review fails")
    result = run(
        [sys.executable, "scripts/validate_touched_state.py", "--review-id", "rev_missing"],
        target,
        check=False,
    )
    print(result.stdout)
    if result.returncode == 0:
        print("Expected validation failure for unknown review")
        return 1
    assert "not found" in result.stdout

    print("\nTest: full validator still passes")
    val = run([sys.executable, "scripts/check_studydd.py"], target, check=False)
    print(val.stdout)
    if val.returncode != 0:
        print(val.stderr)
        return 1

    print("Targeted validator test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
