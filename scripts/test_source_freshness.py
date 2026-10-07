#!/usr/bin/env python3
"""Tests for scripts/check_source_freshness.py.

Creates temporary SOURCE_STATE.yaml and TARGET.yaml fixtures and invokes the
freshness script via subprocess. No network calls are made.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from check_source_freshness import (
    VOLATILITY_MAX_AGE_DAYS,
    classify_source,
    target_freshness_summary,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_SRC = ROOT / "scripts" / "check_source_freshness.py"

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def run_script(tmp_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Copy the freshness script into tmp_root so ROOT resolves to tmp_root."""
    script_dst = tmp_root / "scripts" / "check_source_freshness.py"
    script_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT_SRC, script_dst)
    return subprocess.run(
        [sys.executable, str(script_dst), *args],
        cwd=tmp_root,
        capture_output=True,
        text=True,
        check=False,
    )


def write_source_state(tmp_root: Path, sources: list[dict]) -> None:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    state_path = tmp_root / "sources" / "SOURCE_STATE.yaml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        yaml.safe_dump({"metadata": {"template_version": "0.8.1"}, "sources": sources}, sort_keys=False),
        encoding="utf-8",
    )


def write_target(tmp_root: Path, target_id: str, volatility: str | None) -> None:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    target_dir = tmp_root / "targets" / target_id
    target_dir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": target_id,
        "type": "skill",
        "title": f"Test target {target_id}",
    }
    if volatility:
        data["volatility"] = volatility
    (target_dir / "TARGET.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def test_volatile_fresh_official_passes() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-fresh-") as tmp:
        tmp_root = Path(tmp)
        target_id = "demo-ai-search-exam"
        write_target(tmp_root, target_id, "volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "mslearn_ai_search_overview",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-24T10:00:00+00:00",
                }
            ],
        )

        result = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        print("--- test_volatile_fresh_official_passes stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Fresh usable sources:" in result.stdout
        assert "mslearn_ai_search_overview" in result.stdout
        assert "Stale sources:" in result.stdout
        assert "Unverified sources:" in result.stdout


def test_volatile_stale_source_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-stale-") as tmp:
        tmp_root = Path(tmp)
        target_id = "demo-ai-search-exam"
        write_target(tmp_root, target_id, "volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "old_blog_ai_search_notes",
                    "target_ids": [target_id],
                    "authority": "unverified",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-05-01T10:00:00+00:00",
                }
            ],
        )

        result = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        print("--- test_volatile_stale_source_fails stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode != 0, f"Expected non-zero exit, got {result.returncode}"
        assert "old_blog_ai_search_notes" in result.stdout
        assert "Stale sources:" in result.stdout


def test_stable_target_no_refresh_required() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-stable-") as tmp:
        tmp_root = Path(tmp)
        target_id = "stable-topic"
        write_target(tmp_root, target_id, "stable")
        # No sources at all.
        write_source_state(tmp_root, [])

        result = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        print("--- test_stable_target_no_refresh_required stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"


def test_no_web_search() -> None:
    """The script source must not import network/web-fetching modules."""
    source = SCRIPT_SRC.read_text(encoding="utf-8")
    forbidden = ["urllib", "http.client", "requests", "httpx", "aiohttp", "curl", "wget"]
    for name in forbidden:
        assert name not in source, f"Script imports or references network module: {name}"


def test_allow_stale_practice_only() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-allow-") as tmp:
        tmp_root = Path(tmp)
        target_id = "demo-ai-search-exam"
        write_target(tmp_root, target_id, "volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "old_blog_ai_search_notes",
                    "target_ids": [target_id],
                    "authority": "unverified",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-05-01T10:00:00+00:00",
                }
            ],
        )

        result = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--allow-stale",
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        print("--- test_allow_stale_practice_only stdout ---")
        print(result.stdout)
        if result.stderr:
            print("stderr:", result.stderr)
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        assert "Stale source allowed by override." in result.stdout
        assert "practice-only, not authoritative-current" in result.stdout


def test_now_deterministic() -> None:
    with tempfile.TemporaryDirectory(prefix="studydd-now-") as tmp:
        tmp_root = Path(tmp)
        target_id = "demo-ai-search-exam"
        write_target(tmp_root, target_id, "volatile")
        write_source_state(
            tmp_root,
            [
                {
                    "id": "mslearn_ai_search_overview",
                    "target_ids": [target_id],
                    "authority": "official",
                    "usable_for_questions": True,
                    "last_checked_at": "2026-06-24T10:00:00+00:00",
                }
            ],
        )

        result1 = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        result2 = run_script(
            tmp_root,
            "--target-id",
            target_id,
            "--now",
            "2026-06-24T12:00:00+00:00",
        )
        print("--- test_now_deterministic stdout 1 ---")
        print(result1.stdout)
        print("--- test_now_deterministic stdout 2 ---")
        print(result2.stdout)
        assert result1.returncode == 0
        assert result2.returncode == 0
        assert result1.stdout == result2.stdout


# ---------------------------------------------------------------------------
# target_freshness_summary unit tests (no subprocess, deterministic datetimes)
# ---------------------------------------------------------------------------


def _src(
    target_id: str = "target",
    checked_offset_days: float | None = None,
    usable_for_questions: bool = True,
    expires_at: str | None = None,
    freshness_window_days: int | None = None,
    authority: str = "official",
    volatility: str | None = None,
    source_id: str = "src1",
    last_checked_at: str | None = None,
) -> dict:
    source: dict = {
        "id": source_id,
        "target_ids": [target_id],
        "authority": authority,
        "usable_for_questions": usable_for_questions,
    }
    if checked_offset_days is not None:
        source["last_checked_at"] = (NOW - timedelta(days=checked_offset_days)).isoformat()
    if last_checked_at is not None:
        source["last_checked_at"] = last_checked_at
    if expires_at is not None:
        source["expires_at"] = expires_at
    if freshness_window_days is not None:
        source["freshness_window_days"] = freshness_window_days
    if volatility is not None:
        source["volatility"] = volatility
    return source


def _state(*sources: dict) -> dict:
    return {"sources": list(sources)}


def test_target_freshness_summary_missing_state() -> None:
    summary = target_freshness_summary("target", "volatile", None, NOW)
    assert summary.status == "missing"
    assert not summary.has_fresh_usable
    assert summary.fresh_count == 0
    assert "No source freshness state" in summary.reason

    summary_empty = target_freshness_summary("target", "volatile", _state(), NOW)
    assert summary_empty.status == "missing"


def test_target_freshness_summary_fresh_inside_window() -> None:
    summary = target_freshness_summary(
        "target", "volatile", _state(_src(checked_offset_days=3.0)), NOW
    )
    assert summary.status == "fresh"
    assert summary.has_fresh_usable
    assert summary.fresh_count == 1
    assert summary.best_authority == "official"


def test_target_freshness_summary_stale_outside_window() -> None:
    summary = target_freshness_summary(
        "target", "volatile", _state(_src(checked_offset_days=10.0)), NOW
    )
    assert summary.status == "stale"
    assert not summary.has_fresh_usable
    assert summary.stale_count == 1


def test_target_freshness_summary_malformed_timestamp() -> None:
    summary = target_freshness_summary(
        "target",
        "volatile",
        _state(_src(checked_offset_days=None, last_checked_at="not-a-timestamp")),  # type: ignore[arg-type]
        NOW,
    )
    assert summary.status == "unknown"
    assert summary.unknown_count == 1


def test_target_freshness_summary_stable_no_sources() -> None:
    summary = target_freshness_summary("target", "stable", _state(), NOW)
    assert summary.status == "missing"
    assert not summary.has_fresh_usable
    # Consumers (context pack / planner) map this stable+missing case to not_required.


def test_target_freshness_summary_stable_with_valid_source() -> None:
    summary = target_freshness_summary(
        "target", "stable", _state(_src(checked_offset_days=365.0)), NOW
    )
    assert summary.status == "fresh"
    assert summary.has_fresh_usable


def test_live_target_window_one_day() -> None:
    assert VOLATILITY_MAX_AGE_DAYS["live"] == 1
    fresh = target_freshness_summary(
        "target", "live", _state(_src(checked_offset_days=0.5)), NOW
    )
    assert fresh.status == "fresh"
    stale = target_freshness_summary(
        "target", "live", _state(_src(checked_offset_days=2.0)), NOW
    )
    assert stale.status == "stale"


def test_volatile_target_window_seven_days() -> None:
    assert VOLATILITY_MAX_AGE_DAYS["volatile"] == 7
    fresh = target_freshness_summary(
        "target", "volatile", _state(_src(checked_offset_days=3.0)), NOW
    )
    assert fresh.status == "fresh"
    stale = target_freshness_summary(
        "target", "volatile", _state(_src(checked_offset_days=10.0)), NOW
    )
    assert stale.status == "stale"


def test_moderate_target_window_thirty_days() -> None:
    assert VOLATILITY_MAX_AGE_DAYS["moderate"] == 30
    fresh = target_freshness_summary(
        "target", "moderate", _state(_src(checked_offset_days=15.0)), NOW
    )
    assert fresh.status == "fresh"
    stale = target_freshness_summary(
        "target", "moderate", _state(_src(checked_offset_days=35.0)), NOW
    )
    assert stale.status == "stale"


def test_freshness_window_days_override() -> None:
    source = _src(
        checked_offset_days=5.0,
        freshness_window_days=3,
        volatility="volatile",
    )
    status, reason = classify_source(source, NOW, "volatile")
    assert status == "stale"
    assert reason is not None

    summary = target_freshness_summary("target", "volatile", _state(source), NOW)
    assert summary.status == "stale"
    assert summary.stale_count == 1


def test_target_freshness_summary_multiple_sources_aggregate() -> None:
    summary = target_freshness_summary(
        "target",
        "volatile",
        _state(
            _src(source_id="fresh-official", checked_offset_days=1.0, authority="official"),
            _src(source_id="stale-blog", checked_offset_days=14.0, authority="unverified"),
            _src(source_id="not-usable", checked_offset_days=1.0, usable_for_questions=False),
            {"id": "no-ts", "target_ids": ["target"]},
            {"id": "bad-ts", "target_ids": ["target"], "last_checked_at": "oops"},
        ),
        NOW,
    )
    # unknown_count takes precedence over fresh/stale, but fresh usable still exists.
    assert summary.status == "unknown"
    assert summary.has_fresh_usable
    assert summary.fresh_count == 1
    assert summary.stale_count == 1
    assert summary.unverified_count == 1
    assert summary.missing_count == 1
    assert summary.unknown_count == 1
    assert summary.best_authority == "official"


def test_usable_for_questions_false_counts_unverified() -> None:
    summary = target_freshness_summary(
        "target",
        "volatile",
        _state(_src(checked_offset_days=0.5, usable_for_questions=False)),
        NOW,
    )
    assert summary.status == "unverified"
    assert summary.unverified_count == 1
    assert summary.fresh_count == 0
    assert not summary.has_fresh_usable


def test_expires_at_overrides_window() -> None:
    fresh = target_freshness_summary(
        "target",
        "volatile",
        _state(_src(expires_at=(NOW + timedelta(days=1)).isoformat())),
        NOW,
    )
    assert fresh.status == "fresh"
    assert fresh.has_fresh_usable

    stale = target_freshness_summary(
        "target",
        "volatile",
        _state(_src(expires_at=(NOW - timedelta(days=1)).isoformat())),
        NOW,
    )
    assert stale.status == "stale"
    assert stale.stale_count == 1
    assert not stale.has_fresh_usable


def main() -> int:
    tests = [
        test_volatile_fresh_official_passes,
        test_volatile_stale_source_fails,
        test_stable_target_no_refresh_required,
        test_no_web_search,
        test_allow_stale_practice_only,
        test_now_deterministic,
        test_target_freshness_summary_missing_state,
        test_target_freshness_summary_fresh_inside_window,
        test_target_freshness_summary_stale_outside_window,
        test_target_freshness_summary_malformed_timestamp,
        test_target_freshness_summary_stable_no_sources,
        test_target_freshness_summary_stable_with_valid_source,
        test_live_target_window_one_day,
        test_volatile_target_window_seven_days,
        test_moderate_target_window_thirty_days,
        test_freshness_window_days_override,
        test_target_freshness_summary_multiple_sources_aggregate,
        test_usable_for_questions_false_counts_unverified,
        test_expires_at_overrides_window,
    ]

    failures = 0
    for test in tests:
        print(f"\nRunning {test.__name__}...")
        try:
            test()
            print("  PASSED")
        except AssertionError as exc:
            print(f"  FAILED: {exc}")
            failures += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            failures += 1

    if failures:
        print(f"\n{failures} test(s) failed.")
        return 1

    print("\nAll source freshness tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
