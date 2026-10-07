# ADR-0003: Close the open loops in the learning core

**Status:** accepted by the agent that made it; the owner's acceptance of the slice is pending
**Date:** 2026-10-07
**Author:** agent

## Context

Running the loop end to end, as an agent would, found four places where the documented
behaviour and the code disagreed or ended:

1. **Reviews were created but never completed.** `schedule_review.py` could only append a new
   item. Nothing recorded a finished review, although `reviews/REVIEW_QUEUE.md` promised
   "correct recall: double the interval" and "lapse: increment the lapse count". The lapse
   argument of the interval function was never passed.
2. **A documented call produced state the validator rejected.** A wrong, low-confidence
   answer gets a same-day interval of `0` (`protocols/SCHEDULE_REVIEW.md`), but
   `check_studydd.py` required `interval_days > 0`.
3. **Source checks were demanded but never recorded.** The router sends a stale volatile
   target to `recent_info_check`, and the validator fails a volatile target with no fresh
   source, but no script wrote the result back, so an agent had to hand-edit
   `sources/SOURCE_STATE.yaml`. An open pull request (the source-check completion flow, green on
   three operating systems) already contained the writer.
4. **The fast path could not pass its own check.** `UPDATE_STATE.md` says to validate the
   touched evidence ID without compacting; `validate_touched_state.py --evidence-id` looked
   only in the derived index, which only compaction builds, so a fresh append always failed.

Two smaller defects shared a cause. The selector rewrote `reviews/REVIEW_STATE.yaml` on every
call (dropping its comments, and dirtying the worktree on a read), and the scheduler appended
later review items below the rules section of the queue file.

## Decision

- `schedule_review.py --review-id` records a review result. A correct recall with medium or
  high confidence doubles the interval (at least 1 day, capped at 30 days or
  `--max-interval-days`). A correct but low-confidence recall repeats it: shaky recall earns a
  repeat, not growth. A partial or wrong answer is a lapse: it counts, and resets the interval
  to its shortest window. Past lapses do not cap later successes. The rules live in
  `scripts/review_state.py` and `protocols/SCHEDULE_REVIEW.md`.
- `interval_days: 0` is valid. The validator accepts any non-negative number.
- `record_source_check.py` and its tests, the template/instance boundary check, and the wiring in
  `record_activity_result.py` come from the open pull request, merged by hand against current main,
  with its clock-dependent tests made relative to now and its shared helpers moved to `state_io.py`.
  A learner datum in the template is now a validator error, not a warning.
- The fast-path validator falls back to one targeted parse of the audit log when an ID is not in
  the index, and says that the index is stale.
- State writers keep a file's leading comment block (`scripts/state_io.py`), and the selector
  writes only when a status actually changed. `REVIEW_STATE.yaml` documents its schema at the top
  so the documentation survives rewrites.

## Consequences

- The loop can be run end to end by scripts: ask, grade, record, review, reschedule, check a
  source. `scripts/test_instance_journey.py` does so.
- The interval rule is deliberately simple and transparent. FSRS or SM-2 can replace it behind the
  same file surface once real review data exists (`protocols/SPACED_REPETITION_POLICY.md`).
- Open feature lines that exist only on remote branches (fast-drill mode, a lifecycle manifest with
  portable actions, a transactional-hardening branch) were **not** merged: they are product
  decisions for the owner, not defects.

## Alternatives Considered

- **Make the scheduler's `0` a `1`.** Hides the policy ("same day") to satisfy a validator that was
  too strict.
- **Persist no status at all.** The context pack and validators show `status`; refreshing it only
  when it changes keeps those views honest without churn.
- **Run compaction on every fast-path turn.** Defeats the fast path.

## Related

- Slice: `template-hardening-001`
- Evidence: `evidence/template-hardening-001/summary.md`
