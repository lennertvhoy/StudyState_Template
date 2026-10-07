#!/usr/bin/env python3
"""Tests for the template/instance boundary hardening.

Validates that:
- every tracked file in STATE_MANIFEST.yaml has a valid boundary value;
- the real template repo has no boundary-violation warnings;
- a learner instance created via create_instance.py can populate instance files and
  still pass validation.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_BOUNDARIES = {"template", "instance", "generated"}


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


def test_manifest_has_boundary_for_every_file() -> None:
    manifest = load_yaml(ROOT / "state" / "STATE_MANIFEST.yaml")
    files = manifest.get("files") or {}
    assert files, "state/STATE_MANIFEST.yaml has no 'files' mapping"

    missing: list[str] = []
    invalid: list[tuple[str, object]] = []
    for rel, meta in files.items():
        boundary = meta.get("boundary") if isinstance(meta, dict) else None
        if boundary is None:
            missing.append(rel)
        elif boundary not in ALLOWED_BOUNDARIES:
            invalid.append((rel, boundary))

    assert not missing, f"Missing boundary field: {missing}"
    assert not invalid, f"Invalid boundary value(s): {invalid}"


def test_template_mode_instance_files_are_generic() -> None:
    result = run([sys.executable, "scripts/check_studydd.py"], cwd=ROOT, check=False)
    assert result.returncode == 0, (
        f"Validator failed in template mode:\n{result.stdout}\n{result.stderr}"
    )
    assert "Template boundary violation:" not in result.stdout, (
        "Template repo contains boundary violations"
    )


def test_instance_mode_can_populate_instance_files() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-boundary-") as tmp:
        target = Path(tmp) / "Study_BoundaryTest"
        remote = "https://github.com/example/Study_BoundaryTest.git"
        run(
            [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", remote]
        )

        # Switch to learner_instance mode.
        mode_path = target / "state" / "STUDYDD_MODE.yaml"
        mode_data = load_yaml(mode_path)
        mode_data["mode"] = "learner_instance"
        mode_data["personalized"] = True
        mode_data["public_safe"] = "false_or_review_required"
        save_yaml(mode_path, mode_data)

        # Populate instance-boundary state files.
        study_state = load_yaml(target / "state" / "STUDY_STATE.yaml")
        study_state["learner"]["name"] = "Boundary Test Learner"
        study_state["active_target_id"] = "boundary-target"
        save_yaml(target / "state" / "STUDY_STATE.yaml", study_state)

        (target / "targets" / "boundary-target").mkdir(parents=True, exist_ok=True)
        (target / "targets" / "boundary-target" / "TARGET.yaml").write_text(
            "---\nid: boundary-target\ntype: skill\ntitle: Boundary target\n",
            encoding="utf-8",
        )

        skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
        skill_map["skills"] = [
            {
                "id": "boundary-skill",
                "label": "Boundary skill",
                "status": "pending",
                "readiness": 0,
                "confidence": "low",
                "evidence": [],
            }
        ]
        save_yaml(target / "state" / "SKILL_MAP.yaml", skill_map)

        profile = load_yaml(target / "state" / "LEARNER_PROFILE.yaml")
        profile["adaptation_state"]["methods_tried"] = ["spaced_repetition"]
        save_yaml(target / "state" / "LEARNER_PROFILE.yaml", profile)

        save_yaml(
            target / "sources" / "SOURCE_STATE.yaml",
            {
                "metadata": {
                    "template_version": "0.9.0",
                    "last_updated": "2026-06-29",
                    "updated_by": "test",
                },
                "sources": [
                    {
                        "id": "boundary-source",
                        "authority": "official",
                        "target_ids": ["boundary-target"],
                        "volatility": "stable",
                        "usable_for_questions": True,
                        "last_checked_at": "2026-06-29T08:00:00+00:00",
                    }
                ],
            },
        )

        activity_state = load_yaml(target / "state" / "ACTIVITY_STATE.yaml")
        activity_state["active_activity"] = {
            "id": "act_boundary_001",
            "type": "retrieval_question",
            "target_id": "boundary-target",
            "skill_id": "boundary-skill",
            "assigned_at": "2026-06-29T08:00:00+00:00",
            "due_at": "",
            "status": "proposed",
            "reason": "Test activity.",
            "expected_evidence": ["typed_answer"],
            "learner_override_allowed": True,
        }
        save_yaml(target / "state" / "ACTIVITY_STATE.yaml", activity_state)

        # The instance should now validate cleanly.
        result = run([sys.executable, "scripts/check_studydd.py"], cwd=target, check=False)
        assert result.returncode == 0, (
            f"Validator failed after populating instance files:\n{result.stdout}\n{result.stderr}"
        )


def main() -> int:
    tests = [
        test_manifest_has_boundary_for_every_file,
        test_template_mode_instance_files_are_generic,
        test_instance_mode_can_populate_instance_files,
    ]

    failed: list[tuple[str, Exception]] = []
    for test in tests:
        print(f"Running {test.__name__}...")
        try:
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

    print("\nAll template/instance boundary tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
