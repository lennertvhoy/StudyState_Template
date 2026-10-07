# LEARNING_ACTIVITY_POLICY — StudyState Learning Activity Orchestrator

> **Agent rule.** A question is one teaching move, not the whole system.

## Doctrine

```text
StudyState recommends the best next learning activity, explains why,
lets the learner accept/modify/override, and records evidence from the result.
```

Questions are useful, but they are not always the best next move. Sometimes the learner needs a paper exercise, a video, a lab, a diagram, an interview rehearsal, a presentation rehearsal, a voice note, or an external-platform drill. The agent's job is to choose the activity that is most likely to produce evidence of competence given the current state.

When `sources/SOURCE_STATE.yaml` shows freshness as missing, stale, or unknown for a `moderate`, `volatile`, or `live` target, the agent recommends a `recent_info_check` activity. The learner verifies current facts, sources, or exam objectives and submits source metadata or a short summary before the agent builds authoritative questions. When the check is complete, record the activity result with `scripts/record_activity_result.py` and pass `--source-id` (plus the relevant source metadata flags); the script writes the source check back to `sources/SOURCE_STATE.yaml` automatically via `scripts/record_source_check.py` so future plans see the freshness signal.

## Inputs the agent must consider

When planning the next activity, inspect:

- Due or overdue reviews (`reviews/REVIEW_STATE.yaml`, `scripts/select_next_study_action.py`).
- Weak or blocked skills (`state/SKILL_MAP.yaml`).
- Learner energy and session mode (`protocols/LOW_ENERGY_MODE.md`).
- Learner preferences (`state/LEARNER_PROFILE.yaml`, `activities/ACTIVITY_STATE.yaml`).
- Target requirements and deadlines (`targets/<id>/TARGET.yaml`).
- Active study skill (`study_skills/<id>/SKILL.md`).
- Source freshness for the active target (`protocols/SOURCE_FRESHNESS_POLICY.md`).
- Recent mistake patterns (`state/EVIDENCE_INDEX.yaml`, `scripts/suggest_study_adjustment.py`).
- Recent activity effectiveness (`activities/ACTIVITY_LOG.md`, `state/ACTIVITY_STATE.yaml`).
- Available evidence types for the target (photo, screenshot, command output, transcript, etc.).

## Decision principle

Choose the activity that:

1. clears due learning debt first (spaced review),
2. repairs the weakest skill next,
3. matches the learner's energy,
4. produces evidence the learner can actually submit,
5. respects source freshness for volatile topics,
6. varies the activity type when the learner has repeatedly missed the same skill in chat questions.

`recent_info_check` is the right choice when the target is `moderate`, `volatile`, or `live` and `sources/SOURCE_STATE.yaml` shows freshness as missing, stale, or unknown.

A chat question is the default when nothing else is clearly better. It is not the only choice.

## Recommendation format

Every activity recommendation must include:

- **Type:** one of the supported activity types from `activities/ACTIVITY_TEMPLATES.yaml`.
- **Reason:** why this activity is better than alternatives.
- **Rule ID:** the stable decision identifier when produced by `scripts/next_activity_decision.py`.
- **Task:** a concise description of what the learner should do.
- **Expected evidence:** what the learner will submit for review.
- **Learner control:** the exact phrase: `You can accept, modify, or override this.`

`scripts/plan_learning_activity.py` and `scripts/build_context_pack.py` must use the same shared decision logic so the tutor context pack shows the same activity type, expected evidence, and auditable `Rule: ...` reason that the planner prints.

## Learner control

The learner can:

- **accept** the recommendation,
- **modify** the activity (e.g., choose a different resource or shorter task),
- **override** the recommendation with a different activity.

Strong overrides must be recorded in `state/EVIDENCE_LOG.md` and `activities/ACTIVITY_LOG.md` with the learner's reason. Readiness does not change from an override; it changes only from submitted evidence.

## Activity state

`state/ACTIVITY_STATE.yaml` tracks the active activity and recent activity history. It is canonical state, not an audit log. The append-only audit trail lives in `activities/ACTIVITY_LOG.md`.

## No readiness inflation

Effort, completion, and time spent can be acknowledged, but readiness only changes when submitted evidence demonstrates competence. A learner who watched a video, completed a lab, or rehearsed a talk has done useful work; they are not yet stronger until the evidence shows it.

## External resources

When recommending a video, reading, or external platform, follow `protocols/EXTERNAL_RESOURCE_POLICY.md`. Recommend one good resource with a clear reason, not a dump of links.

## Strong recommendation overrides

If the agent makes a strong recommendation and the learner overrides it, record:

- the recommended activity type and reason,
- the learner's chosen activity,
- the learner's reason,
- the expected evidence.

This keeps the study state honest when the learner chooses a different path.
