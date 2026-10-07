#!/usr/bin/env python3
"""Tests for scripts/lint_questions.py.

Creates temporary question banks, SOURCE_STATE.yaml fixtures, and StudyState mode
files, then invokes the linter via subprocess. No network calls are made.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_SRC = ROOT / "scripts" / "lint_questions.py"


def run_script(tmp_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Copy the linter and its local dependencies into tmp_root."""
    script_dst = tmp_root / "scripts" / "lint_questions.py"
    script_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT_SRC, script_dst)
    shutil.copy(
        ROOT / "scripts" / "check_source_freshness.py",
        script_dst.parent / "check_source_freshness.py",
    )
    return subprocess.run(
        [sys.executable, str(script_dst), *args],
        cwd=tmp_root,
        capture_output=True,
        text=True,
        check=False,
    )


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def write_question(
    tmp_root: Path,
    target_id: str,
    qid: str,
    overrides: dict[str, Any],
    example: bool = False,
) -> Path:
    if example:
        question_dir = (
            tmp_root / "EXAMPLES" / "demo" / "targets" / target_id / "questions"
        )
    else:
        question_dir = tmp_root / "targets" / target_id / "questions"
    question_dir.mkdir(parents=True, exist_ok=True)
    path = question_dir / f"{qid}.yaml"

    base: dict[str, Any] = {
        "id": qid,
        "target_id": target_id,
        "skill_id": f"{target_id}-skill",
        "cognitive_level": "explain",
        "difficulty": 2,
        "public_prompt": "What is the question?",
        "private_answer_key": "The correct answer is 42.",
        "rubric": [" Mentions 42"],
        "common_traps": ["Saying 43"],
        "last_used": "2026-06-24",
        "cooldown_days": 7,
    }
    base.update(overrides)
    write_yaml(path, base)
    return path


def write_target(tmp_root: Path, target_id: str, volatility: str | None = None) -> None:
    target_dir = tmp_root / "targets" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "id": target_id,
        "type": "skill",
        "title": f"Test target {target_id}",
    }
    if volatility:
        data["volatility"] = volatility
    write_yaml(target_dir / "TARGET.yaml", data)


def write_source_state(tmp_root: Path, sources: list[dict[str, Any]]) -> None:
    write_yaml(
        tmp_root / "sources" / "SOURCE_STATE.yaml",
        {"metadata": {"template_version": "0.8.1"}, "sources": sources},
    )


def write_mode(tmp_root: Path, mode: str) -> None:
    write_yaml(
        tmp_root / "state" / "STUDYDD_MODE.yaml",
        {"mode": mode, "public_safe": mode == "template", "personalized": False},
    )


def test_volatile_no_source_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "volatile-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-001",
            {
                "question_mode": "authoritative_current",
                "source_ids": [],
            },
        )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_volatile_no_source_fails stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "Q-001: fail" in result.stdout
        assert "authoritative_current volatile/live question has no source_ids" in result.stdout


def test_answer_key_leakage_caught() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "leak-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id)
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-002",
            {
                "public_prompt": "What is the secret phrase?",
                "private_answer_key": "The secret phrase is open sesame.",
            },
        )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_answer_key_leakage_caught stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "Q-002: fail" in result.stdout
        assert "private answer key text appears in public_prompt" in result.stdout


def test_legacy_source_ref_warns_for_volatile() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "legacy-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-003",
            {
                "source_ref": "old-blog-post",
                "source_ids": [],
            },
        )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_legacy_source_ref_warns_for_volatile stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Q-003: warn" in result.stdout
        assert "uses legacy source_ref only" in result.stdout


def test_authoritative_current_stale_source_fails_quality_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "stale-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "old-source",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-05-01T10:00:00+00:00",
                }
            ],
        )
        write_question(
            tmp_root,
            target_id,
            "Q-004",
            {
                "question_mode": "authoritative_current",
                "source_ids": ["old-source"],
            },
        )

        result = run_script(tmp_root, "--target-id", target_id, "--now", "2026-06-24T12:00:00+00:00")
        print("--- test_authoritative_current_stale_source_fails_quality_gate stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "Q-004: fail" in result.stdout
        assert "source 'old-source' is stale" in result.stdout
        assert "set quality_gate: fail" in result.stdout


def test_quality_gate_reason_required_for_warn_fail() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "gate-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id)
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-005",
            {
                "question_quality": {
                    "quality_gate": "warn",
                    "quality_gate_reason": "",
                },
            },
        )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_quality_gate_reason_required_for_warn_fail stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "Q-005: fail" in result.stdout
        assert "quality_gate is 'warn' but quality_gate_reason is missing" in result.stdout


def test_template_mode_does_not_fail_on_missing_learner_bank() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        # Template mode with no targets/ directory at all.
        write_mode(tmp_root, "template")
        write_source_state(tmp_root, [])

        result = run_script(tmp_root)
        print("--- test_template_mode_does_not_fail_on_missing_learner_bank stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Checked: 0 question file(s)" in result.stdout


def test_strict_turns_warnings_into_failures() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "strict-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-006",
            {"source_ref": "legacy", "source_ids": []},
        )

        result = run_script(tmp_root, "--strict", "--target-id", target_id)
        print("--- test_strict_turns_warnings_into_failures stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected exit 0 under --strict, got {result.returncode}"


def test_fresh_source_allows_generated_false_only() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "fresh-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "fresh-source",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-24T10:00:00+00:00",
                }
            ],
        )
        write_question(
            tmp_root,
            target_id,
            "Q-007",
            {
                "question_mode": "authoritative_current",
                "source_ids": ["fresh-source"],
                "generated_from_memory_allowed": True,
            },
        )

        result = run_script(tmp_root, "--target-id", target_id, "--now", "2026-06-24T12:00:00+00:00")
        print("--- test_fresh_source_allows_generated_false_only stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "generated_from_memory_allowed: false" in result.stdout


def test_question_volatility_overrides_target() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "override-target"
        write_mode(tmp_root, "learner_instance")
        # Target says moderate (30 days); question says live (1 day).
        write_target(tmp_root, target_id, volatility="moderate")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "checked-source",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-23T10:00:00+00:00",
                }
            ],
        )
        write_question(
            tmp_root,
            target_id,
            "Q-008",
            {
                "question_mode": "authoritative_current",
                "source_ids": ["checked-source"],
                "volatility": "live",
            },
        )

        result = run_script(tmp_root, "--target-id", target_id, "--now", "2026-06-24T12:00:00+00:00")
        print("--- test_question_volatility_overrides_target stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "Q-008: fail" in result.stdout
        assert "source 'checked-source' is stale" in result.stdout


def test_skill_question_balance_warns_on_recall_only() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "recall-heavy-target"
        skill_id = f"{target_id}-skill"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="stable")
        write_source_state(tmp_root, [])
        for i in range(3):
            write_question(
                tmp_root,
                target_id,
                f"Q-RECALL-{i:03d}",
                {
                    "cognitive_level": "recall",
                    "skill_id": skill_id,
                    "public_prompt": f"Recall question {i}?",
                    "private_answer_key": "Answer.",
                },
            )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_skill_question_balance_warns_on_recall_only stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "recall-only questions and no application/transfer questions" in result.stdout


def test_option_position_bias_warns() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "position-bias-target"
        skill_id = f"{target_id}-skill"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="stable")
        write_source_state(tmp_root, [])
        for i in range(2):
            write_question(
                tmp_root,
                target_id,
                f"Q-POS-{i:03d}",
                {
                    "cognitive_level": "choose-best",
                    "skill_id": skill_id,
                    "public_prompt": f"Choose the best option {i}?",
                    "options": ["Alpha", "Beta", "Gamma", "Delta"],
                    "correct_label": "A",
                    "private_answer_key": "Alpha",
                },
            )

        result = run_script(tmp_root, "--target-id", target_id)
        print("--- test_option_position_bias_warns stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "correct option is always in position 1" in result.stdout


def test_discovers_example_target_questions() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "example-target"
        write_mode(tmp_root, "template")
        # No targets/ dir; question lives under EXAMPLES/demo/targets/.
        write_source_state(tmp_root, [])
        write_question(
            tmp_root,
            target_id,
            "Q-EXAMPLE-001",
            {"cognitive_level": "explain", "volatility": "stable"},
            example=True,
        )

        result = run_script(tmp_root)
        print("--- test_discovers_example_target_questions stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Q-EXAMPLE-001: pass" in result.stdout


def test_generated_from_memory_false_with_fresh_source_passes() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-lint-") as tmp:
        tmp_root = Path(tmp)
        target_id = "fresh-ok-target"
        write_mode(tmp_root, "learner_instance")
        write_target(tmp_root, target_id, volatility="volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "fresh-source",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-24T10:00:00+00:00",
                }
            ],
        )
        write_question(
            tmp_root,
            target_id,
            "Q-009",
            {
                "question_mode": "authoritative_current",
                "source_ids": ["fresh-source"],
                "generated_from_memory_allowed": False,
            },
        )

        result = run_script(tmp_root, "--target-id", target_id, "--now", "2026-06-24T12:00:00+00:00")
        print("--- test_generated_from_memory_false_with_fresh_source_passes stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Q-009: pass" in result.stdout


def main() -> int:
    tests = [
        test_volatile_no_source_fails,
        test_answer_key_leakage_caught,
        test_legacy_source_ref_warns_for_volatile,
        test_authoritative_current_stale_source_fails_quality_gate,
        test_quality_gate_reason_required_for_warn_fail,
        test_template_mode_does_not_fail_on_missing_learner_bank,
        test_strict_turns_warnings_into_failures,
        test_fresh_source_allows_generated_false_only,
        test_question_volatility_overrides_target,
        test_skill_question_balance_warns_on_recall_only,
        test_option_position_bias_warns,
        test_discovers_example_target_questions,
        test_generated_from_memory_false_with_fresh_source_passes,
    ]

    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  PASSED")
        except AssertionError as exc:
            print(f"  FAILED: {exc}")
            failures += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            failures += 1

    if failures:
        print(f"\n{failures} test(s) failed.")
        return 1

    print("\nAll question quality tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
