# SCHEDULE_REVIEW — Schedule Spaced Repetition

> **Agent action.** Add review items when evidence shows weakness.

## When To Schedule

Schedule a review when:

- answer is partial
- answer is incorrect
- answer is unclear and later resolved
- answer was repaired after a hint
- answer was correct but shaky or lucky
- the skill has not been tested in a long time and readiness may be stale

Do not schedule a review for:

- a single confident correct answer on a freshly learned skill
- a `confirmed` skill with recent strong evidence

## How To Schedule

Use `scripts/schedule_review.py` to create a machine-readable item in `reviews/REVIEW_STATE.yaml` and a human-readable mirror in `reviews/REVIEW_QUEUE.md`.

Example:

```bash
python3 scripts/schedule_review.py \
  --skill-id skill_example \
  --evidence-id ev_001 \
  --target-id target_example \
  --grade partial \
  --confidence low \
  --now "2026-06-24T18:30:00+02:00"
```

`due_at` must be a timezone-aware ISO 8601 timestamp.

## Record A Review Result

When the learner has reviewed an existing item, record the outcome. Do not
create a second item and do not edit `reviews/REVIEW_STATE.yaml` by hand.

```bash
python3 scripts/schedule_review.py \
  --review-id rev_skill_example_20260624_183000 \
  --grade correct \
  --confidence high
```

The script updates `last_reviewed_at`, `due_at`, `interval_days`, `lapses`, and
`last_result` in `reviews/REVIEW_STATE.yaml`, and refreshes the item's block in
`reviews/REVIEW_QUEUE.md`. `select_next_study_action.py` prints this command
for the item it recommends. Pass `--max-interval-days N` when the target's
deadline should cap the interval.

## Review Item Format

```markdown
- **Review ID:** R-YYYYMMDD-<target>-NNN
- **Target ID:**
- **Skill ID:**
- **Evidence ID:**
- **Prompt:**
- **Due date:**
- **Interval days:**
- **Confidence/ease:**
- **Lapse count:**
- **Last result:**
- **Mistake type:**
- **Review mode:** recall / scenario / explain / troubleshoot / choose-best
```

## Interval Guidance

The scheduler is a simple, transparent interval map. It never uses more than
the grade, the confidence, and the previous interval.

First schedule (a new review item):

- wrong + low confidence: same day (0 days)
- wrong + medium/high confidence: 1 day
- partial: 1 day
- correct + low confidence: 2 days
- correct + medium confidence: 4 days
- correct + high confidence: 7 days

When a review is recorded:

- correct + medium/high confidence: double the interval (at least 1 day), capped at 30 days or `--max-interval-days`
- correct + low confidence: repeat the interval; shaky recall earns a repeat, not growth
- partial or wrong: a lapse. Increment the lapse count and reset to the shortest window (0 or 1 day)
- past lapses stay in `lapses`, but do not cap later successes

`interval_days: 0` is valid: it means due again the same day.

A future algorithm (FSRS, SM-2) can replace this map once the review data is stable, without changing the file surface.

## Review Mode Selection

- **recall** — definition, list, or fact.
- **scenario** — application in a realistic situation.
- **explain** — why and how something works.
- **troubleshoot** — diagnose and fix a problem.
- **choose-best** — select the best option among plausible distractors.

Choose a different mode than the original evidence when possible.
