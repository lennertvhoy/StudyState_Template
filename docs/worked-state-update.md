# Worked State-Update Example

One question, graded honestly, with the state update it justifies. The skill and
question are invented. This shows the discipline; it is not a default target.

## Scenario

- Skill ID: `example-search-rag`
- Skill label: "Search and retrieval-augmented generation"
- Previous status: `pending`, readiness 0
- Active question ID: `Q-20260624-001`
- Question: "What is the difference between keyword search and vector search, and when would you combine them?"
- Cognitive level: explain
- Expected answer format: a short paragraph with a concrete scenario
- Answer key (private until the learner answers): keyword search is term matching, vector
  search is semantic similarity, and hybrid search combines both for relevance
- Common traps: calling keyword search "dumb" instead of term matching; forgetting a concrete scenario

## Learner answer

> Keyword search looks for exact words, while vector search finds similar meanings. I would
> combine them when a user query might miss the exact product name but describes what they want.

## Grading

Verdict: **partial**.

- Correct: the keyword versus vector distinction, and combining them for better relevance.
- Missing: no concrete scenario and no target-specific implementation detail.
- Mistake type: `correct-concept-weak-implementation`

## Repair question

"Describe one concrete configuration choice you would make when setting up a hybrid
retrieval pipeline."

The learner answers correctly: an index with both text and vector fields, and a query that
requests both retrieval types. A repair is not a new numbered question; once it is resolved,
the original question is closed.

## Evidence recorded

Appended to `state/EVIDENCE_LOG.md`:

```markdown
- **Date:** 2026-06-24
- **Target ID:** example-target
- **Skill ID:** example-search-rag
- **Question ID:** Q-20260624-001
- **Evidence ID:** ev_example_001
- **Question summary:** Difference between keyword and vector search and when to combine them.
- **Learner answer summary:** Correct distinction; concrete hybrid configuration added after the repair question.
- **Verdict:** partial -> correct after repair
- **Mistake type:** correct-concept-weak-implementation
- **Explanation:** The first answer was conceptually right but lacked target-specific detail. The repair question showed applied understanding.
- **Confidence:** medium
```

## State update proposal

Do not mark `example-search-rag` as `confirmed` after one question. Understanding shown after
a repair is good evidence but not mastery.

- `state/SKILL_MAP.yaml`: status `practiced`, readiness `55`, confidence `medium`, the evidence
  reference added, the next validation question updated.
- `state/STUDY_STATE.yaml`: the active focus points at the next, varied validation question.
- `reviews/REVIEW_STATE.yaml` and `reviews/REVIEW_QUEUE.md`: a review, because the first answer
  had a mistake.

  ```bash
  python3 scripts/schedule_review.py --skill-id example-search-rag --evidence-id ev_example_001 \
    --target-id example-target --grade partial --confidence medium
  ```

  When the learner later does that review, record the result so the interval grows or resets:

  ```bash
  python3 scripts/schedule_review.py --review-id <the id it printed> --grade correct --confidence high
  ```
- `sessions/SESSION_LOG.md`: a session entry with the focus, question, result, evidence, and the
  proposed state changes.
- `NEXT_ACTIONS.md`: the single next action. `state/STUDY_STATUS.md`: the refreshed summary.

Then validate the touched records and wait for the learner's confirmation before writing,
unless automatic updates were authorized:

```bash
python3 scripts/validate_touched_state.py --skill-id example-search-rag --evidence-id ev_example_001
```
