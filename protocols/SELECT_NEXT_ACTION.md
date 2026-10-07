# SELECT_NEXT_ACTION — Choose The One Next Study Action

> **Agent action.** Use this protocol to pick exactly one next study action.

## Review-First Doctrine

> **Due reviews are not reminders. They are learning debt.**

Before choosing any new material, check the current time and `reviews/REVIEW_STATE.yaml`. If any review is due or overdue, strongly prefer that review.

> **Spaced repetition is the default. Human override is allowed. Silent neglect is not.**

## Context loading

Build the context pack with `--task start_session` or `--task schedule_review`. Include `state/CURRENT_CONTEXT.md`, `state/SKILL_MAP.yaml`, `reviews/REVIEW_STATE.yaml`, the active study skill, and the next activity recommendation with its auditable `Rule: ...` reason. Do not load full raw logs.

## Selection Priority

Choose the first item that applies:

1. **Due or overdue review item** — a review in `reviews/REVIEW_STATE.yaml` with `due_at <= now`. Use `scripts/select_next_study_action.py` to surface the best candidate.
2. **Blocked skill** — a skill in `state/SKILL_MAP.yaml` with status `blocked`.
3. **Weak skill with fresh evidence** — a `weak` skill that has not been re-tested since the last failure.
4. **Pending skill near the active focus** — a `pending` skill related to the current target.
5. **Practiced skill needing varied evidence** — a `practiced` skill that has only one correct answer on record.
6. **Confirmed skill needing maintenance** — only in mixed checkpoint sessions or when other items are exhausted.

Apply the active study skill when choosing question style, mode, and difficulty.

## Activity-type routing

After applying the selection priority above, use the shared decision logic surfaced by `scripts/plan_learning_activity.py` and `scripts/build_context_pack.py` to choose among the primary routing rules. The planner prints the rule that triggered the choice, and the context pack carries the same rule reason for tutor agents.

1. **Spaced-repetition review** (`spaced_review`) — due or overdue reviews first.
2. **Recent-info check** (`recent_info_check`) — if the active target is `moderate`/`volatile`/`live` and `sources/SOURCE_STATE.yaml` shows freshness as missing, stale, or unknown. Stable targets with `requires_recent_info_check: true` are treated as `moderate` for freshness checking. Fresh `sources/SOURCE_STATE.yaml` is the primary suppressor of repeated source-check recommendations; only `outcome: fresh` removes the need for another `recent_info_check`. The recent-activity fallback (skipping the check because one already appears in recent activities) applies only when source state is missing, not when it exists but is stale or unverified. Due reviews still win.
3. **Lab / practical exercise** (`practical_lab`) — if the active target/study skill is hands-on (e.g., `practical_lab`, `sysadmin`, `cloud`, `networking`) or matching templates mark it as best for this domain.
4. **Diagram / visual explanation** (`diagram_or_whiteboard`) — if the active target/study skill is conceptual (e.g., `philosophy`, `conceptual_understanding`) or matching templates mark it as best for this domain.
5. **Exam-style question** (`retrieval_question`) — if the target `type` is `certification` or `exam` and the skill is at least practiced (`readiness >= 40`).

**Fallback** — when none of the five categories clearly apply, use a focused retrieval question, paper exercise, or explain-back based on skill status.

The learner can accept, modify, or override the recommendation. Strong overrides are recorded in `state/EVIDENCE_LOG.md` and `activities/ACTIVITY_LOG.md`.

## Override Handling

If the learner wants to skip a due review, make the tradeoff explicit:

- Explain that spaced review is the highest-retention move.
- Accept the override without shame.
- Record the override in `reviews/REVIEW_OVERRIDES.md`.
- Increment `override_count` on the skipped review item in `reviews/REVIEW_STATE.yaml`.
- Propose when to revisit the skipped review.

## Match Session Mode

- **Deep mode** — pick the hardest due review, weak area, or a mixed checkpoint.
- **Normal mode** — pick one strong question from the highest priority item.
- **Low-energy mode** — pick one due review or a small recall/prompt question.
- **Recovery mode** — pick one concept to read or explain; no question required.

## Write To NEXT_ACTIONS.md

`NEXT_ACTIONS.md` must contain exactly one clear current next action. Move the previous current action to either:

- **Pending actions** if not done, or
- **Recently completed** with a date if done.

## What The Action Must Specify

- target ID
- skill ID
- question ID or review ID
- question type (recall, apply, troubleshoot, choose-best, explain, design)
- mode (deep, normal, low-energy, recovery)
- why this action was chosen
