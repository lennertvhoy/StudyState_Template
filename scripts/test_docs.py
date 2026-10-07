#!/usr/bin/env python3
"""The documentation must not point at things that are not there.

A restructure leaves dangling links and file names behind; in a public template that is the
first thing a new reader trips over. This checks every relative Markdown link, and every file
the prose names inside backticks (`scripts/x.py`, `protocols/X.md`, ...), against the tree.
Historical records (the changelog, ADRs, evidence) legitimately name removed files and are skipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import testkit  # noqa: E402

ROOT = testkit.ROOT

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
NAMED_FILE = re.compile(r"`((?:scripts|protocols|docs|PROMPTS|study_skills|core)/[A-Za-z0-9_./-]+\.(?:py|md|json|yaml|yml))`")
HISTORICAL = {"CHANGELOG.md"}
HISTORICAL_DIRS = {"adr", "evidence", ".git", "EXAMPLES"}


def markdown_files() -> list[Path]:
    files = []
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT)
        if rel.name in HISTORICAL or any(part in HISTORICAL_DIRS for part in rel.parts):
            continue
        files.append(path)
    return files


def prose(path: Path) -> str:
    """The file's text without fenced code blocks (examples, not claims about the tree) and without
    the ProjectState managed block, which names ProjectState's own tools."""
    text = re.sub(r"<!-- projectstate:managed:start.*?projectstate:managed:end -->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def test_relative_links_resolve() -> None:
    broken = []
    for path in markdown_files():
        for match in LINK.finditer(prose(path)):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            file_part = target.split("#")[0].split("?")[0]
            if file_part and not (path.parent / file_part).exists():
                broken.append(f"{path.relative_to(ROOT).as_posix()} -> {target}")
    assert not broken, broken


def test_files_named_in_prose_exist() -> None:
    missing = []
    for path in markdown_files():
        for match in NAMED_FILE.finditer(prose(path)):
            name = match.group(1)
            if any(ch in name for ch in "<>*") or (ROOT / name).exists():
                continue
            missing.append(f"{path.relative_to(ROOT).as_posix()} names {name}")
    assert not missing, missing


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
    print("\nAll documentation tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
