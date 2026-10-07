# StudyState Template

_Drafted by an agent from the owner's request of 2026-10-07 to make this the best template it can be. The owner owns this file and confirms or edits it._

## User

The owner, and the coding agents that maintain this template and cast learner instances from it. Learners are the end beneficiaries: they talk to an agent inside an instance and never use the template directly.

## Outcome

A learner can say "Start a StudyState session" in a repository cast from this template, and a coding agent runs one honest, evidence-gated learning cycle that resumes from files alone: one question is asked, the actual answer is graded, evidence is recorded, weak answers become spaced reviews that expand or reset as they are completed, and exactly one next action is written down. The template keeps every instance current without overwriting learner state.

## Scope

- The generic learning loop: protocols, study skills, activity templates, scripts, validators, and the public demo.
- The instance lifecycle: casting a learner instance, and updating it later with a mechanical update that refuses on local edits.
- The ProjectState v6 coordination core, for work on the mold and as the starting point of each new instance.
- The compatibility surfaces consumers rely on: the mode marker, the version file, documented script entry points, the `.studydd/` paths, and the lifecycle modes.

## Non-goals

- Holding any real learner, target, exam, evidence, or private data. That lives only in instances.
- A human-facing application, server, database, or UI.
- Being a runtime dependency: StudyState scripts never read or require ProjectState files.
- Renaming legacy `studydd` machine identifiers without a versioned migration.
- Merging the unmerged feature lines (fast-drill mode, the lifecycle-manifest work) without an owner decision.

## Durable constraints

- The owner owns this outcome, the non-goals, the acceptance criteria, and governance.
- The repository is public: generic and public-safe, with no machine paths and no private repository names.
- Readiness is never inflated; every progress claim in an instance needs evidence.
- Dependency installs need explicit consent; scripts stay cross-platform and use `pathlib`.
- Tests never depend on the wall clock.
