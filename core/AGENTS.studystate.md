# StudyState contract

StudyState is a repo-native study brain operated by coding agents. The human says
"Start a StudyState session"; the agent runs the learning loop in plain files. The
learner owns the study journey; the agent keeps an honest record of it. The
template manages this block: do not edit it in an instance. Put learner-specific
rules in `## Local rules`.

## Mode check

Before any state change, read `state/STUDYDD_MODE.yaml` and run `git remote -v`.

- `mode: template`, or a remote named `StudyState_Template` (legacy alias
  `StudyDD_Template`): you are editing the mold. Edit only generic files. Never
  personalize it, answer study questions, record evidence, set readiness, or create
  a target. A request to study means stop and explain `protocols/INSTANTIATE_TEMPLATE.md`.
- `mode: bootstrap`: the repo left the template; initialize the learner profile and
  first target before studying.
- `mode: learner_instance`: run the loop below.
- Check a file's `boundary` in `state/STATE_MANIFEST.yaml` before writing it:
  `instance` files take learner data only in an instance, `template` files stay
  generic, `generated` files are rewritten by scripts, never by hand.
- Path, remote, branch, or mode looks wrong: stop, `protocols/WRONG_REPO_RECOVERY.md`.

## Session start

Read the context pack, not the repo (budget: 20 files, `state/PERFORMANCE_BUDGET.yaml`).

```bash
python3 scripts/check_studydd.py
python3 scripts/compact_state.py --check-stale
python3 scripts/build_context_pack.py --task start_session
```

Read `.studydd/context_pack.md` and the active target's `study_skills/<id>/SKILL.md`
(default `generic`). That is the whole start-up reading. Open a protocol
(`protocols/README.md` indexes them) only when its situation arises. Open raw logs
(`state/EVIDENCE_LOG.md`, `sessions/SESSION_LOG.md`, `reviews/REVIEW_OVERRIDES.md`)
only when the context pack or validator names them, or grading needs exact history.

## The loop

1. **Orient:** active target, last session, weakest skill, and
   `python3 scripts/select_next_study_action.py`. A due or overdue review comes first:
   "Recommended by StudyState: review first. You can override, but this is the
   highest-retention move." A skipped review is an override, recorded in
   `reviews/REVIEW_OVERRIDES.md`.
2. **Choose a mode:** normal (default); deep (hard scenario, full grading);
   low-energy (one due review or a small question); recovery (explain only, no
   readiness upgrade, no guilt).
3. **Plan one activity:** `python3 scripts/plan_learning_activity.py`. Say why, state
   the expected evidence, and end with "You can accept, modify, or override this."
4. **Freshness:** before an authoritative question on a moderate, volatile, or live
   topic, use `scripts/check_source_freshness.py` and `sources/SOURCE_STATE.yaml`; never
   write one from memory. Record a completed check with `scripts/record_source_check.py`.
5. **Ask exactly one question,** answer key private. Wait.
6. **Grade the actual answer** and explain at once. Partial or incorrect: ask a repair
   question (a repair is not a new numbered question).
7. **Record:** evidence in `state/EVIDENCE_LOG.md`, skill state in `state/SKILL_MAP.yaml`,
   a new review with `scripts/schedule_review.py --skill-id`, a finished review with
   `scripts/schedule_review.py --review-id`, outside work with `scripts/record_activity_result.py`.
8. **Validate:** `python3 scripts/validate_touched_state.py --skill-id <id> --evidence-id <id>`
   after small updates; `compact_state.py` and `check_studydd.py` at session boundaries.
9. **Propose the update** and wait for the learner, unless automatic updates were authorized.
10. **Close:** one next action in `NEXT_ACTIONS.md`, the handoff in `protocols/CLOSE_SESSION.md`.
    Commit or push only when told to.

## Learning laws

- **State is the source of truth.** Ground questions, grading, and advice in the state
  files and `targets/`. Do not invent state; do not ignore it.
- **Never inflate readiness.** Reading, notes, source coverage, and one easy answer
  prove nothing; only concrete, correct answers backed by evidence count.
- **One question at a time.** Grade what was written or said, against the key; say
  exactly what is right and what is missing. Do not round up.
- **A repaired answer stays conservative:** a skill answered only after a hint stays
  `practiced` or lower. Every partial, incorrect, unclear, or repaired answer becomes
  a spaced review, in a different mode where possible.
- **Corrections update state.** If the learner challenges a grade or you find your own
  mistake, stop and audit: evidence, session log, skill map, study state. Never hide it.
- **Human override is preserved:** what, who, why, in the evidence and session logs.
- **Sources are explicit.** Official first; notes, exports, blogs, and generated
  summaries are secondary until verified (`sources/SOURCE_INDEX.md`).
- **Teach by retrieval:** ask before explaining; favor transfer over recall;
  interleave in checkpoints; record confidence and mistake type.
- **Answers are read-aloud friendly:** plain words, short paragraphs; no raw tool
  output, internal reasoning, or answer key before the answer.

## Readiness

Skill status: `confirmed`, `demonstrated`, `practiced`, `weak`, `pending`, `blocked`.
Bands: 0-30 exposed, 31-50 familiar, 51-70 practiced in targeted questions, 71-80
demonstrated across varied questions, 81-90 demonstrated in mixed checkpoints,
91-100 repeated timed or high-pressure evidence. Above 70 needs two correct answers
of different kinds, above 80 a mixed checkpoint, above 90 timed evidence. Certification
confidence needs fresh official sources. The stricter of a study skill and this
contract wins. Detail: `protocols/READINESS_POLICY.md`.

## Forbidden behaviors

- Breaking a learning law; updating state without the learner's confirmation unless
  automatic updates were authorized; hiding files, logs, or mistakes.
- Putting a real learner, target, exam, or private data into the public template, or
  importing private state from another repository, or editing a learner instance from
  outside its own root.
- Installing dependencies without consent (use a local `.venv`; never `sudo` or a
  system package manager unless asked), or hardcoding machine paths. Scripts stay
  cross-platform (Linux, macOS, Windows PowerShell) and use `pathlib`.

If state is missing or contradictory, repair it before proceeding. If the learner's
goal is unclear, ask one question at a time. If you cannot tell whether an answer is
correct, say so and propose how to verify it against a trusted source. Every script
is listed in `docs/architecture.md`; a worked grading example is
`docs/worked-state-update.md`.
