#!/usr/bin/env python3
"""Tests for scripts/update_instance.py.

Each scenario builds a throwaway template (a copy of this checkout) and a learner
instance cast from it, changes the template, and updates the instance. Nothing
touches the real repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402
import testkit  # noqa: E402

LOCAL_RULE = "- Study in short evening sessions; use Dutch for explanations.\n"
LEARNER_FILES = (
    "state/STUDY_STATE.yaml",
    "state/SKILL_MAP.yaml",
    "state/EVIDENCE_LOG.md",
    "NEXT_ACTIONS.md",
    "reviews/REVIEW_STATE.yaml",
    "targets/kit-target/TARGET.yaml",
    "PROJECT.md",
    "STATE.yaml",
    "evidence/bootstrap-001/summary.md",
    "scripts/projectstate_gate.py",
)


class World:
    """A template copy plus an instance cast from it, with the instance committed."""

    def __init__(self, tmp: str):
        self.tmp = Path(tmp)
        self.template = testkit.copy_template(self.tmp)
        self.instance = testkit.make_learner_instance(self.tmp, template=self.template)
        agents = self.instance / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        agents.write_text(text.replace("## Local rules\n", "## Local rules\n\n" + LOCAL_RULE, 1), encoding="utf-8", newline="\n")
        testkit.commit_all(self.instance, "instance baseline")

    def update(self, *args: str):
        return testkit.script("update_instance.py", "--target", str(self.instance), *args, cwd=self.template, check=False)

    def change_template(self) -> None:
        """A realistic release: new, changed, removed managed files, a new block, a new version."""
        (self.template / "protocols" / "NEW_PROTOCOL.md").write_text("# New\n", encoding="utf-8", newline="\n")
        ask = self.template / "protocols" / "ASK_QUESTION.md"
        ask.write_text(ask.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8", newline="\n")
        (self.template / "docs" / "future-model-efficiency.md").unlink()
        core = self.template / own.CORE_BLOCK_PATH
        core.write_text(core.read_text(encoding="utf-8") + "\n## New section\n\nNew contract text.\n", encoding="utf-8", newline="\n")
        version = self.template / own.VERSION_PATH
        version.write_text(version.read_text(encoding="utf-8").replace('template_version: "0.12.0"', 'template_version: "0.12.1"'), encoding="utf-8", newline="\n")
        testkit.script("template_release.py", "sync", cwd=self.template)
        testkit.commit_all(self.template, "release 0.12.1")

    def digests(self, paths) -> dict[str, str]:
        return {p: hashlib.sha256((self.instance / p).read_bytes()).hexdigest() for p in paths}

    def status(self) -> str:
        return testkit.git(self.instance, "status", "--porcelain")


def test_a_fresh_instance_is_current_and_a_dry_run_writes_nothing() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        result = world.update("--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Unchanged:" in result.stdout and "add (" not in result.stdout and "replace (" not in result.stdout
        assert world.status() == ""


def test_a_release_updates_only_what_the_template_owns() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        learner_before = world.digests(LEARNER_FILES)
        agents_before = (world.instance / "AGENTS.md").read_text(encoding="utf-8")

        dry = world.update()
        assert dry.returncode == 0, dry.stdout + dry.stderr
        assert "protocols/NEW_PROTOCOL.md" in dry.stdout and "protocols/ASK_QUESTION.md" in dry.stdout
        assert "docs/future-model-efficiency.md" in dry.stdout and AGENTS_BLOCK in dry.stdout
        assert "Dry run: nothing was written" in dry.stdout
        assert world.status() == "", "a dry run never writes"
        assert world.update("--check").returncode == 1, "--check exits 1 when a change is needed"

        applied = world.update("--apply")
        assert applied.returncode == 0, applied.stdout + applied.stderr

        assert (world.instance / "protocols" / "NEW_PROTOCOL.md").read_text(encoding="utf-8") == "# New\n"
        assert "A new rule." in (world.instance / "protocols" / "ASK_QUESTION.md").read_text(encoding="utf-8")
        assert not (world.instance / "docs" / "future-model-efficiency.md").exists(), "an unedited file removed upstream is removed"

        agents = (world.instance / "AGENTS.md").read_text(encoding="utf-8")
        assert "New contract text." in agents and "release=0.12.1" in agents
        assert LOCAL_RULE in agents, "local rules survive"
        assert agents[agents.index(own.BLOCK_END):] == agents_before[agents_before.index(own.BLOCK_END):], "text after the block is byte-identical"
        assert agents[: agents.index("<!-- studystate:managed:start")] == agents_before[: agents_before.index("<!-- studystate:managed:start")]

        assert world.digests(LEARNER_FILES) == learner_before, "learner state and the ProjectState files are untouched"

        lock = own.read_lock(world.instance)
        assert lock["template_version"] == "0.12.1"
        assert lock["files"]["protocols/NEW_PROTOCOL.md"] == own.digest_file(world.template / "protocols" / "NEW_PROTOCOL.md")
        assert "docs/future-model-efficiency.md" not in lock["files"]

        version_text = (world.instance / own.VERSION_PATH).read_text(encoding="utf-8")
        assert "# StudyState template version tracking." in version_text, "the file's comments survive"
        data = testkit.load_yaml(world.instance / own.VERSION_PATH)
        assert data["template_version"] == "0.12.1" and data["last_template_upgrade_version"] == "0.12.1"
        assert data["instance_created_from_template_version"] == "0.12.0", "the origin is never rewritten"
        entry = data["upgrade_history"][-1]
        assert entry["from_version"] == "0.12.0" and entry["to_version"] == "0.12.1" and "1 added" in entry["note"]

        assert testkit.script("check_studydd.py", cwd=world.instance, check=False).returncode == 0, "the instance still validates"
        assert (world.instance / ".git").exists() and testkit.git(world.instance, "log", "--oneline").count("\n") == 1, "nothing is committed"


AGENTS_BLOCK = "AGENTS.md#studystate-block"


def test_applying_twice_changes_nothing_more() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        assert world.update("--apply").returncode == 0
        # Uncommitted result of the first apply: checking again must not trip the dirty guard.
        assert world.update("--check").returncode == 0, "nothing left to write, so the dirty guard stays quiet"
        testkit.commit_all(world.instance, "apply 0.12.1")
        snapshot = world.digests(own.files_of_class(world.template, own.load_ownership(world.template), "managed"))
        again = world.update("--apply")
        assert again.returncode == 0
        assert world.status() == "", "a second apply writes nothing"
        assert world.digests(snapshot) == snapshot
        assert world.update("--check").returncode == 0


def test_two_releases_append_two_history_entries() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        assert world.update("--apply").returncode == 0
        testkit.commit_all(world.instance, "apply 0.12.1")

        version = world.template / own.VERSION_PATH
        version.write_text(version.read_text(encoding="utf-8").replace('"0.12.1"', '"0.12.2"', 1), encoding="utf-8", newline="\n")
        (world.template / "protocols" / "NEW_PROTOCOL.md").write_text("# New again\n", encoding="utf-8", newline="\n")
        testkit.script("template_release.py", "sync", cwd=world.template)
        testkit.commit_all(world.template, "release 0.12.2")
        assert world.update("--apply").returncode == 0

        history = testkit.load_yaml(world.instance / own.VERSION_PATH)["upgrade_history"]
        assert [h["to_version"] for h in history][-2:] == ["0.12.1", "0.12.2"]
        assert history[-1]["from_version"] == "0.12.1"


def test_a_file_edited_in_the_instance_blocks_the_update() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        ask = world.instance / "protocols" / "ASK_QUESTION.md"
        ask.write_text(ask.read_text(encoding="utf-8") + "\nMy own rule.\n", encoding="utf-8", newline="\n")
        testkit.commit_all(world.instance, "local edit")
        world.change_template()

        refused = world.update()
        assert refused.returncode == 2, refused.stdout + refused.stderr
        assert "REPLACE EDITED" in refused.stdout and "protocols/ASK_QUESTION.md" in refused.stdout
        assert "--replace-edited" in refused.stderr
        assert world.update("--apply").returncode == 2
        assert "My own rule." in ask.read_text(encoding="utf-8"), "nothing was overwritten"
        assert "NEW_PROTOCOL" not in " ".join(p.name for p in (world.instance / "protocols").iterdir()), "a refusal writes nothing at all"

        forced = world.update("--replace-edited", "--apply")
        assert forced.returncode == 0, forced.stdout + forced.stderr
        text = ask.read_text(encoding="utf-8")
        assert "My own rule." not in text and "A new rule." in text


def test_an_edited_contract_block_blocks_the_update() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        agents = world.instance / "AGENTS.md"
        text = agents.read_text(encoding="utf-8")
        agents.write_text(text.replace("## Mode check", "## Mode check\n\nMy tweak.", 1), encoding="utf-8", newline="\n")
        testkit.commit_all(world.instance, "tweak the contract")
        world.change_template()

        refused = world.update()
        assert refused.returncode == 2 and "the block was edited in the instance" in refused.stdout
        assert world.update("--replace-edited", "--apply").returncode == 0
        assert "My tweak." not in agents.read_text(encoding="utf-8") and LOCAL_RULE in agents.read_text(encoding="utf-8")


def test_uncommitted_changes_in_written_files_block_the_update() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        version = world.instance / own.VERSION_PATH
        version.write_text(version.read_text(encoding="utf-8") + "\n# unsaved thought\n", encoding="utf-8", newline="\n")

        refused = world.update()
        assert refused.returncode == 2 and "uncommitted changes" in refused.stderr and own.VERSION_PATH in refused.stderr
        allowed = world.update("--apply", "--allow-dirty")
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr


def test_an_instance_without_a_lock_cannot_tell_edits_from_old_text() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        (world.instance / own.LOCK_PATH).unlink()
        testkit.commit_all(world.instance, "drop the lock")
        assert world.update("--check").returncode == 1, "an identical instance still needs its lock written"
        assert world.update("--apply").returncode == 0, "identical files are not treated as edited"
        assert own.read_lock(world.instance) is not None
        testkit.commit_all(world.instance, "lock restored")

        (world.instance / own.LOCK_PATH).unlink()
        testkit.commit_all(world.instance, "drop the lock again")
        world.change_template()
        refused = world.update()
        assert refused.returncode == 2 and "REPLACE UNKNOWN" in refused.stdout
        assert world.update("--replace-edited", "--apply").returncode == 0


def test_an_older_instance_without_the_block_is_refused_with_guidance() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        (world.instance / "AGENTS.md").write_text("# AGENTS.md\n\nLegacy rules, no markers.\n", encoding="utf-8", newline="\n")
        testkit.commit_all(world.instance, "legacy agents")
        refused = world.update()
        assert refused.returncode == 2 and "Convert an older instance" in refused.stderr


def test_unsafe_targets_are_refused() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        for target, expected in (
            (world.template, "template itself"),
            (world.tmp / "nowhere", "not a directory"),
            (world.tmp, "not a StudyState instance"),
        ):
            result = testkit.script("update_instance.py", "--target", str(target), cwd=world.template, check=False)
            assert result.returncode == 2 and expected in result.stderr, (target, result.stderr)

        other_template = testkit.copy_template(world.tmp, "Other_Template")
        result = testkit.script("update_instance.py", "--target", str(other_template), cwd=world.template, check=False)
        assert result.returncode == 2 and "mode 'template'" in result.stderr

        # An instance cannot update itself: the tool must run from a template.
        result = testkit.script("update_instance.py", "--target", str(world.instance), cwd=world.instance, check=False)
        assert result.returncode != 0, "update_instance.py is not shipped to instances"


def test_symlinks_are_refused() -> None:
    if os.name == "nt":  # creating a symlink needs a privilege a CI runner may not have
        return
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        outside = world.tmp / "outside"
        outside.mkdir()
        (world.instance / "protocols" / "NEW_PROTOCOL.md").symlink_to(outside / "elsewhere.md")
        testkit.commit_all(world.instance, "symlink")
        refused = world.update("--apply")
        assert refused.returncode == 2 and "symlink" in refused.stderr
        assert not (outside / "elsewhere.md").exists(), "nothing was written through the link"


def test_a_damaged_lock_cannot_make_the_update_delete_learner_files() -> None:
    """The lock is instance-supplied input: it must never turn into permission to delete."""
    for bad_key in (
        "state/STUDY_STATE.yaml",       # learner state
        "targets/kit-target/TARGET.yaml",
        "AGENTS.md",                    # composite, never deleted
        "../../outside.txt",            # escapes the instance
        "/etc/hosts",                   # absolute
        "protocols//x.md",              # malformed
    ):
        with testkit.tempdir("studystate-update-") as tmp:
            world = World(tmp)
            lock = own.read_lock(world.instance)
            victim = world.instance / bad_key
            lock["files"][bad_key] = own.digest_file(victim) if victim.is_file() else "0" * 64
            (world.instance / own.LOCK_PATH).write_text(json.dumps(lock), encoding="utf-8", newline="\n")
            testkit.commit_all(world.instance, "tampered lock")
            before = world.digests(LEARNER_FILES)
            refused = world.update("--apply")
            assert refused.returncode == 2 and "lists" in refused.stderr, (bad_key, refused.returncode, refused.stderr)
            assert world.digests(LEARNER_FILES) == before, f"learner files must survive a lock that names {bad_key}"
            assert world.status() == "", "a refusal writes nothing"


def test_json_report_and_flag_conflicts() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        world.change_template()
        report = json.loads(world.update("--json").stdout)
        assert report["from_version"] == "0.12.0" and report["to_version"] == "0.12.1" and report["changes_needed"] is True
        kinds = {a["path"]: a["kind"] for a in report["actions"]}
        assert kinds["protocols/NEW_PROTOCOL.md"] == "add" and kinds["docs/future-model-efficiency.md"] == "remove"
        assert world.update("--apply", "--check").returncode == 2, "--apply and --check conflict"


def test_crlf_agents_md_is_preserved_and_mixed_endings_are_refused() -> None:
    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        agents = world.instance / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        testkit.commit_all(world.instance, "crlf checkout")
        world.change_template()
        applied = world.update("--apply")
        assert applied.returncode == 0, applied.stdout + applied.stderr
        data = agents.read_bytes()
        assert data.count(b"\r\n") == data.count(b"\n") and b"New contract text." in data, "a Windows checkout stays CRLF and gets the new block"
        assert LOCAL_RULE.encode().replace(b"\n", b"\r\n") in data, "local text survives with its line endings"

    with testkit.tempdir("studystate-update-") as tmp:
        world = World(tmp)
        agents = world.instance / "AGENTS.md"
        agents.write_bytes(agents.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n", 3))
        testkit.commit_all(world.instance, "mixed endings")
        world.change_template()
        refused = world.update()
        assert refused.returncode == 2 and "mixes CRLF and LF" in refused.stderr


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
    print("\nAll update_instance tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
