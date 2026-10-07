# REVIEW_QUEUE — Spaced Repetition

> **Agent-maintained.** Add review items only when evidence shows a weak, partial, repaired, or shaky answer.

## Due now

- None. This public template has not been initialized for a learner yet.

## Scheduled

- None.

## Review item format

Each review item should include:

- **Review ID:**
- **Target ID:**
- **Skill ID:**
- **Evidence ID:**
- **Prompt:**
- **Due date:**
- **Interval days:**
- **Confidence/ease:**
- **Lapse count:**
- **Last result:**
- **Mistake type:** (see `protocols/MISTAKE_TAXONOMY.md`)
- **Review mode:** recall / scenario / explain / troubleshoot / choose-best

## Rules

- Schedule a review after every partial, incorrect, unclear, repaired, or shaky answer.
- Do not schedule a review for a single confident correct answer on a fresh skill.
- First interval after a weak answer: 0 or 1 day (see `protocols/SCHEDULE_REVIEW.md`).
- Correct recall with medium or high confidence: double the interval, capped by the target deadline or 30 days.
- Correct but low-confidence recall: repeat the interval.
- Lapse or partial: reset the interval to its shortest window and increment the lapse count.
- Record every completed review with `python3 scripts/schedule_review.py --review-id <id> --grade ... --confidence ...`.
- Choose a review mode that differs from the original question mode when possible.
