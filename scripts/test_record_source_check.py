#!/usr/bin/env python3
"""Tests for scripts/record_source_check.py.

Creates temporary learner instances and invokes the source-check recording
script via subprocess. Verifies template-mode write refusal, dry-run/demo
behavior, learner-instance updates, idempotency, stale-outcome semantics,
validation, and integration with the next-activity decision loop.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_NAME = "scripts/record_source_check.py"

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


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

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def create_temp_instance(tmp: str, name: str, target_id: str, target_yaml: str) -> Path:
    target = Path(tmp) / f"Study_{name}"
    remote = f"https://github.com/example/Study_{name}.git"
    subprocess.run(
        [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    mode_path = target / "state" / "STUDYDD_MODE.yaml"
    mode_data = load_yaml(mode_path)
    mode_data["mode"] = "learner_instance"
    mode_data["personalized"] = True
    mode_data["public_safe"] = "false_or_review_required"
    save_yaml(mode_path, mode_data)

    study_state = load_yaml(target / "state" / "STUDY_STATE.yaml")
    study_state["learner"]["name"] = f"{name} Test Learner"
    study_state["active_target_id"] = target_id
    save_yaml(target / "state" / "STUDY_STATE.yaml", study_state)

    (target / "targets" / target_id).mkdir(parents=True, exist_ok=True)
    (target / "targets" / target_id / "TARGET.yaml").write_text(target_yaml, encoding="utf-8")

    return target


def run_script(instance: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, SCRIPT_NAME, *args],
        cwd=instance,
        capture_output=True,
        text=True,
        check=False,
    )


def source_state(instance: Path) -> dict:
    return load_yaml(instance / "sources" / "SOURCE_STATE.yaml")


def _template_source_state() -> dict:
    return load_yaml(ROOT / "sources" / "SOURCE_STATE.yaml")


def _source_ids(state: dict) -> list[str]:
    return [s.get("id") for s in state.get("sources", []) if s.get("id")]


def test_template_mode_refuses_write() -> None:
    before = _template_source_state()
    result = run_script(
        ROOT,
        "template-test-source",
        "--target-id",
        "template-test-target",
        "--outcome",
        "fresh",
        "--summary",
        "should not be recorded",
    )
    assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
    after = _template_source_state()
    assert after == before, "Template SOURCE_STATE.yaml must not change"
    assert "learner_instance" in (result.stdout + result.stderr).lower()


def test_demo_runs_in_template_mode_without_writing() -> None:
    before = _template_source_state()
    result = run_script(ROOT, "demo-source", "--demo")
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    after = _template_source_state()
    assert after == before, "Demo must not write SOURCE_STATE.yaml"
    assert "demo" in result.stdout.lower() or "example" in result.stdout.lower()


def test_dry_run_does_not_write() -> None:
    before = _template_source_state()
    result = run_script(
        ROOT,
        "dry-run-source",
        "--target-id",
        "dry-run-target",
        "--outcome",
        "fresh",
        "--summary",
        "dry run summary",
        "--dry-run",
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
    after = _template_source_state()
    assert after == before, "Dry run must not write SOURCE_STATE.yaml"
    assert "dry-run" in (result.stdout + result.stderr).lower() or "would" in result.stdout.lower()


def test_learner_instance_updates_existing_source_and_bumps_last_checked() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-update-") as tmp:
        target_yaml = "---\nid: update-target\ntype: certification\ntitle: Update target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceUpdate", "update-target", target_yaml)

        old_checked = "2026-06-01T10:00:00+00:00"
        save_yaml(
            target / "sources" / "SOURCE_STATE.yaml",
            {
                "metadata": {"template_version": "0.9.0", "last_updated": "2026-06-01", "updated_by": "test"},
                "sources": [
                    {
                        "id": "existing-source",
                        "authority": "official",
                        "target_ids": ["update-target"],
                        "volatility": "volatile",
                        "usable_for_questions": True,
                        "last_checked_at": old_checked,
                    }
                ],
            },
        )

        new_checked = "2026-06-27T10:00:00+00:00"
        result = run_script(
            target,
            "existing-source",
            "--outcome",
            "fresh",
            "--checked-at",
            new_checked,
            "--summary",
            "Re-checked official docs",
            "--evidence-id",
            "ev_src_001",
            "--activity-id",
            "act_src_001",
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"

        state = source_state(target)
        source = state["sources"][0]
        assert source["last_checked_at"] == new_checked
        assert source["last_check"]["outcome"] == "fresh"
        assert source["last_check"]["checked_at"] == new_checked
        assert source["last_check"]["summary"] == "Re-checked official docs"
        assert source["last_check"]["evidence_id"] == "ev_src_001"
        assert source["last_check"]["activity_id"] == "act_src_001"
        assert state["metadata"]["updated_by"] == "record_source_check.py"
        assert "last_updated" in state["metadata"]


def test_learner_instance_creates_source_when_target_id_given() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-create-") as tmp:
        target_yaml = "---\nid: create-target\ntype: certification\ntitle: Create target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceCreate", "create-target", target_yaml)

        checked_at = "2026-06-27T10:00:00+00:00"
        result = run_script(
            target,
            "new-source",
            "--target-id",
            "create-target",
            "--outcome",
            "fresh",
            "--authority",
            "official",
            "--volatility",
            "volatile",
            "--checked-at",
            checked_at,
            "--summary",
            "Initial source check",
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"

        state = source_state(target)
        assert len(state["sources"]) == 1
        source = state["sources"][0]
        assert source["id"] == "new-source"
        assert source["target_ids"] == ["create-target"]
        assert source["authority"] == "official"
        assert source["volatility"] == "volatile"
        assert source["last_checked_at"] == checked_at
        assert source["last_check"]["outcome"] == "fresh"


def test_idempotent_update_by_source_id() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-idempotent-") as tmp:
        target_yaml = "---\nid: idempotent-target\ntype: certification\ntitle: Idempotent target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceIdempotent", "idempotent-target", target_yaml)

        save_yaml(
            target / "sources" / "SOURCE_STATE.yaml",
            {
                "metadata": {"template_version": "0.9.0"},
                "sources": [
                    {
                        "id": "shared-source",
                        "authority": "official",
                        "target_ids": ["idempotent-target"],
                        "volatility": "volatile",
                        "usable_for_questions": True,
                        "last_checked_at": "2026-06-01T10:00:00+00:00",
                    }
                ],
            },
        )

        run_script(target, "shared-source", "--outcome", "fresh", "--summary", "First update")
        run_script(target, "shared-source", "--outcome", "fresh", "--summary", "Second update")

        state = source_state(target)
        assert _source_ids(state) == ["shared-source"]
        assert state["sources"][0]["last_check"]["summary"] == "Second update"


def test_stale_outcome_records_last_check_but_does_not_bump_last_checked_at() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-stale-") as tmp:
        target_yaml = "---\nid: stale-target\ntype: certification\ntitle: Stale target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceStale", "stale-target", target_yaml)

        old_checked = "2026-06-01T10:00:00+00:00"
        save_yaml(
            target / "sources" / "SOURCE_STATE.yaml",
            {
                "metadata": {"template_version": "0.9.0"},
                "sources": [
                    {
                        "id": "stale-source",
                        "authority": "official",
                        "target_ids": ["stale-target"],
                        "volatility": "volatile",
                        "usable_for_questions": True,
                        "last_checked_at": old_checked,
                    }
                ],
            },
        )

        new_checked = "2026-06-27T10:00:00+00:00"
        result = run_script(
            target,
            "stale-source",
            "--outcome",
            "stale",
            "--checked-at",
            new_checked,
            "--summary",
            "Official docs are now stale",
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"

        state = source_state(target)
        source = state["sources"][0]
        assert source["last_checked_at"] == old_checked, "Stale outcome must not bump last_checked_at"
        assert source["last_check"]["outcome"] == "stale"
        assert source["last_check"]["checked_at"] == new_checked


def test_missing_source_without_target_id_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-missing-") as tmp:
        target_yaml = "---\nid: missing-target\ntype: certification\ntitle: Missing target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceMissing", "missing-target", target_yaml)

        result = run_script(target, "unknown-source", "--outcome", "fresh")
        assert result.returncode == 3, f"Expected exit 3, got {result.returncode}"


def test_invalid_timestamp_rejected_without_corrupting_yaml() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-invalid-") as tmp:
        target_yaml = "---\nid: invalid-target\ntype: certification\ntitle: Invalid target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceInvalid", "invalid-target", target_yaml)

        before = {
            "metadata": {"template_version": "0.9.0"},
            "sources": [
                {
                    "id": "invalid-source",
                    "authority": "official",
                    "target_ids": ["invalid-target"],
                    "volatility": "volatile",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-01T10:00:00+00:00",
                }
            ],
        }
        save_yaml(target / "sources" / "SOURCE_STATE.yaml", before)

        result = run_script(
            target,
            "invalid-source",
            "--outcome",
            "fresh",
            "--checked-at",
            "not-a-timestamp",
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"
        after = source_state(target)
        assert after == before, "Invalid input must not corrupt SOURCE_STATE.yaml"


def test_invalid_enum_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-enum-") as tmp:
        target_yaml = "---\nid: enum-target\ntype: certification\ntitle: Enum target\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceEnum", "enum-target", target_yaml)

        result = run_script(
            target,
            "enum-source",
            "--target-id",
            "enum-target",
            "--outcome",
            "questionable",
        )
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"


def recent_checked_at() -> str:
    """An hour ago: these tests evaluate freshness on the real clock, so a fixed date would age out."""
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def test_fresh_source_check_suppresses_recent_info_check() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-integration-") as tmp:
        target_yaml = "---\nid: volatile-integration\ntype: certification\ntitle: Volatile Integration Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceIntegration", "volatile-integration", target_yaml)

        before = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target, check=False)
        assert before.returncode == 0, before.stderr
        assert "recent_info_check" in before.stdout, "Volatile target with no source state should route to recent_info_check"

        checked_at = recent_checked_at()
        result = run_script(
            target,
            "fresh-integration-source",
            "--target-id",
            "volatile-integration",
            "--outcome",
            "fresh",
            "--authority",
            "official",
            "--volatility",
            "volatile",
            "--checked-at",
            checked_at,
            "--summary",
            "Official docs verified",
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"

        after = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target, check=False)
        assert after.returncode == 0, after.stderr
        assert "recent_info_check" not in after.stdout, "Fresh source should suppress recent_info_check"
        assert "Source freshness: fresh" in after.stdout


def test_stable_target_does_not_require_source_check() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-stable-") as tmp:
        target_yaml = "---\nid: stable-target\ntype: certification\ntitle: Stable Cert\nvolatility: stable\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourceStable", "stable-target", target_yaml)

        result = run([sys.executable, "scripts/plan_learning_activity.py"], cwd=target, check=False)
        assert result.returncode == 0, result.stderr
        assert "recent_info_check" not in result.stdout, "Stable target should not require source check"


def test_context_pack_reflects_recorded_fresh_source_state() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-src-pack-") as tmp:
        target_yaml = "---\nid: pack-target\ntype: certification\ntitle: Pack Cert\nvolatility: volatile\nstudy_skill: it_certification\n"
        target = create_temp_instance(tmp, "SourcePack", "pack-target", target_yaml)

        run_script(
            target,
            "fresh-pack-source",
            "--target-id",
            "pack-target",
            "--outcome",
            "fresh",
            "--authority",
            "official",
            "--volatility",
            "volatile",
            "--checked-at",
            recent_checked_at(),
            "--summary",
            "Official docs verified for pack test",
        )

        run([sys.executable, "scripts/compact_state.py"], cwd=target)
        result = run(
            [sys.executable, "scripts/build_context_pack.py", "--task", "start_session"],
            cwd=target,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        text = (target / ".studydd" / "context_pack.md").read_text(encoding="utf-8")
        assert "**Recommended activity:** recent_info_check" not in text
        assert "Source freshness:" in text
        assert "Status: fresh" in text


def main() -> int:
    tests = [
        test_template_mode_refuses_write,
        test_demo_runs_in_template_mode_without_writing,
        test_dry_run_does_not_write,
        test_learner_instance_updates_existing_source_and_bumps_last_checked,
        test_learner_instance_creates_source_when_target_id_given,
        test_idempotent_update_by_source_id,
        test_stale_outcome_records_last_check_but_does_not_bump_last_checked_at,
        test_missing_source_without_target_id_fails,
        test_invalid_timestamp_rejected_without_corrupting_yaml,
        test_invalid_enum_rejected,
        test_fresh_source_check_suppresses_recent_info_check,
        test_stable_target_does_not_require_source_check,
        test_context_pack_reflects_recorded_fresh_source_state,
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

    print("\nAll record_source_check tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
