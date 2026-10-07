#!/usr/bin/env python3
"""Tests for scripts/template_release.py and the ownership guard in create_instance.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402
import testkit  # noqa: E402

ROOT = testkit.ROOT


def release(root: Path, command: str):
    return testkit.script("template_release.py", command, cwd=root, check=False)


def test_the_real_template_passes_its_own_check() -> None:
    result = release(ROOT, "check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_an_unclassified_file_is_reported_and_blocks_instance_creation() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        (copy / "stray-notes.txt").write_text("scratch", encoding="utf-8")
        result = release(copy, "check")
        assert result.returncode == 1 and "stray-notes.txt" in result.stdout

        created = testkit.script(
            "create_instance.py", "--target", str(Path(tmp) / "Study_Stray"), "--remote", "https://example.invalid/s.git",
            cwd=copy, check=False,
        )
        assert created.returncode == 1 and "stray-notes.txt" in created.stdout
        assert not (Path(tmp) / "Study_Stray").exists(), "nothing is created when ownership is unclear"


def test_block_drift_is_caught_and_sync_repairs_it() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        core = copy / own.CORE_BLOCK_PATH
        core.write_text(core.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8")
        result = release(copy, "check")
        assert result.returncode == 1 and "differs from core/AGENTS.studystate.md" in result.stdout

        assert release(copy, "sync").returncode == 0
        assert "A new rule." in (copy / own.AGENTS_PATH).read_text(encoding="utf-8")
        again = release(copy, "check")
        assert again.returncode == 0, again.stdout
        assert "already matches" in release(copy, "sync").stdout, "sync is idempotent"


def test_sync_changes_only_the_block() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        before = (copy / own.AGENTS_PATH).read_text(encoding="utf-8")
        block = own.find_block(before)
        core = copy / own.CORE_BLOCK_PATH
        core.write_text(core.read_text(encoding="utf-8") + "\nAnother rule.\n", encoding="utf-8")
        release(copy, "sync")
        after = (copy / own.AGENTS_PATH).read_text(encoding="utf-8")
        assert after[: block.start] == before[: block.start], "the ProjectState block and frontmatter are untouched"
        assert after[after.index(own.BLOCK_END):] == before[before.index(own.BLOCK_END):], "local text is untouched"


def test_version_without_changelog_or_marker_is_caught() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        version = copy / own.VERSION_PATH
        version.write_text(re.sub(r'^template_version: ".*"$', 'template_version: "9.9.9"', version.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
        result = release(copy, "check")
        assert result.returncode == 1
        assert "release 0." in result.stdout and "template_version is 9.9.9" in result.stdout
        assert "no '## 9.9.9' entry" in result.stdout


def test_missing_instance_scaffold_is_caught() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        (copy / "core" / "instance" / "PROJECT.md").unlink()
        result = release(copy, "check")
        assert result.returncode == 1 and "core/instance/PROJECT.md is missing" in result.stdout


def test_a_new_instance_gets_instance_files_and_no_maintenance_files() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        for rel in ("CHANGELOG.md", "core", "docs/adr", "scripts/update_instance.py", "scripts/template_release.py", "evidence/template-hardening-001"):
            assert not (inst / rel).exists(), f"{rel} is template-only and must not reach an instance"
        assert "StudyState Template" not in (inst / "PROJECT.md").read_text(encoding="utf-8")
        assert "template-hardening" not in (inst / "STATE.yaml").read_text(encoding="utf-8")
        assert (inst / "evidence" / "bootstrap-001" / "summary.md").is_file()
        assert (inst / "scripts" / "projectstate_gate.py").is_file(), "an instance carries its own gate"
        agents = (inst / "AGENTS.md").read_text(encoding="utf-8")
        assert agents.count("projectstate:managed:start") == 1 and agents.count("studystate:managed:start") == 1
        assert "Read `core/MAINTAINING.md`" not in agents, "template maintenance rules stay out of an instance"
        assert "## Local rules" in agents and "## Owner directives" in agents


def test_a_new_instance_gate_is_honest_and_the_validator_is_green() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        gate = testkit.script("projectstate_gate.py", cwd=inst, check=False)
        assert gate.returncode == 1, "a scaffold cannot honestly be validated"
        assert "WARN" not in gate.stdout, "a fresh instance starts without size warnings: " + gate.stdout
        assert testkit.script("check_studydd.py", cwd=inst, check=False).returncode == 0


def test_an_instances_own_suite_and_ci_are_green_and_self_contained() -> None:
    """Template-scenario tests cast instances from the checkout, so they cannot run inside one."""
    with testkit.tempdir("studystate-release-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        suite = testkit.script("run_tests.py", cwd=inst, check=False)
        assert suite.returncode == 0, "an instance's own test suite must pass in the instance:\n" + suite.stdout[-1500:]
        tests = sorted(p.name for p in (inst / "scripts").glob("test_*.py"))
        assert tests and not any("journey" in t or "update_instance" in t or "release" in t for t in tests), tests

        workflow = (inst / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        for template_only in ("template_release", "test_instance_journey", "clock-offset", "update_instance"):
            assert template_only not in workflow, f"the instance CI must not run template-only step {template_only!r}"
        for name in re.findall(r"scripts/([\w.]+\.py)", workflow):
            assert (inst / "scripts" / name).is_file(), f"the instance CI runs scripts/{name}, which the instance lacks"


def test_every_script_is_in_the_architecture_map() -> None:
    """AGENTS.md promises that docs/architecture.md lists every script; make it true."""
    text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    missing = [p.name for p in sorted((ROOT / "scripts").glob("*.py")) if not p.name.startswith("test_") and p.name not in text]
    assert not missing, f"scripts missing from docs/architecture.md: {missing}"


def test_mode_and_version_files_keep_their_comments() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        target = Path(tmp) / "Study_Comments"
        testkit.run(
            [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", "https://example.invalid/c.git"],
            cwd=ROOT,
        )
        mode = (target / own.MODE_PATH).read_text(encoding="utf-8")
        assert "# StudyState mode lifecycle" in mode, "the lifecycle documentation survives"
        assert "mode: bootstrap" in mode and 'template_origin: "https://github.com/lennertvhoy/StudyState_Template.git"' in mode
        version = (target / own.VERSION_PATH).read_text(encoding="utf-8")
        assert "# StudyState template version tracking." in version
        data = testkit.load_yaml(target / own.VERSION_PATH)
        assert data["instance_created_from_template_version"] == own.template_version(ROOT)


def test_git_identity_is_not_forced_on_the_learner() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        target = Path(tmp) / "Study_Identity"
        testkit.run(
            [sys.executable, "scripts/create_instance.py", "--target", str(target), "--remote", "https://example.invalid/i.git"],
            cwd=ROOT,
        )
        configured = testkit.run(["git", "config", "--global", "user.name"], cwd=target, check=False).stdout.strip()
        local = testkit.run(["git", "config", "--local", "user.name"], cwd=target, check=False).stdout.strip()
        if configured:
            assert local == "", "a learner with a global git identity keeps it"
        else:
            assert local, "without any identity a placeholder lets the first commit succeed"


def test_creating_inside_the_template_is_refused() -> None:
    with testkit.tempdir("studystate-release-") as tmp:
        copy = testkit.copy_template(Path(tmp))
        result = testkit.script(
            "create_instance.py", "--target", str(copy / "nested"), "--remote", "https://example.invalid/n.git",
            cwd=copy, check=False,
        )
        assert result.returncode == 1 and "outside the template checkout" in result.stdout
        assert not (copy / "nested").exists()


def main() -> int:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed: list[tuple[str, BaseException]] = []
    for test in tests:
        print(f"Running {test.__name__}...")
        try:
            test()
            print("  passed")
        except BaseException as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            print(f"  failed: {exc!r}")
            failed.append((test.__name__, exc))
    if failed:
        print("\nFailed tests:")
        for name, exc in failed:
            print(f"  - {name}: {exc!r}")
        return 1
    print("\nAll template release tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
