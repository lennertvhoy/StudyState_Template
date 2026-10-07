"""Shared state-file helpers: timestamps and comment-preserving YAML.

State files document themselves in a leading comment block. ``yaml.safe_dump``
drops comments, so every script that rewrites a state file writes through
:func:`save_yaml`, which carries the header across the rewrite.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_timestamp(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp; naive values are read as UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Error reading {path}: {exc}")
        sys.exit(1)


def _leading_comment_block(text: str) -> str:
    """Return the comment and blank lines before the first YAML key."""
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == "---":
            continue
        if stripped == "" or stripped.startswith("#"):
            kept.append(line)
            continue
        break
    return "".join(kept)


def save_yaml(path: Path, data: dict) -> None:
    """Write ``data`` as YAML, keeping the file's leading comment block.

    ``yaml.safe_dump`` drops comments; a state file's header is its in-place
    documentation, so it is carried across the rewrite.
    """
    import yaml

    header = ""
    if path.is_file():
        header = _leading_comment_block(path.read_text(encoding="utf-8"))
    body = yaml.safe_dump(data, sort_keys=False)
    path.write_text(header + body, encoding="utf-8", newline="\n")
