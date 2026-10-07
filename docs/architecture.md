# Architecture

The map of the repository: what each directory holds and what each script does.
The agent's contract is `AGENTS.md`; the protocols in `protocols/` hold the detail
for one situation each (`protocols/README.md` indexes them).

## The model

StudyState keeps learning state as plain Markdown and YAML in a Git repository. A
coding agent operates it; nothing lives in an app database or a chat history.

- **State is files.** Canonical state is small and machine-readable. Audit logs are
  append-only. Summaries and indexes are derived and can be regenerated.
- **The agent reads a context pack, not the repo.** `build_context_pack.py` assembles
  the compact runtime context for one task; raw logs are opened only to audit.
- **Evidence gates readiness.** A skill moves only when a graded answer or recorded
  outside activity supports it.
- **Reviews are learning debt.** A weak answer becomes a spaced review; a completed
  review grows or resets its interval.
- **The mold and the cast are separate.** This repository is the template; learner
  instances are cast from it and updated from it (`docs/UPGRADING.md`).

## Directories

| Path | Holds | Owner after casting |
| --- | --- | --- |
| `state/` | learner profile, skill map, evidence, status, mode and version markers | the instance (the manifest is template-owned) |
| `targets/` | one folder per study target: `TARGET.yaml`, question banks | the instance |
| `reviews/` | the spaced-repetition queue and override log | the instance |
| `sessions/` | session log and generated summaries | the instance |
| `sources/` | source registry and freshness state | the instance |
| `activities/` | activity templates (template-owned) and the activity log (instance) | both |
| `study_skills/` | per-domain tutoring policy, one `SKILL.md` each | the template |
| `protocols/` | operating rules for the agent | the template |
| `PROMPTS/` | paste-ready prompts for coding agents | the template |
| `scripts/` | the tooling below | the template |
| `docs/` | guides and this map | the template |
| `EXAMPLES/` | reference states, never defaults | the template |
| `.github/` | CI workflow (template), issue and PR templates (seeded) | mixed |
| `PROJECT.md`, `STATE.yaml`, `evidence/` | ProjectState coordination for work on the repository | the instance |

`core/ownership.json` (template only) classifies every file as `managed`,
`seeded`, `composite`, or `template_only`. `docs/UPGRADING.md` explains what that
means for an instance.

## Scripts

Every script runs as `python3 scripts/<name>.py` and prints its flags with `--help`.

**Health and context**

- `check_studydd.py` is the repository health and educational-drift validator.
- `agent_preflight.py` gives a quick orientation; `agent_consistency_check.py` and
  `agent_evidence_check.py` cross-check state files and evidence references.
- `compact_state.py` turns the append-only logs into summaries and indexes;
  `build_context_pack.py` builds `.studydd/context_pack.md` for a task.
- `validate_touched_state.py` is the fast-path check for the IDs one turn touched;
  `plan_state_update.py` prints the files an operation is expected to touch.
- `check_environment.py` and `setup_studydd.py` check and prepare a machine; setup
  installs nothing without explicit consent.

**Choosing and recording**

- `select_next_study_action.py` recommends review first when reviews are due.
- `plan_learning_activity.py` and `next_activity_decision.py` choose the next activity;
  they share one decision function, so the context pack and the planner agree.
- `schedule_review.py` creates a review, or records a review result with `--review-id`;
  `review_state.py` holds the interval rules.
- `check_source_freshness.py` evaluates freshness; `record_source_check.py` records a
  completed check.
- `record_activity_result.py` records work done outside the chat, including a source check.
- `lint_questions.py` lints question banks; `suggest_study_adjustment.py` proposes at
  most one adaptation from recent evidence; `analyze_voice_note.py` and
  `analyze_presentation_rehearsal.py` analyze transcripts without dependencies.
- `state_io.py` holds the timestamp and comment-preserving YAML helpers the writers share.

**Instances and privacy**

- `create_instance.py` casts a learner instance from the template.
- `update_instance.py` brings an instance up to the template's release (template only).
- `agent_privacy_check.py` is a practical privacy scan to run before pushing an instance.
- `run_demo_replay.py` is the public demo of one full learning loop with fake data.

**Template maintenance (template only)**

- `template_release.py` checks and syncs the contract block, ownership, version, and changelog.
- `template_ownership.py` (shipped) is the ownership and lock library.
- `projectstate_gate.py` is the vendored ProjectState gate; update it with ProjectState's own tool.

**Tests**

- `run_tests.py` runs every `test_*.py`; `--clock-offset-days N` runs them in the future.
- `test_instance_journey.py` is the primary journey: cast, study, review, source check, update.
- `testkit.py` holds shared helpers; the other `test_*.py` files each cover one area.

## Generated files

Safe to regenerate, never hand-edited with learner data:
`.studydd/context_pack.md`, `.studydd/state_cache.json` (gitignored),
`state/CURRENT_CONTEXT.md`, `state/EVIDENCE_INDEX.yaml`, `sessions/SESSION_SUMMARIES.md`,
and `state/TEMPLATE_LOCK.json` (written by `create_instance.py` and `update_instance.py`).

## Lifecycle references

- **Naming and compatibility**: `docs/naming-and-compatibility.md`. Public name is StudyState;
  machine identifiers keep their legacy `studydd` spellings until a versioned migration.
- **StatePort integration**: `docs/stateport-integration.md`. Which contracts must stay stable.
- **Create an instance**: `python3 scripts/create_instance.py`, or `protocols/INSTANTIATE_TEMPLATE.md`.
- **Update an instance**: `docs/UPGRADING.md` and `protocols/UPGRADE_INSTANCE_FROM_TEMPLATE.md`.
- **Git provenance, privacy, wrong repo**: `protocols/GIT_PROVENANCE.md`,
  `protocols/PRIVACY_REVIEW.md`, `protocols/WRONG_REPO_RECOVERY.md`.
- **CI**: `.github/workflows/validate.yml` runs `run_tests.py`, the validator, and the demo.
