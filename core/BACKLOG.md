# Template backlog

The roadmap for the template itself. Template-only: it is never copied into a learner instance, whose
own strategic backlog is `state/STUDY_BACKLOG.md`. The one current slice and its exact next action live
in `STATE.yaml`; this file holds work that is not immediate.

## Needs an owner decision

- **fast-drill mode** (open pull request): a lightweight checkpoint speed layer for question drills. A
  1,100-line script plus a spec, written against the older template. Merge, rework, or close.
- **lifecycle manifest and portable actions** (unmerged branches): instance layout contract, compatibility
  views, typed actions, transactional proposal writers. StatePort's adapter binds to that line, not to what is on
  `main`. Decide whether `main` converges on it, or StatePort adapts to `main`. This slice's ownership and lock
  files (`core/ownership.json`, `state/TEMPLATE_LOCK.json`) were designed to coexist with it.
- **transactional hardening** (open work-in-progress pull request): state-transition boundaries. Same question.
- **source-check completion** (open pull request): ported by hand in 0.12.0 with its tests fixed; the pull request
  is superseded and can be closed.

## Next

- **Convert the one existing instance** to the studystate block (`docs/UPGRADING.md`, "Convert an older
  instance"), reconciling its edited scripts first. Until then it cannot be updated mechanically.
- **Windows and macOS.** Push the branch, read the first CI results, and fix whatever the full suite finds there.
- **A real spaced-repetition algorithm.** Replace the interval map with FSRS or SM-2 behind the same file surface,
  once a learner's review history exists to calibrate against (`protocols/SPACED_REPETITION_POLICY.md`).
- **machine-identifier migration.** Move the legacy `studydd` spellings (paths, script names, schema IDs) to
  `studystate`, with aliases, upgrade tests, rollback, and coordinated StatePort changes
  (`docs/naming-and-compatibility.md`).
- **single-writer policy.** A generic lock and protocol so two agents never write one instance's state at once.

## Add-ons

- `addon-telegram-study-bot`: daily review prompts, answer capture, reminders, low-energy study mode.
- `addon-containerized-studystate`: Docker, Podman, or devcontainer setup for portable local execution.

## Done

- 0.12.0: ProjectState v6 core; short contract; ownership, lock, and mechanical updates; review and
  source-check loops closed; template/instance boundary enforced; tests discovered and clock-independent.
