"""Small helpers shared by StudyState's scenario tests.

Not a test module (the runner only collects ``test_*.py``). Tests that need a
real learner instance call :func:`make_learner_instance`, which runs the actual
``create_instance.py`` and then moves the copy to ``learner_instance`` mode with
one skill and one evidence entry, the minimum the validators need.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SKILL_ID = "kit-skill"
TARGET_ID = "kit-target"
EVIDENCE_ID = "ev_kit_001"


def tempdir(prefix: str = "studystate-test-") -> tempfile.TemporaryDirectory:
    """A temporary directory that tolerates what git leaves behind.

    Git writes read-only object files; on Windows deleting them fails unless errors are
    ignored. A leftover temporary directory is harmless, a failed test is not.
    """
    return tempfile.TemporaryDirectory(prefix=prefix, ignore_cleanup_errors=True)


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(map(str, cmd))}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def script(name: str, *args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``scripts/<name>`` inside ``cwd`` with the current interpreter."""
    return run([sys.executable, f"scripts/{name}", *args], cwd=cwd, check=check)


def load_yaml(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# Throwaway repositories must be quiet: git's detached auto-maintenance can still be
# writing into .git when a temporary directory is deleted, which fails the cleanup.
GIT_QUIET = ["-c", "maintenance.auto=false", "-c", "gc.auto=0", "-c", "gc.autoDetach=false"]


def git(cwd: Path, *args: str) -> str:
    return run(
        ["git", "-c", "user.name=Kit", "-c", "user.email=kit@example.invalid", *GIT_QUIET, *args], cwd=cwd
    ).stdout


def commit_all(path: Path, message: str = "kit commit") -> None:
    """Initialize Git in ``path`` if needed and commit everything."""
    if not (path / ".git").exists():
        git(path, "init", "-q", "-b", "main")
    git(path, "add", "-A")
    git(path, "commit", "-q", "--allow-empty", "-m", message)


def copy_template(parent: Path, name: str = "StudyState_Template") -> Path:
    """A throwaway copy of the template that a test may change freely.

    Copies exactly the files the real template ships (tracked or untracked and
    not ignored), gives the copy a template-looking remote, and commits it so
    ``git ls-files`` and ``git rev-parse HEAD`` behave as in the real repository.
    """
    target = parent / name
    for rel in own.template_files(ROOT):
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, destination)
        destination.chmod((ROOT / rel).stat().st_mode & 0o777)
    git(target, "init", "-q", "-b", "main")
    git(target, "remote", "add", "origin", "https://example.invalid/StudyState_Template.git")
    commit_all(target, "template copy")
    return target


def make_learner_instance(parent: Path, name: str = "Study_Kit", template: Path = ROOT) -> Path:
    """Create a validated learner instance under ``parent`` and return its path."""
    target = parent / name
    run(
        [
            sys.executable,
            str(template / "scripts" / "create_instance.py"),
            "--target",
            str(target),
            "--remote",
            f"https://example.invalid/{name}.git",
        ],
        cwd=template,
    )

    mode = load_yaml(target / "state" / "STUDYDD_MODE.yaml")
    mode.update({"mode": "learner_instance", "personalized": True, "public_safe": "false_or_review_required"})
    save_yaml(target / "state" / "STUDYDD_MODE.yaml", mode)

    state = load_yaml(target / "state" / "STUDY_STATE.yaml")
    state["learner"]["name"] = "Kit Learner"
    state["active_target_id"] = TARGET_ID
    save_yaml(target / "state" / "STUDY_STATE.yaml", state)

    target_dir = target / "targets" / TARGET_ID
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "TARGET.yaml").write_text(
        f"---\nid: {TARGET_ID}\ntype: skill\ntitle: Kit target\ndescription: Temporary test target.\n",
        encoding="utf-8",
    )

    skill_map = load_yaml(target / "state" / "SKILL_MAP.yaml")
    skill_map["skills"] = [
        {
            "id": SKILL_ID,
            "label": "Kit skill",
            "status": "weak",
            "readiness": 20,
            "confidence": "low",
            "evidence": [EVIDENCE_ID],
        }
    ]
    save_yaml(target / "state" / "SKILL_MAP.yaml", skill_map)

    evidence = target / "state" / "EVIDENCE_LOG.md"
    evidence.write_text(
        evidence.read_text(encoding="utf-8")
        + f"\n- **Date:** 2026-10-07\n- **Target ID:** {TARGET_ID}\n- **Skill ID:** {SKILL_ID}\n"
        f"- **Question ID:** Q-KIT-001\n- **Evidence ID:** {EVIDENCE_ID}\n"
        "- **Question summary:** Kit question.\n- **Learner answer summary:** Partly right.\n"
        "- **Verdict:** partial\n- **Explanation:** Test fixture.\n- **Confidence:** low\n",
        encoding="utf-8",
    )
    return target
