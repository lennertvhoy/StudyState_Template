#!/usr/bin/env python3
"""Create a deterministic StudyState learner instance from the public template.

Usage:
    python3 scripts/create_instance.py \
        --target ../Study_MyTarget \
        --remote https://github.com/example/Study_MyTarget.git

The instance receives the template-owned files, the seeded starter state, and
its own README, project definition, state slice, and local-rules stub. It does
not receive the template's maintenance material (see ``core/ownership.json``).
It records a lock of the template files it was cast with, so
``scripts/update_instance.py`` can later update it without overwriting local edits.
"""

from __future__ import annotations

import argparse
import re
import shutil
import stat
import subprocess
import sys
from datetime import date
from pathlib import Path

import template_ownership as own

ROOT = Path(__file__).resolve().parent.parent

AGENT_NAME = "StudyState Agent"
AGENT_EMAIL = "studydd-agent@example.invalid"
TEMPLATE_ORIGIN = "https://github.com/lennertvhoy/StudyState_Template.git"

INSTANCE_SCAFFOLD = ROOT / "core" / "instance"
# Scaffold file -> destination in the instance. These replace the template's own
# README and ProjectState files, which describe maintaining the mold.
SCAFFOLD_FILES = {
    "README.md": "README.md",
    "PROJECT.md": "PROJECT.md",
    "STATE.yaml": "STATE.yaml",
    "evidence/bootstrap-001/summary.md": "evidence/bootstrap-001/summary.md",
    # The template's own CI runs template-only tests; an instance gets a CI that fits it.
    "validate.yml": ".github/workflows/validate.yml",
}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"  cwd: {cwd}")
        print(f"  stderr: {result.stderr.strip()}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def is_non_empty_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(child.name != ".git" for child in path.iterdir())


def is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(stat.S_IMODE(source.stat().st_mode))


def set_scalar(text: str, key: str, value: str, *, quote: bool = True, add_after: str | None = None) -> str:
    """Set a top-level ``key: value`` line, keeping every comment in the file."""
    rendered = f'{key}: "{value}"' if quote else f"{key}: {value}"
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _m: rendered, text, count=1)
    if add_after:
        after = re.compile(rf"^{re.escape(add_after)}:.*$", re.MULTILINE).search(text)
        if after:
            return text[: after.end()] + "\n" + rendered + text[after.end():]
    return text.rstrip("\n") + "\n" + rendered + "\n"


def build_agents_md(template_agents: str, today: str) -> str:
    """The instance's AGENTS.md: the template's contract blocks plus empty local text."""
    block = own.find_block(template_agents)
    if block is None:
        raise own.OwnershipError("the template's AGENTS.md has no studystate:managed block")
    head = template_agents[: block.end].rstrip("\n") + "\n"
    head = re.sub(r"^initialized_on: .*$", f"initialized_on: {today}", head, count=1, flags=re.MULTILINE)
    head = re.sub(r"^last_updated: .*$", f"last_updated: {today}", head, count=1, flags=re.MULTILINE)
    local = (INSTANCE_SCAFFOLD / "AGENTS.local.md").read_text(encoding="utf-8")
    return head + local


def write_lock_for(target: Path, ownership: own.Ownership, version: str, commit: str) -> None:
    files = {
        rel: own.digest_file(target / rel)
        for rel in own.files_of_class(ROOT, ownership, "managed")
        if (target / rel).is_file()
    }
    block = own.find_block((target / own.AGENTS_PATH).read_text(encoding="utf-8"))
    own.write_lock(target, version, commit, files, own.block_digest(block.inner) if block else None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a StudyState learner instance")
    parser.add_argument("--target", required=True, help="Target directory for the instance")
    parser.add_argument("--remote", required=True, help="Git remote URL for the instance")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    remote = args.remote

    print("StudyState create-instance")
    print("=======================")

    # 1. Verify current repo is template mode.
    mode = own.read_mode(ROOT)
    if mode != "template":
        print(f"Error: current repo is not in template mode (mode={mode}).")
        return 1

    remotes = run(["git", "remote", "-v"], ROOT, check=False).stdout
    # Accept the legacy StudyDD_Template remote name as a compatibility alias.
    if "StudyState_Template" not in remotes and "StudyDD_Template" not in remotes:
        print("Error: current repo does not appear to be the StudyState_Template remote.")
        return 1

    # 2. Refuse unsafe targets.
    if is_inside(target, ROOT):
        print(f"Error: target must be outside the template checkout: {target}")
        return 1
    if target.exists() and target.is_file():
        print(f"Error: target path is a file: {target}")
        return 1
    if is_non_empty_dir(target):
        print(f"Error: target directory already exists and is not empty: {target}")
        return 1

    # 3. Decide what the instance receives.
    try:
        ownership = own.load_ownership(ROOT)
        stray = own.unclassified(ROOT, ownership)
        if stray:
            print("Error: the template has files that core/ownership.json does not classify:")
            for rel in stray:
                print(f"  - {rel}")
            print("Classify them, then run python3 scripts/template_release.py check.")
            return 1
        version = own.template_version(ROOT)
        files = [rel for rel in own.template_files(ROOT) if ownership.classify(rel) in {"managed", "seeded", "composite"}]
    except own.OwnershipError as exc:
        print(f"Error: {exc}")
        return 1
    commit = own.git_head(ROOT)
    today = date.today().isoformat()
    scaffold_targets = set(SCAFFOLD_FILES.values())

    # 4. Copy the template-owned and seeded files.
    print(f"1. Copying {len(files)} template files to {target}")
    target.mkdir(parents=True, exist_ok=True)
    for rel in files:
        if rel == own.AGENTS_PATH or rel in scaffold_targets:
            continue
        copy_file(ROOT / rel, target / rel)

    # 5. Compose the instance-specific files.
    print("2. Writing the instance README, project definition, state slice, and AGENTS.md")
    try:
        (target / own.AGENTS_PATH).write_text(
            build_agents_md(own.read_text_eol(ROOT / own.AGENTS_PATH)[0], today), encoding="utf-8", newline="\n"
        )
    except own.OwnershipError as exc:
        print(f"Error: {exc}")
        return 1
    for source, destination in SCAFFOLD_FILES.items():
        copy_file(INSTANCE_SCAFFOLD / source, target / destination)

    # 6. Initialize Git. Keep the learner's own identity when one is configured.
    print("3. Initializing Git")
    try:
        run(["git", "init", "-b", "main"], target)
    except subprocess.CalledProcessError:
        run(["git", "init"], target)
        try:
            run(["git", "checkout", "-b", "main"], target)
        except subprocess.CalledProcessError:
            run(["git", "branch", "-M", "main"], target)
    if not run(["git", "config", "user.name"], target, check=False).stdout.strip():
        run(["git", "config", "user.name", AGENT_NAME], target)
    if not run(["git", "config", "user.email"], target, check=False).stdout.strip():
        run(["git", "config", "user.email", AGENT_EMAIL], target)
    run(["git", "remote", "add", "origin", remote], target)

    # 7. Switch mode to bootstrap, keeping the lifecycle documentation in the file.
    print("4. Switching to bootstrap mode")
    mode_path = target / own.MODE_PATH
    text = mode_path.read_text(encoding="utf-8")
    text = set_scalar(text, "mode", "bootstrap", quote=False)
    text = set_scalar(text, "template_origin", TEMPLATE_ORIGIN, add_after="template_remote")
    text = set_scalar(text, "personalized", "false", quote=False)
    text = set_scalar(text, "public_safe", "false_or_review_required", quote=False)
    mode_path.write_text(text, encoding="utf-8", newline="\n")

    # 8. Preserve template origin metadata and lock the template files.
    print("5. Recording template origin metadata and the template lock")
    version_path = target / own.VERSION_PATH
    text = version_path.read_text(encoding="utf-8")
    text = set_scalar(text, "instance_created_from_template_version", version)
    text = set_scalar(text, "instance_created_from_template_commit", commit)
    text = set_scalar(text, "last_template_upgrade_version", version)
    text = set_scalar(text, "last_template_upgrade_commit", commit)
    version_path.write_text(text, encoding="utf-8", newline="\n")
    write_lock_for(target, ownership, version, commit)

    # 9. Run bootstrap validation.
    print("6. Running bootstrap validation")
    result = run([sys.executable, "scripts/check_studydd.py"], target, check=False)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print("Bootstrap validation failed.")
        return 1
    print("Bootstrap validation passed.")

    # 10. Print next prompt.
    prompt_text = (target / "PROMPTS" / "coding_agent_start_prompt.md").read_text(encoding="utf-8")
    print("\nNext step: open the new instance in your coding agent and paste the following prompt:")
    print(f"\n{prompt_text}\n")

    print(f"Instance created at: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
