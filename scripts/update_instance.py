#!/usr/bin/env python3
"""Bring a StudyState learner instance up to this template's release.

Run it from the template checkout; an instance never updates itself:

    python3 scripts/update_instance.py --target ../Study_MyTarget            # dry run
    python3 scripts/update_instance.py --target ../Study_MyTarget --apply

It replaces the template-owned files (``managed`` in ``core/ownership.json``) and
the StudyState block inside the instance's ``AGENTS.md``, merges the version file,
and refreshes ``state/TEMPLATE_LOCK.json``. It never writes learner state,
targets, reviews, sessions, sources, local rules, or the ProjectState files; it
never commits. Without ``--apply`` it writes nothing.

A file the instance edited since it was cast is never overwritten silently: the
lock records what the template installed, so an edit is detected and the update
refuses unless ``--replace-edited`` says you have read the report.

Exit codes: 0 ok (dry run complete, applied, or already current); 1 only with
``--check`` when a change is needed; 2 refused or invalid.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import template_ownership as own

ROOT = Path(__file__).resolve().parent.parent
VALID_TARGET_MODES = {"bootstrap", "learner_instance"}
AGENTS_BLOCK = "AGENTS.md#studystate-block"


@dataclass
class Action:
    path: str
    kind: str  # add, replace, replace_edited, replace_unknown, remove, keep_edited, none
    detail: str = ""


class Refusal(Exception):
    """The update cannot proceed safely."""


# --- planning --------------------------------------------------------------


def check_target(target: Path) -> None:
    if not target.exists() or not target.is_dir():
        raise Refusal(f"target is not a directory: {target}")
    if target.is_symlink():
        raise Refusal("target must not be a symlink")
    if target.resolve() == ROOT.resolve():
        raise Refusal("target is the template itself; give a learner instance")
    mode = own.read_mode(target)
    if mode is None:
        raise Refusal("target has no state/STUDYDD_MODE.yaml: it is not a StudyState instance")
    if mode not in VALID_TARGET_MODES:
        raise Refusal(f"target is in mode {mode!r}; only {sorted(VALID_TARGET_MODES)} can be updated")


def check_lock_entry(ownership: own.Ownership, rel: str) -> None:
    """Refuse a lock entry that is not a well-formed path to a template-owned file.

    The lock lives in the instance, so it is input, not authority. Without this check a
    damaged or hand-edited lock could name a learner file and have the update delete it.
    """
    parts = rel.replace("\\", "/").split("/")
    if not rel or rel.startswith(("/", "\\")) or ":" in parts[0] or any(part in {"", ".", ".."} for part in parts):
        raise Refusal(f"{own.LOCK_PATH} lists a malformed path: {rel!r}")
    if ownership.classify(rel) != "managed":
        raise Refusal(
            f"{own.LOCK_PATH} lists {rel}, which the template does not own; the lock is damaged or was edited by hand. "
            "Remove that entry, or recreate the lock by converting the instance (docs/UPGRADING.md)"
        )


def safe_destination(target: Path, rel: str) -> Path:
    """The path for ``rel`` inside ``target``, refusing symlinks and escapes."""
    base = target.resolve()
    destination = target / rel
    probe = destination
    while probe != target:
        if probe.is_symlink():
            raise Refusal(f"{rel} is or sits under a symlink")
        probe = probe.parent
    if base not in destination.resolve().parents:
        raise Refusal(f"{rel} resolves outside the target")
    return destination


def plan_files(target: Path, ownership: own.Ownership, lock: dict | None) -> tuple[list[Action], list[str]]:
    managed = own.files_of_class(ROOT, ownership, "managed")
    locked_files: dict[str, str] = (lock or {}).get("files", {})
    actions: list[Action] = []
    for rel in managed:
        destination = safe_destination(target, rel)
        if destination.is_dir():
            raise Refusal(f"{rel} is a directory in the target but a file in the template")
        if not destination.exists():
            actions.append(Action(rel, "add"))
            continue
        new = own.digest_file(ROOT / rel)
        current = own.digest_file(destination)
        if current == new:
            actions.append(Action(rel, "none"))
        elif rel not in locked_files:
            actions.append(Action(rel, "replace_unknown", "no record of what the template installed here"))
        elif current == locked_files[rel]:
            actions.append(Action(rel, "replace"))
        else:
            actions.append(Action(rel, "replace_edited", "edited in the instance since it was installed"))

    managed_set = set(managed)
    for rel in sorted(locked_files):
        check_lock_entry(ownership, rel)
    for rel, installed in sorted(locked_files.items()):
        if rel in managed_set:
            continue
        destination = safe_destination(target, rel)
        if not destination.is_file():
            continue
        if own.digest_file(destination) == installed:
            actions.append(Action(rel, "remove", "no longer in the template"))
        else:
            actions.append(Action(rel, "keep_edited", "no longer in the template, but edited here; left in place"))
    return actions, managed


def plan_agents(target: Path, lock: dict | None, version: str) -> tuple[Action, str | None]:
    """Plan the StudyState block in AGENTS.md; returns the action and the new text."""
    path = safe_destination(target, own.AGENTS_PATH)
    if not path.is_file():
        raise Refusal("AGENTS.md is missing in the target")
    try:
        text, _eol = own.read_text_eol(path)
        block = own.find_block(text)
    except own.OwnershipError as exc:
        raise Refusal(str(exc)) from exc
    if block is None:
        raise Refusal(
            "AGENTS.md has no studystate:managed block (an instance cast before release 0.12.0). "
            "Merge it by hand once; see docs/UPGRADING.md, 'Convert an older instance'."
        )

    new_inner = (ROOT / own.CORE_BLOCK_PATH).read_text(encoding="utf-8")
    if not new_inner.endswith("\n"):
        new_inner += "\n"
    new_text = own.replace_block(text, version, new_inner)
    current, new = own.block_digest(block.inner), own.block_digest(new_inner)
    locked = (lock or {}).get("agents_block_sha256")

    if current == new and block.release == version:
        return Action(AGENTS_BLOCK, "none"), None
    if current == new:
        return Action(AGENTS_BLOCK, "replace", f"release marker {block.release} -> {version}"), new_text
    if locked is None:
        return Action(AGENTS_BLOCK, "replace_unknown", "no record of what the template installed here"), new_text
    if current == locked:
        return Action(AGENTS_BLOCK, "replace"), new_text
    return Action(AGENTS_BLOCK, "replace_edited", "the block was edited in the instance"), new_text


def dirty_paths(target: Path, paths: list[str]) -> list[str]:
    """Paths among ``paths`` with uncommitted changes, when the target is a Git repository."""
    if not paths or not (target / ".git").exists():
        return []
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--", *paths],
            cwd=target, capture_output=True, check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        raise Refusal("git cannot report the target's status; use --allow-dirty to skip the check")
    entries = [e for e in result.stdout.decode("utf-8", "replace").split("\0") if e]
    return sorted({e[3:] for e in entries if len(e) > 3})


# --- version file ----------------------------------------------------------


def _set_scalar(text: str, key: str, value: str) -> str:
    line = f'{key}: "{value}"'
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda _m: line, text, count=1)
    return text.rstrip("\n") + "\n" + line + "\n"


def merge_version_file(text: str, *, from_version: str, to_version: str, commit: str, today: str, note: str) -> str:
    """Record an upgrade in STUDYDD_TEMPLATE_VERSION.yaml without disturbing its comments.

    Only the three scalar keys and the ``upgrade_history`` list change. The new
    list item copies the indentation of the existing items so the YAML stays valid.
    """
    text = _set_scalar(text, "template_version", to_version)
    text = _set_scalar(text, "last_template_upgrade_version", to_version)
    text = _set_scalar(text, "last_template_upgrade_commit", commit)

    def entry(indent: str) -> list[str]:
        return [
            f'{indent}- date: "{today}"',
            f'{indent}  from_version: "{from_version}"',
            f'{indent}  to_version: "{to_version}"',
            f'{indent}  to_commit: "{commit}"',
            f"{indent}  note: {json.dumps(note)}",
        ]

    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not line.startswith("upgrade_history:"):
            continue
        rest = line[len("upgrade_history:"):].strip()
        if rest == "[]":
            lines[index] = "upgrade_history:"
            lines[index + 1:index + 1] = entry("  ")
            return "\n".join(lines)
        if rest:
            raise Refusal("upgrade_history has an unsupported shape; update it by hand")
        # A block list: the items follow, indented or starting at column 0.
        last = index
        indent = "  "
        for offset in range(index + 1, len(lines)):
            current = lines[offset]
            if current.lstrip().startswith("- ") and last == index:
                indent = current[: len(current) - len(current.lstrip())]
            if current.startswith((" ", "-")) and current.strip():
                last = offset
            elif current.strip() == "" or current.lstrip().startswith("#"):
                continue
            else:
                break
        lines[last + 1:last + 1] = entry(indent)
        return "\n".join(lines)
    return text.rstrip("\n") + "\nupgrade_history:\n" + "\n".join(entry("  ")) + "\n"


# --- applying --------------------------------------------------------------


def atomic_write(destination: Path, data: bytes, mode: int | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=destination.parent, prefix=".update-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        if mode is not None:
            os.chmod(temp_name, mode)
        os.replace(temp_name, destination)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def apply_plan(
    target: Path, actions: list[Action], managed: list[str], agents_text: str | None,
    version: str, commit: str, from_version: str, today: str,
) -> None:
    counts = {"add": 0, "replace": 0, "remove": 0}
    for action in actions:
        if action.path == AGENTS_BLOCK:
            continue  # the block is written below, inside AGENTS.md
        destination = target / action.path
        if action.kind in {"add", "replace", "replace_edited", "replace_unknown"}:
            source = ROOT / action.path
            atomic_write(destination, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
            counts["add" if action.kind == "add" else "replace"] += 1
        elif action.kind == "remove":
            destination.unlink()
            counts["remove"] += 1
            parent = destination.parent
            while parent != target:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent

    if agents_text is not None:
        _text, eol = own.read_text_eol(target / own.AGENTS_PATH)
        atomic_write(target / own.AGENTS_PATH, own.encode_text(agents_text, eol))

    note = (
        f"Mechanical update by scripts/update_instance.py: {counts['add']} added, "
        f"{counts['replace']} replaced, {counts['remove']} removed. Learner state untouched."
    )
    version_path = target / own.VERSION_PATH
    if version_path.is_file():
        text, eol = own.read_text_eol(version_path)
        merged = merge_version_file(text, from_version=from_version, to_version=version, commit=commit, today=today, note=note)
        atomic_write(version_path, own.encode_text(merged, eol))

    block = own.find_block(own.read_text_eol(target / own.AGENTS_PATH)[0])
    files = {rel: own.digest_file(target / rel) for rel in managed if (target / rel).is_file()}
    own.write_lock(target, version, commit, files, own.block_digest(block.inner) if block else None)


# --- reporting -------------------------------------------------------------

LABELS = {
    "add": "add",
    "replace": "replace",
    "replace_edited": "REPLACE EDITED",
    "replace_unknown": "REPLACE UNKNOWN",
    "remove": "remove",
    "keep_edited": "keep (edited)",
}


def print_report(actions: list[Action], target: Path, version: str, from_version: str, lock: dict | None, apply: bool) -> None:
    changing = [a for a in actions if a.kind != "none"]
    print(f"StudyState update: {from_version} -> {version}")
    print(f"Template: {ROOT}")
    print(f"Target:   {target}")
    print(f"Lock:     {'present' if lock else 'absent (no record of what the template installed)'}")
    print("")
    for kind in ("add", "replace", "replace_edited", "replace_unknown", "remove", "keep_edited"):
        group = [a for a in actions if a.kind == kind]
        if not group:
            continue
        print(f"{LABELS[kind]} ({len(group)}):")
        for action in group[:40]:
            suffix = f"  [{action.detail}]" if action.detail else ""
            print(f"  {action.path}{suffix}")
        if len(group) > 40:
            print(f"  ... and {len(group) - 40} more")
        print("")
    unchanged = len(actions) - len(changing)
    print(f"Unchanged: {unchanged}. Learner state, targets, reviews, sessions, sources, local rules, and the ProjectState files are never touched.")
    print("ProjectState gate and block: update them with ProjectState's own projectstate_update.py.")
    if not apply:
        print("Dry run: nothing was written. Re-run with --apply to write.")


# --- main ------------------------------------------------------------------


def run(args: argparse.Namespace) -> int:
    if own.read_mode(ROOT) != "template":
        raise Refusal("run this from the template checkout (state/STUDYDD_MODE.yaml must say mode: template)")
    target = Path(args.target).resolve() if not Path(args.target).is_symlink() else Path(args.target)
    check_target(target)

    ownership = own.load_ownership(ROOT)
    stray = own.unclassified(ROOT, ownership)
    if stray:
        raise Refusal("the template has files that core/ownership.json does not classify: " + ", ".join(stray))

    version = own.template_version(ROOT)
    lock = own.read_lock(target)
    from_version = (lock or {}).get("template_version") or "unknown"

    actions, managed = plan_files(target, ownership, lock)
    agents_action, agents_text = plan_agents(target, lock, version)
    actions.append(agents_action)

    unsafe = [a for a in actions if a.kind in {"replace_edited", "replace_unknown"}]
    if unsafe and not args.replace_edited:
        print_report(actions, target, version, from_version, lock, args.apply)
        raise Refusal(
            f"{len(unsafe)} item(s) were edited in the instance or have no install record; "
            "review the report, then pass --replace-edited to overwrite them (the edits survive only in Git history)"
        )

    needs_change = any(a.kind != "none" for a in actions) or (lock or {}).get("template_version") != version

    # The guard protects uncommitted work, so it applies only when something would be written.
    if needs_change and not args.allow_dirty:
        writing = [a.path for a in actions if a.kind in {"add", "replace", "replace_edited", "replace_unknown", "remove"} and a.path != AGENTS_BLOCK]
        if agents_text is not None:
            writing.append(own.AGENTS_PATH)
        writing += [own.VERSION_PATH, own.LOCK_PATH]
        dirty = dirty_paths(target, writing)
        if dirty:
            print_report(actions, target, version, from_version, lock, args.apply)
            raise Refusal(
                "uncommitted changes in files the update would write: " + ", ".join(dirty)
                + ". Commit or stash them, work on a private branch, or pass --allow-dirty (uncommitted edits would be lost)"
            )

    if args.json:
        print(json.dumps({
            "from_version": from_version, "to_version": version, "target": str(target),
            "lock": bool(lock), "changes_needed": needs_change, "applied": False,
            "actions": [asdict(a) for a in actions if a.kind != "none"],
        }, indent=2))
    else:
        print_report(actions, target, version, from_version, lock, args.apply)

    if args.apply and needs_change:
        apply_plan(target, actions, managed, agents_text, version, own.git_head(ROOT), from_version, date.today().isoformat())
        print("Applied. Review `git diff`, run the instance's checks, then commit. Nothing was committed.")
        print("  python3 scripts/check_studydd.py")
        return 0
    if args.check and needs_change:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update a StudyState learner instance from this template")
    parser.add_argument("--target", required=True, help="Path to the learner instance")
    parser.add_argument("--apply", action="store_true", help="Write the update (default is a dry run)")
    parser.add_argument("--check", action="store_true", help="Dry run that exits 1 when a change is needed")
    parser.add_argument("--json", action="store_true", help="Print the plan as JSON")
    parser.add_argument("--replace-edited", action="store_true", help="Overwrite files and blocks edited in the instance")
    parser.add_argument("--allow-dirty", action="store_true", help="Skip the uncommitted-changes check")
    args = parser.parse_args(argv)
    if args.apply and args.check:
        parser.error("--apply and --check are mutually exclusive")
    try:
        return run(args)
    except (Refusal, own.OwnershipError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
