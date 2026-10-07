# StudyState_Template

[![Validate](https://github.com/lennertvhoy/StudyState_Template/actions/workflows/validate.yml/badge.svg)](https://github.com/lennertvhoy/StudyState_Template/actions/workflows/validate.yml)

**Repo-native study brain for coding agents.**

StudyState is not a human-facing app. It is a study brain that a coding agent (Codex, Claude
Code, Kimi Code, Cursor, or similar) operates inside a Git repository. You say "Start a
StudyState session"; the agent runs the learning loop and keeps your study library, tutor
memory, readiness tracker, spaced-repetition queue, source registry, and next action in plain
Markdown and YAML. Your progress is never hidden in an app database or a chat history.

This repository is the **mold**. You do not study in it: you cast your own learner instance
from it, and the template can later bring that instance up to date without touching your state.

## Why this exists

AI tutors are useful, but they often forget what you know, inflate readiness after one easy
answer, lose track of weak areas, grade against the answer they expected, and make mistakes
they never record. StudyState makes learning state explicit, evidence-based, and auditable.

- **Readiness is earned.** A skill moves only on a graded answer or recorded outside work. One
  good answer makes a skill `practiced`, not `confirmed`; a repaired answer stays conservative.
- **Sources are tracked and kept fresh.** Volatile topics (cloud services, vendor exams, pricing)
  need fresh official sources before an authoritative question. A stale target routes to a source
  check, and the recorded check ends the routing.
- **Due reviews are learning debt.** A weak answer becomes a spaced review; a finished review
  doubles or resets its interval. A skipped review is an override, recorded, never ignored.
- **The agent reads a context pack, not the repo.** Start-up reads the contract, the context pack, and
  one study skill; raw logs stay for audit. The fast path validates only the records a turn touched.
- **The learner stays in control.** Every recommendation can be accepted, modified, or overridden,
  and the override is part of the record.

## Start

You need Python 3.10 or newer, Git, and a coding agent. PyYAML is the only dependency, and
nothing installs without your consent (`docs/setup.md`).

1. **Get the template.** Click "Use this template" on GitHub, or clone it. Any name works.

   ```bash
   git clone https://github.com/lennertvhoy/StudyState_Template.git
   cd StudyState_Template
   ```

2. **Cast your own instance** from that checkout. Do not study inside the template itself.

   ```bash
   python3 scripts/create_instance.py \
     --target ../Study_Me \
     --remote https://github.com/example/Study_Me.git
   ```

   `--remote` is optional; it is where you may later push. Nothing is pushed.

3. **Open `../Study_Me` in your coding agent,** paste `PROMPTS/coding_agent_start_prompt.md`, and
   tell it what you want to learn:

   > Initialize this StudyState instance for me. I want to prepare for a certification exam. Ask me
   > only the essential setup questions first.

The agent verifies the repository, builds a compact context pack, recommends one activity, asks one
question, grades your actual answer, records evidence, schedules a review if the answer was weak,
and writes the next action. See `docs/agent-native-quickstart.md`.

## A session

1. **Orient:** active target, weakest skill, and the review-first selector.
2. **Plan one activity** and say why: a question, a review, a paper exercise, a lab, an interview or
   presentation rehearsal, a voice note, a reading task, or an upload to review.
3. **Check freshness** for volatile topics before an authoritative question.
4. **Ask one question; grade the actual answer;** repair if partial.
5. **Record** evidence, skill state, and a review; validate the touched records.
6. **Close** with one next action and a truthful handoff.

The agent chooses the next activity by fixed, auditable rules, and says which rule fired:

1. Due or overdue reviews come first.
2. A stale, missing, or unknown source for a moderate, volatile, or live target means a `recent_info_check`.
3. A hands-on skill (lab, cloud, sysadmin, networking) or a conceptual one (philosophy) gets a lab or diagram.
4. A certification target with a practiced skill gets an exam-style question.
5. Otherwise a focused retrieval question, paper exercise, or explain-back.

Study skills (`study_skills/<id>/SKILL.md`) adapt the tutoring to the target: IT certification,
philosophy, primary maths, language learning, interview preparation, and practical labs differ in
question style, grading, and evidence. A target declares one with `study_skill:` in `TARGET.yaml`.

## Three modes

`state/STUDYDD_MODE.yaml` says which one a repository is in.

| Mode | Meaning |
| --- | --- |
| `template` | the reusable mold. Generic and public-safe: no learner, no evidence, no private data. |
| `bootstrap` | a freshly cast instance whose learner profile and first target are not initialized yet. |
| `learner_instance` | a personal study repo with a profile, targets, evidence, sessions, reviews, and a next action. |

## Stay current

When the template improves, bring an instance up to date from this checkout:

```bash
python3 scripts/update_instance.py --target ../Study_Me           # dry run
python3 scripts/update_instance.py --target ../Study_Me --apply
```

It replaces only template-owned files and the template's block in the instance's `AGENTS.md`,
refuses to overwrite a file you edited, and never touches your state, targets, reviews, sessions,
sources, or local rules. `docs/UPGRADING.md` explains the report, the refusals, and the one-time
conversion of an instance cast before 0.12.0. `CHANGELOG.md` states each release's instance action.

## The coordination core

The template and every instance it casts follow the ProjectState v6 core: a human-owned
`PROJECT.md`, one current slice in `STATE.yaml`, an evidence summary in `evidence/<slice>/`, and a
small gate, `python3 scripts/projectstate_gate.py`. A failed primary journey outranks passing
secondary checks. In an instance this coordinates work on the repository; the learner's study
state lives in `state/`. The gate fails on a fresh instance until the outcome and first journey are
recorded, which is honest. StudyState scripts never read or require these files at runtime.

## Maintaining the template

Read `core/MAINTAINING.md` first, then the decisions in `docs/adr/`.

```bash
python3 scripts/test_instance_journey.py            # the primary journey: cast, study, review, source check, update
python3 scripts/run_tests.py                        # every test, real clock
python3 scripts/run_tests.py --clock-offset-days 400  # every test, 400 days in the future
python3 scripts/template_release.py check           # contract block, file ownership, version, changelog agree
python3 scripts/projectstate_gate.py                # the template's own recorded outcome
python3 scripts/check_studydd.py                    # repository health
```

CI runs the same commands on Linux, macOS, and Windows (`.github/workflows/validate.yml`). A green
suite is not the primary journey; if the journey fails, nothing else makes a slice green.

## Public and private

- This repository is public and must stay generic. Personalization happens only in an instance.
- Run `python3 scripts/agent_privacy_check.py` in an instance before pushing it anywhere shared, and
  never push an instance publicly without the learner's explicit consent.

## Demo

```bash
python3 scripts/run_demo_replay.py
```

The replay creates a temporary instance, asks one fake question, grades it honestly, writes evidence,
schedules a review, shows review-first selection, records an override, and validates the result. It
never touches a real learner repo. A static copy of the final state is in `EXAMPLES/demo_ai_search_exam/`,
and `docs/demo-walkthrough.md` walks through it. `EXAMPLES/` holds reference states only, never defaults.

## Docs

`docs/README.md` indexes the guides. The agent's contract is `AGENTS.md`; `protocols/README.md`
indexes the rules for each situation; `docs/architecture.md` maps every directory and script.

## Compatibility

StudyState is the public name; it was formerly StudyDD. Machine identifiers (`state/STUDYDD_*.yaml`,
`.studydd/`, script file names, schema IDs) keep their legacy spellings until a versioned migration
(`docs/naming-and-compatibility.md`). `docs/stateport-integration.md` lists the surfaces consumers such
as StatePort depend on.

## Future add-ons

Intentionally not part of the core:

- `addon-telegram-study-bot`: a daily review prompt, answer capture, reminders, low-energy study mode.
- `addon-containerized-studystate`: Docker, Podman, or devcontainer setup for portable local execution.

## License

MIT. See `LICENSE.md`.

## Status

v0.12.0. The template is a ProjectState v6 repository with a short contract; the review and
source-check loops are closed; instances are cast with a lock and updated mechanically; every test
runs in CI and passes on a clock 400 days ahead. See `CHANGELOG.md`.
