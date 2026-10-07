#!/usr/bin/env python3
"""Keep the template's release surface consistent. Template maintenance only.

    python3 scripts/template_release.py check   # verify; exit 1 on any finding
    python3 scripts/template_release.py sync    # rewrite the AGENTS.md block from its source

The StudyState block in ``AGENTS.md`` is generated from ``core/AGENTS.studystate.md``
and carries the template version in its start marker. Instances receive that block
through ``scripts/update_instance.py``, so the template must never ship a block that
differs from its source or a version with no changelog entry.

``check`` fails when:

* a file the template ships is not classified in ``core/ownership.json``;
* the block in ``AGENTS.md`` differs from its source or names another version;
* ``CHANGELOG.md`` has no entry for the current template version;
* a ``core/instance`` scaffold file is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import template_ownership as own

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_FILES = (
    "AGENTS.local.md",
    "PROJECT.md",
    "README.md",
    "STATE.yaml",
    "evidence/bootstrap-001/summary.md",
    "validate.yml",
)


def source_block(root: Path) -> str:
    inner = (root / own.CORE_BLOCK_PATH).read_text(encoding="utf-8")
    return inner if inner.endswith("\n") else inner + "\n"


def findings(root: Path) -> list[str]:
    problems: list[str] = []
    try:
        ownership = own.load_ownership(root)
        version = own.template_version(root)
    except own.OwnershipError as exc:
        return [str(exc)]

    for rel in own.unclassified(root, ownership):
        problems.append(f"{rel} is not classified in {own.OWNERSHIP_PATH}")
    for rel in own.template_files(root):
        try:
            ownership.classify(rel)
        except own.OwnershipError as exc:
            problems.append(str(exc))

    agents = root / own.AGENTS_PATH
    try:
        block = own.find_block(agents.read_text(encoding="utf-8")) if agents.is_file() else None
    except own.OwnershipError as exc:
        return problems + [str(exc)]
    if block is None:
        problems.append("AGENTS.md has no studystate:managed block; run: python3 scripts/template_release.py sync")
    else:
        if own.block_digest(block.inner) != own.block_digest(source_block(root)):
            problems.append(f"the AGENTS.md block differs from {own.CORE_BLOCK_PATH}; run: python3 scripts/template_release.py sync")
        if block.release != version:
            problems.append(f"the AGENTS.md block says release {block.release} but template_version is {version}")

    changelog = root / "CHANGELOG.md"
    if not changelog.is_file() or f"## {version}" not in changelog.read_text(encoding="utf-8"):
        problems.append(f"CHANGELOG.md has no '## {version}' entry (state its instance action)")

    for rel in SCAFFOLD_FILES:
        if not (root / "core" / "instance" / rel).is_file():
            problems.append(f"core/instance/{rel} is missing")
    return problems


def sync(root: Path) -> int:
    version = own.template_version(root)
    agents = root / own.AGENTS_PATH
    text = agents.read_text(encoding="utf-8")
    updated = own.replace_block(text, version, source_block(root))
    if updated == text:
        print(f"AGENTS.md block already matches {own.CORE_BLOCK_PATH} (release {version}).")
        return 0
    agents.write_text(updated, encoding="utf-8", newline="\n")
    print(f"AGENTS.md block rewritten from {own.CORE_BLOCK_PATH} (release {version}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Template release consistency")
    parser.add_argument("command", choices=["check", "sync"])
    parser.add_argument("--root", default=str(ROOT), help="Template root (default: this checkout)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "sync":
            return sync(root)
        problems = findings(root)
    except own.OwnershipError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if problems:
        print("Template release check failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Template release check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
