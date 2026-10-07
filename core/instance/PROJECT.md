# Study Instance

## User

Not yet defined — the learner and the owner of this repository must say who studies here.

## Outcome

Not yet defined — the human must state the observable result the learner wants, for example a certification passed, an interview prepared, or a skill demonstrably practiced.

## Scope

- The learner's active targets, their skill maps, and the evidence behind every readiness claim.
- The agent-operated session loop: verify, read, choose, ask, grade, update, validate, hand off.
- Spaced reviews, source tracking, and the single next action.

## Non-goals

- A human-facing application: no server, database, or UI.
- Inflating readiness: reading, notes, source coverage, or one easy answer do not prove mastery.
- Sending learner data anywhere without the learner's explicit go for that exact action.

## Durable constraints

- The learner owns the study journey and may accept, modify, or override any recommendation; overrides are recorded.
- Every progress claim is grounded in `state/EVIDENCE_LOG.md` or `sessions/SESSION_LOG.md`.
- ProjectState coordination files (`PROJECT.md`, `STATE.yaml`, `evidence/`) are never read or required by StudyState scripts at runtime.
- The human owns this file and the slice acceptance criteria.
