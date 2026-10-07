"""Who owns which file: the template, or the learner instance.

A learner instance is cast from this template and then lives on its own. To keep
it current without overwriting learner state, every file the template ships has
exactly one owner class, declared in ``core/ownership.json``:

``managed``
    Template-owned. ``update_instance.py`` replaces it when the template changes.
``seeded``
    Copied once when the instance is created, instance-owned afterwards.
``composite``
    One file with two owners (``AGENTS.md`` holds a template-managed block inside
    instance-owned text; the version file is merged key by key).
``template_only``
    Maintenance material for the mold; never copied into an instance.

The longest matching pattern wins, so ``state/STATE_MANIFEST.yaml`` can be
``managed`` inside the ``seeded`` ``state/**``. ``*`` matches across ``/``.

This module is standard-library only so it runs wherever Python does.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

OWNERSHIP_PATH = "core/ownership.json"
LOCK_PATH = "state/TEMPLATE_LOCK.json"
VERSION_PATH = "state/STUDYDD_TEMPLATE_VERSION.yaml"
MODE_PATH = "state/STUDYDD_MODE.yaml"
AGENTS_PATH = "AGENTS.md"
CORE_BLOCK_PATH = "core/AGENTS.studystate.md"

CLASSES = ("managed", "seeded", "composite", "template_only")

BLOCK_START_RE = re.compile(r"^<!-- studystate:managed:start release=(\S+) -->[ \t]*$", re.MULTILINE)
BLOCK_END = "<!-- studystate:managed:end -->"
BLOCK_END_RE = re.compile(r"^" + re.escape(BLOCK_END) + r"[ \t]*$", re.MULTILINE)

SKIP_DIRS = {
    ".git", ".venv", ".studydd", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".worktrees", "node_modules",
}
SKIP_NAMES = {".DS_Store"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


class OwnershipError(ValueError):
    """The ownership file or a block marker is malformed."""


# --- digests ---------------------------------------------------------------


def digest_bytes(data: bytes) -> str:
    """sha256 of ``data``, ignoring CRLF versus LF in text files."""
    if b"\0" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


# --- line endings ----------------------------------------------------------


def read_text_eol(path: Path) -> tuple[str, str]:
    """Read UTF-8 text as LF, plus the file's line ending ("\\n" or "\\r\\n").

    A file that is uniformly CRLF (a Windows checkout) round-trips; one that mixes
    endings, or holds a lone CR, raises, so local text is never silently mangled.
    """
    data = path.read_bytes()
    crlf = data.count(b"\r\n")
    if data.count(b"\r") != crlf:
        raise OwnershipError(f"{path.name} has mixed or lone CR line endings; convert it to LF")
    if crlf and crlf != data.count(b"\n"):
        raise OwnershipError(f"{path.name} mixes CRLF and LF line endings; convert it to LF")
    return data.decode("utf-8").replace("\r\n", "\n"), "\r\n" if crlf else "\n"


def encode_text(text: str, eol: str) -> bytes:
    return (text.replace("\n", eol) if eol != "\n" else text).encode("utf-8")


# --- ownership -------------------------------------------------------------


@dataclass(frozen=True)
class Ownership:
    patterns: tuple[tuple[str, str], ...]  # (class, pattern)

    def matches(self, rel: str) -> list[tuple[str, str]]:
        return [(cls, pat) for cls, pat in self.patterns if fnmatch.fnmatchcase(rel, pat)]

    def classify(self, rel: str) -> str | None:
        """Owner class of ``rel`` (longest pattern wins), or None if unclassified."""
        found = self.matches(rel)
        if not found:
            return None
        best = max(len(pat) for _, pat in found)
        winners = {cls for cls, pat in found if len(pat) == best}
        if len(winners) > 1:
            raise OwnershipError(f"{rel} is matched equally well by classes {sorted(winners)}")
        return winners.pop()


def load_ownership(root: Path) -> Ownership:
    path = root / OWNERSHIP_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OwnershipError(f"cannot read {OWNERSHIP_PATH}: {exc}") from exc
    classes = data.get("classes")
    if not isinstance(classes, dict) or set(classes) != set(CLASSES):
        raise OwnershipError(f"{OWNERSHIP_PATH} must define exactly the classes {list(CLASSES)}")
    patterns: list[tuple[str, str]] = []
    for cls in CLASSES:
        entries = classes[cls]
        if not isinstance(entries, list) or not all(isinstance(p, str) and p for p in entries):
            raise OwnershipError(f"{OWNERSHIP_PATH} class {cls!r} must be a list of non-empty patterns")
        patterns.extend((cls, p.replace("**", "*")) for p in entries)
    return Ownership(tuple(patterns))


def _walk(root: Path) -> list[str]:
    files: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in SKIP_DIRS for part in rel.parts) or path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
            continue
        files.append(rel.as_posix())
    return files


def template_files(root: Path) -> list[str]:
    """Every file the template ships, as sorted POSIX paths relative to ``root``.

    Uses Git (tracked plus untracked-but-not-ignored) when ``root`` is a
    repository, so uncommitted work is classified too; otherwise walks the tree.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root, capture_output=True, check=False,
        )
    except OSError:
        return _walk(root)
    if result.returncode != 0:
        return _walk(root)
    listed = [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]
    return sorted({p for p in listed if (root / p).is_file() and not (root / p).is_symlink()})


def files_of_class(root: Path, ownership: Ownership, cls: str) -> list[str]:
    return [rel for rel in template_files(root) if ownership.classify(rel) == cls]


def unclassified(root: Path, ownership: Ownership) -> list[str]:
    return [rel for rel in template_files(root) if ownership.classify(rel) is None]


# --- the AGENTS.md managed block ------------------------------------------


@dataclass(frozen=True)
class Block:
    release: str
    inner: str          # text between the marker lines, LF, ends with a newline
    start: int          # offset of the start marker line
    end: int            # offset just past the end marker line (including its newline)


def find_block(text: str) -> Block | None:
    starts = list(BLOCK_START_RE.finditer(text))
    ends = list(BLOCK_END_RE.finditer(text))
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].end():
        raise OwnershipError("AGENTS.md has malformed studystate:managed markers (need exactly one start and one end)")
    start, end = starts[0], ends[0]
    inner = text[start.end():end.start()].lstrip("\n")
    stop = end.end()
    if text[stop:stop + 1] == "\n":
        stop += 1
    return Block(start.group(1), inner, start.start(), stop)


def render_block(release: str, inner: str) -> str:
    if not inner.endswith("\n"):
        inner += "\n"
    return f"<!-- studystate:managed:start release={release} -->\n{inner}{BLOCK_END}\n"


def replace_block(text: str, release: str, inner: str) -> str:
    block = find_block(text)
    if block is None:
        raise OwnershipError("AGENTS.md has no studystate:managed block")
    return text[: block.start] + render_block(release, inner) + text[block.end:]


def block_digest(inner: str) -> str:
    return digest_bytes(inner.encode("utf-8"))


# --- the instance lock -----------------------------------------------------


def read_lock(root: Path) -> dict | None:
    path = root / LOCK_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OwnershipError(f"cannot read {LOCK_PATH}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise OwnershipError(f"{LOCK_PATH} is malformed")
    return data


def write_lock(root: Path, version: str, commit: str, files: dict[str, str], block: str | None) -> None:
    data = {
        "format": 1,
        "template_version": version,
        "template_commit": commit,
        "agents_block_sha256": block,
        "files": dict(sorted(files.items())),
    }
    path = root / LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def template_version(root: Path) -> str:
    """The template's version, read without a YAML parser."""
    text = (root / VERSION_PATH).read_text(encoding="utf-8")
    match = re.search(r"^template_version:\s*[\"']?([^\"'\s#]+)", text, re.MULTILINE)
    if not match:
        raise OwnershipError(f"{VERSION_PATH} has no template_version")
    return match.group(1)


def read_mode(root: Path) -> str | None:
    path = root / MODE_PATH
    if not path.is_file():
        return None
    match = re.search(r"^mode:\s*[\"']?([A-Za-z_]+)", path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""
