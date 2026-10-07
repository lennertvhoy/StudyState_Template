#!/usr/bin/env python3
"""Tests for scripts/template_ownership.py and core/ownership.json."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def ownership(*pairs: tuple[str, str]) -> own.Ownership:
    return own.Ownership(tuple((cls, pat.replace("**", "*")) for cls, pat in pairs))


def raises(exc: type[BaseException], fn, *args) -> bool:
    try:
        fn(*args)
    except exc:
        return True
    return False


def test_longest_pattern_wins() -> None:
    o = ownership(
        ("managed", "docs/**"),
        ("template_only", "docs/adr/**"),
        ("seeded", "state/**"),
        ("managed", "state/STATE_MANIFEST.yaml"),
    )
    assert o.classify("docs/setup.md") == "managed"
    assert o.classify("docs/adr/0001.md") == "template_only"
    assert o.classify("state/STUDY_STATE.yaml") == "seeded"
    assert o.classify("state/STATE_MANIFEST.yaml") == "managed"
    assert o.classify("unlisted.txt") is None


def test_equally_specific_classes_conflict() -> None:
    o = ownership(("managed", "a/*"), ("seeded", "b/*"))
    assert o.classify("a/x") == "managed"
    clash = ownership(("managed", "x/*.md"), ("seeded", "x/?.md"))
    # Same length, different classes, both match: ambiguous, never guessed.
    assert raises(own.OwnershipError, clash.classify, "x/a.md")


def test_the_real_template_is_fully_classified() -> None:
    o = own.load_ownership(ROOT)
    assert own.unclassified(ROOT, o) == [], "every shipped file needs an owner class in core/ownership.json"
    for rel in own.template_files(ROOT):
        o.classify(rel)  # raises on an ambiguous match


def test_no_dead_patterns() -> None:
    data = json.loads((ROOT / own.OWNERSHIP_PATH).read_text(encoding="utf-8"))
    files = own.template_files(ROOT)
    import fnmatch

    for cls, patterns in data["classes"].items():
        for pattern in patterns:
            glob = pattern.replace("**", "*")
            assert any(fnmatch.fnmatchcase(f, glob) for f in files), f"{cls} pattern {pattern!r} matches no file"


def test_ownership_file_is_validated() -> None:
    with tempfile.TemporaryDirectory(prefix="studystate-own-") as tmp:
        root = Path(tmp)
        (root / "core").mkdir()
        path = root / own.OWNERSHIP_PATH
        path.write_text("{not json", encoding="utf-8")
        assert raises(own.OwnershipError, own.load_ownership, root)
        path.write_text(json.dumps({"classes": {"managed": ["a"]}}), encoding="utf-8")
        assert raises(own.OwnershipError, own.load_ownership, root), "all four classes are required"
        path.write_text(json.dumps({"classes": {c: [""] for c in own.CLASSES}}), encoding="utf-8")
        assert raises(own.OwnershipError, own.load_ownership, root), "empty patterns are rejected"


def test_template_files_walk_skips_caches_without_git() -> None:
    with tempfile.TemporaryDirectory(prefix="studystate-own-") as tmp:
        root = Path(tmp)
        for rel in ("a.txt", "scripts/x.py", ".venv/lib/y.py", "scripts/__pycache__/x.pyc", ".studydd/context_pack.md", "n/.DS_Store"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("x", encoding="utf-8")
        assert own._walk(root) == ["a.txt", "scripts/x.py"]


def test_digest_ignores_line_endings_but_not_content() -> None:
    assert own.digest_bytes(b"a\r\nb\r\n") == own.digest_bytes(b"a\nb\n")
    assert own.digest_bytes(b"a\nb\n") != own.digest_bytes(b"a\nB\n")
    binary = b"\x00\r\n\x01"
    assert own.digest_bytes(binary) != own.digest_bytes(binary.replace(b"\r\n", b"\n")), "binary data is hashed as is"


def test_block_find_replace_roundtrip() -> None:
    text = "front\n\n" + own.render_block("1.0.0", "# Contract\n\nBody.\n") + "\n## Local rules\n\nMine.\n"
    block = own.find_block(text)
    assert block is not None and block.release == "1.0.0" and block.inner == "# Contract\n\nBody.\n"
    updated = own.replace_block(text, "1.1.0", "# Contract\n\nNew body.\n")
    assert updated.startswith("front\n\n") and updated.endswith("\n## Local rules\n\nMine.\n"), "text outside the block is untouched"
    assert "release=1.1.0" in updated and "Body.\n" not in updated.replace("New body.\n", "")
    assert own.find_block(updated).inner == "# Contract\n\nNew body.\n"
    assert own.block_digest("x\n") == own.block_digest("x\n")
    assert own.find_block("no markers at all\n") is None


def test_malformed_markers_are_rejected() -> None:
    start = "<!-- studystate:managed:start release=1 -->\n"
    end = own.BLOCK_END + "\n"
    for bad in (start + "no end\n", "no start\n" + end, start + start + end, end + start):
        assert raises(own.OwnershipError, own.find_block, bad), bad
    assert raises(own.OwnershipError, own.replace_block, "none\n", "1", "x\n")


def test_lock_roundtrip_is_deterministic() -> None:
    with tempfile.TemporaryDirectory(prefix="studystate-own-") as tmp:
        root = Path(tmp)
        assert own.read_lock(root) is None
        own.write_lock(root, "1.2.3", "abc", {"b.txt": "2", "a.txt": "1"}, "blockhash")
        first = (root / own.LOCK_PATH).read_text(encoding="utf-8")
        own.write_lock(root, "1.2.3", "abc", {"a.txt": "1", "b.txt": "2"}, "blockhash")
        assert (root / own.LOCK_PATH).read_text(encoding="utf-8") == first, "key order does not change the bytes"
        lock = own.read_lock(root)
        assert lock["template_version"] == "1.2.3" and lock["files"] == {"a.txt": "1", "b.txt": "2"}
        (root / own.LOCK_PATH).write_text("[]", encoding="utf-8")
        assert raises(own.OwnershipError, own.read_lock, root)


def test_scalar_readers_do_not_need_yaml() -> None:
    assert own.template_version(ROOT) == (own.template_version(ROOT).strip())
    assert own.read_mode(ROOT) == "template"
    with tempfile.TemporaryDirectory(prefix="studystate-own-") as tmp:
        assert own.read_mode(Path(tmp)) is None


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
    print("\nAll ownership tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
