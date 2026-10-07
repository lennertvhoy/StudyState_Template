#!/usr/bin/env python3
"""Run every ``scripts/test_*.py`` and report. Standard library only.

    python3 scripts/run_tests.py                          # all tests, real clock
    python3 scripts/run_tests.py --clock-offset-days 400  # all tests, clock 400 days ahead
    python3 scripts/run_tests.py --only review            # tests whose name contains "review"
    python3 scripts/run_tests.py --list

Each test runs as its own process, the same way a person or CI would run it, so a
test that only works inside a shared interpreter is caught. Discovery means a new
``test_*.py`` is run everywhere without editing CI.

``--clock-offset-days N`` moves ``datetime.now()``, ``utcnow()``, ``date.today()``
and ``time.time()`` forward by N days in every Python process the tests start. A
test that fixes a calendar date and then evaluates it on the real clock passes today
and fails later; the offset run finds those while they are cheap to fix.

Exit codes: 0 all passed; 1 a test failed; 2 bad usage or no tests found.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
DEFAULT_TIMEOUT_SECONDS = 600

CLOCK_SHIM = '''\
"""Shift the wall clock forward (injected by scripts/run_tests.py)."""
import datetime as _dt
import os
import time as _time

_days = float(os.environ.get("STUDYSTATE_CLOCK_OFFSET_DAYS", "0") or 0)
if _days:
    _delta = _dt.timedelta(days=_days)
    _datetime, _date = _dt.datetime, _dt.date

    # Every entry point is built on _datetime.now(), which reads the system clock
    # directly. CPython's date.today() and datetime.today() call time.time(), which is
    # patched below, so shifting them as well would apply the offset twice.
    class _ShiftedDateTime(_datetime):
        @classmethod
        def now(cls, tz=None):
            return _datetime.now(tz) + _delta

        @classmethod
        def utcnow(cls):
            return _datetime.utcnow() + _delta

        @classmethod
        def today(cls):
            return _datetime.now() + _delta

    class _ShiftedDate(_date):
        @classmethod
        def today(cls):
            return (_datetime.now() + _delta).date()

    _dt.datetime = _ShiftedDateTime
    _dt.date = _ShiftedDate
    _real_time = _time.time
    _time.time = lambda: _real_time() + _days * 86400
'''


def discover(only: str | None) -> list[Path]:
    tests = sorted(SCRIPTS.glob("test_*.py"))
    if only:
        tests = [t for t in tests if only in t.name]
    return tests


def runs_nothing(test: Path) -> bool:
    """True for a file that defines tests but would exit 0 without running any as a script."""
    text = test.read_text(encoding="utf-8")
    return "def test_" in text and "__main__" not in text


def run_one(test: Path, env: dict[str, str], timeout: int) -> tuple[bool, float, str]:
    started = time.monotonic()
    if runs_nothing(test):
        return False, 0.0, "defines test_ functions but has no `if __name__ == \"__main__\"` runner, so it would pass without running"
    try:
        result = subprocess.run(
            [sys.executable, str(test)], cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = "".join(part.decode("utf-8", "replace") if isinstance(part, bytes) else part for part in (exc.stdout, exc.stderr) if part)
        return False, time.monotonic() - started, f"timed out after {timeout}s\n{output}"
    return result.returncode == 0, time.monotonic() - started, result.stdout + result.stderr


def clock_is_shifted(env: dict[str, str], days: float) -> bool:
    """Ask a fresh child process what time it is; the shim must have moved it."""
    probe = (
        "import datetime, time; "
        "print(datetime.datetime.now(datetime.timezone.utc).timestamp(), time.time(), datetime.date.today().toordinal())"
    )
    result = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True, check=False)
    try:
        dt_now, time_now, ordinal = (float(part) for part in result.stdout.split())
    except ValueError:
        return False
    real = time.time()
    expected = days * 86400
    # Allow an hour of slack for slow starts and for date.today() being a local calendar day.
    return (
        abs(dt_now - (real + expected)) < 3600
        and abs(time_now - (real + expected)) < 3600
        and abs((ordinal - __import__("datetime").date.today().toordinal()) - days) <= 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the StudyState test scripts")
    parser.add_argument("--clock-offset-days", type=float, default=0.0, help="Shift the wall clock forward by N days")
    parser.add_argument("--only", help="Run only tests whose file name contains this text")
    parser.add_argument("--list", action="store_true", help="List the tests and exit")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Seconds allowed per test")
    parser.add_argument("--tail", type=int, default=40, help="Lines of output to show for a failing test")
    args = parser.parse_args(argv)

    tests = discover(args.only)
    if not tests:
        print("No tests found.", file=sys.stderr)
        return 2
    if args.list:
        for test in tests:
            print(test.relative_to(ROOT).as_posix())
        return 0

    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    with tempfile.TemporaryDirectory(prefix="studystate-clock-") as shim_dir:
        if args.clock_offset_days:
            (Path(shim_dir) / "sitecustomize.py").write_text(CLOCK_SHIM, encoding="utf-8")
            env["PYTHONPATH"] = shim_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            env["STUDYSTATE_CLOCK_OFFSET_DAYS"] = str(args.clock_offset_days)
            if not clock_is_shifted(env, args.clock_offset_days):
                print("Error: the clock shim did not take effect in a child process; the offset run would prove nothing.", file=sys.stderr)
                return 2
            print(f"Clock shifted forward by {args.clock_offset_days:g} days.")

        failures: list[str] = []
        started = time.monotonic()
        for test in tests:
            ok, seconds, output = run_one(test, env, args.timeout)
            print(f"{'PASS' if ok else 'FAIL'}  {test.name}  ({seconds:.1f}s)")
            if not ok:
                failures.append(test.name)
                lines = output.rstrip().splitlines()[-args.tail:]
                print("\n".join(f"      {line}" for line in lines))

    elapsed = time.monotonic() - started
    print("")
    if failures:
        print(f"{len(failures)} of {len(tests)} test scripts failed in {elapsed:.0f}s: {', '.join(failures)}")
        return 1
    print(f"All {len(tests)} test scripts passed in {elapsed:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
