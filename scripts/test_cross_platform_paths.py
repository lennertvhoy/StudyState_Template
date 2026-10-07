#!/usr/bin/env python3
"""Cross-platform portability smoke tests.

Catches obvious portability mistakes: hardcoded home paths, missing Windows
setup instructions, un-gitignored generated state, and scripts that cannot be
run with the portable `python scripts/...` form.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Scripts that should run with `python scripts/<name>.py --help`.
VALIDATION_SCRIPTS = [
    "scripts/check_studydd.py",
    "scripts/check_environment.py",
    "scripts/setup_studydd.py",
    "scripts/test_cross_platform_paths.py",
]

# Patterns that are obvious portability mistakes in setup docs and scripts.
FORBIDDEN_PATH_PATTERNS = [
    "/home/",
    "/Users/",
    "C:\\\\",
]

# Scripts that must use pathlib (or os.path) for path handling.
REPO_SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))


def test_setup_docs_cover_all_platforms() -> None:
    setup_doc = ROOT / "docs" / "setup.md"
    assert setup_doc.is_file(), "docs/setup.md is missing"
    text = setup_doc.read_text(encoding="utf-8")
    assert "Linux" in text, "docs/setup.md must mention Linux"
    assert "macOS" in text, "docs/setup.md must mention macOS"
    assert "Windows PowerShell" in text, "docs/setup.md must mention Windows PowerShell"
    assert "```bash" in text, "docs/setup.md must include bash code blocks"
    assert "```powershell" in text, "docs/setup.md must include PowerShell code blocks"


def test_setup_docs_have_no_hardcoded_paths() -> None:
    setup_doc = ROOT / "docs" / "setup.md"
    text = setup_doc.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_PATH_PATTERNS:
        assert pattern not in text, f"docs/setup.md contains hardcoded path: {pattern!r}"


def _repo_text_files() -> list[Path]:
    """Every text file the template ships, found without requiring git."""
    skip_dirs = {".git", ".venv", ".studydd", "__pycache__", ".pytest_cache", ".worktrees", "node_modules"}
    files: list[Path] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in skip_dirs for part in path.relative_to(ROOT).parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files.append(path)
    return files


def test_repo_has_no_hardcoded_machine_paths() -> None:
    """The no-machine-paths law applies to every file the template ships.

    There are no exemptions: historical records live in Git history, not in the
    tree, so nothing here may name a home directory. This file is skipped only
    because it has to spell the forbidden patterns out.
    """
    files = [p for p in _repo_text_files() if p.name != Path(__file__).name]
    assert len(files) > 50, "expected the full template tree to be scanned"
    offenders: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATH_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.relative_to(ROOT).as_posix()} ({pattern!r})")
    assert not offenders, "hardcoded machine paths found: " + ", ".join(offenders)


def test_setup_helper_has_no_hardcoded_paths() -> None:
    setup_script = ROOT / "scripts" / "setup_studydd.py"
    text = setup_script.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_PATH_PATTERNS:
        assert pattern not in text, f"scripts/setup_studydd.py contains hardcoded path: {pattern!r}"


def test_environment_checker_has_no_hardcoded_paths() -> None:
    env_script = ROOT / "scripts" / "check_environment.py"
    text = env_script.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_PATH_PATTERNS:
        assert pattern not in text, f"scripts/check_environment.py contains hardcoded path: {pattern!r}"


def test_repo_scripts_use_pathlib() -> None:
    """Scripts that touch the filesystem should import pathlib (or os.path)."""
    skipped = {"scripts/test_cross_platform_paths.py"}
    file_io_markers = [
        "open(",
        ".read_text",
        ".write_text",
        "os.path",
        "Path(",
    ]
    for script in REPO_SCRIPTS:
        rel = script.relative_to(ROOT).as_posix()
        if rel in skipped:
            continue
        text = script.read_text(encoding="utf-8")
        touches_files = any(marker in text for marker in file_io_markers)
        if not touches_files:
            continue
        assert "from pathlib import" in text or "import pathlib" in text or "import os.path" in text, (
            f"{rel} does filesystem work and should import pathlib or os.path for portable paths"
        )


def test_studydd_generated_state_is_gitignored() -> None:
    gitignore = ROOT / ".gitignore"
    assert gitignore.is_file(), ".gitignore is missing"
    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    assert ".studydd/" in lines or ".studydd" in lines, ".studydd/ must be gitignored"


def test_validation_scripts_run_with_python() -> None:
    for rel in VALIDATION_SCRIPTS:
        script = ROOT / rel
        assert script.is_file(), f"{rel} is missing"
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"{rel} failed when invoked as '{sys.executable} {rel} --help'"
        )


def test_dependency_manifest_exists() -> None:
    assert (ROOT / "requirements.txt").is_file(), "requirements.txt is missing"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Cross-platform portability smoke tests for StudyState")
        print("")
        print("Usage: python scripts/test_cross_platform_paths.py")
        return 0

    tests = [
        test_setup_docs_cover_all_platforms,
        test_setup_docs_have_no_hardcoded_paths,
        test_repo_has_no_hardcoded_machine_paths,
        test_setup_helper_has_no_hardcoded_paths,
        test_environment_checker_has_no_hardcoded_paths,
        test_repo_scripts_use_pathlib,
        test_studydd_generated_state_is_gitignored,
        test_validation_scripts_run_with_python,
        test_dependency_manifest_exists,
    ]

    failed = []
    for test in tests:
        try:
            print(f"Running {test.__name__}...")
            test()
            print("  passed")
        except AssertionError as exc:
            print(f"  failed: {exc}")
            failed.append((test.__name__, exc))
        except Exception as exc:
            print(f"  error: {exc}")
            failed.append((test.__name__, exc))

    if failed:
        print("\nFailed tests:")
        for name, exc in failed:
            print(f"  - {name}: {exc}")
        return 1

    print("\nAll cross-platform path tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
