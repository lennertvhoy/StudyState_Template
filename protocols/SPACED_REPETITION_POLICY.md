# SPACED_REPETITION_POLICY — Time-Aware Review-First Doctrine

> **Agent action.** Apply this policy at the start of every StudyState session.

## Doctrine

**Due reviews are not reminders. They are learning debt.**

Spaced retrieval is one of the strongest learning principles available. The agent should treat a due or overdue review as the default next action, because reviewing at the point of forgetting produces better long-term retention than pushing forward with new material.

The rule:

> **Spaced repetition is the default. Human override is allowed. Silent neglect is not.**

## What the agent must do at session start

1. Build the context pack with `--task start_session` so the active study skill is loaded. This is a session-boundary operation.
2. Read the current date and time.
3. Read `reviews/REVIEW_STATE.yaml` and `state/CURRENT_CONTEXT.md`.
4. Count reviews whose `due_at` is now or in the past.
5. Run or perform the equivalent of `scripts/select_next_study_action.py`.
6. If any review is due or overdue, recommend review first.

During ordinary review execution, stay on the fast path: load only the relevant review item and skill. Do not scan the full review history or raw logs unless the review references are broken.

The active study skill may prefer certain review modes (e.g., scenario for IT certification, apply-to-new-passage for philosophy, recall for language learning).

## Recommended phrase

Use this language when recommending review:

```text
Recommended by StudyState: review first. You can override, but this is the highest-retention move.
```

## When new material is allowed

New material is acceptable only when one of the following is true:

- No reviews are due.
- The review load is small and the learner's deadline plan explicitly justifies new material.
- The learner explicitly overrides the review-first recommendation.
- The session is tagged low-energy and the agent selects a lighter review mode.
- The current target has an urgent deadline and the learner has made an explicit tradeoff.

## Override discipline

If the learner chooses not to do a due review, the agent must record an override in `reviews/REVIEW_OVERRIDES.md`:

- **Timestamp:** when the override happened
- **Learner:** learner identifier
- **Skipped review IDs:** which reviews were passed over
- **Reason:** learner's stated reason
- **Chosen action:** what the learner chose instead
- **Agent recommendation:** what the agent recommended
- **Next review recommendation:** when/how to revisit the skipped reviews

The agent must not shame the learner. It should explain the retention tradeoff briefly, accept the override, and move on.

## Low-energy and recovery modes

In low-energy mode, the agent may still pick a due review but should choose a lighter mode (recall or explain) and keep the session short. Recovery mode is allowed without review if the learner is stuck or frustrated.

## Machine-readable state

`reviews/REVIEW_STATE.yaml` is the reliable surface. Keep it in sync with `reviews/REVIEW_QUEUE.md`. Use `scripts/schedule_review.py` to add items with timezone-aware `due_at` timestamps and to record each completed review (`--review-id`), which expands or resets the interval. Never hand-edit an item's interval or due date.

## Limitation

The current scheduler uses a simple transparent interval map. It can later be replaced by FSRS, SM-2, or another algorithm once the review data is stable, without changing the agent behavior or file surface.
