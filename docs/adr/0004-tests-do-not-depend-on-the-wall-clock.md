# ADR-0004: Tests do not depend on the wall clock

**Status:** accepted by the agent that made it; the owner's acceptance of the slice is pending
**Date:** 2026-10-07
**Author:** agent

## Context

The template has failed twice in the same way: a fixture recorded a fixed calendar date, a
check judged freshness against the real clock, and the suite passed only inside a 30-day window
(the demo fixture earlier in 2026; then three tests merged from an open pull request, which had
been green in June and failed in October). CI also listed tests by hand, so a passing test
(`test_create_instance.py`) was never run there.

## Decision

- `scripts/run_tests.py` discovers every `scripts/test_*.py` and runs each as its own process.
  CI and people use it, so a new test is picked up without editing the workflow.
- `scripts/run_tests.py --clock-offset-days N` moves `datetime.now()`, `utcnow()`, `date.today()`,
  and `time.time()` forward by N days in every Python process the tests start. CI runs the suite
  at 0 and at 400 days. The runner first checks, in a child process, that the shift took effect, so
  the offset run cannot pass by not shifting anything (an early version of the shim applied the
  offset twice to `date.today()`; that check is what found it).
- A test file that defines `test_` functions but has no runner is rejected, because it would exit 0
  without running them.
- A test pins its clock with `--now`, or builds timestamps relative to now.
- Test repositories disable git's detached auto-maintenance, which can still be writing into
  `.git` when a temporary directory is deleted.

## Consequences

- A fixed-date test that will rot fails in the next CI run instead of months later.
- The offset run doubles test time (about 30 seconds each).

## Alternatives Considered

- **A fake-time library.** A dependency for a stdlib problem; the shim is 30 lines.
- **Freeze time only for known tests.** The bug is the tests nobody knows are time-dependent.

## Related

- Slice: `template-hardening-001`
- Evidence: `evidence/template-hardening-001/summary.md`
