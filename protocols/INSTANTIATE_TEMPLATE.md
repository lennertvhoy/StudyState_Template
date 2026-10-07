# INSTANTIATE_TEMPLATE — Create A Learner Instance From The Mold

> **Agent action.** Use this protocol when the learner wants a new StudyState repo.

## Law

`StudyState_Template` is the factory mold. A learner instance is a cast made from that mold.

- Do not personalize the template repo.
- Do not put private learner state into the template repo.
- Personalization happens only in the new instance, after the template's Git history has been left behind.
- The new repo passes through `bootstrap` mode before it becomes a `learner_instance`.

## Source Template Verification

Before casting, confirm the source template:

- repo path: the local checkout of the template (folder `StudyState_Template`; older
  checkouts may say `StudyDD_Template`)
- remote: `https://github.com/lennertvhoy/StudyState_Template.git` (the legacy
  `StudyDD_Template` URL redirects to it and is still accepted)
- `state/STUDYDD_MODE.yaml` says `mode: template`

If the source repo does not look like the template, stop and ask the learner for the correct
template path or remote.

## Target Directory Selection

1. Ask the learner for the new instance directory name, for example `Study_Me`.
2. Confirm the target path, for example `../Study_Me`.
3. The target must not exist or must be empty, and must not be inside the template repo.
   The script refuses otherwise.

## Cast The Instance

Run from the template checkout:

```bash
python3 scripts/create_instance.py \
  --target ../Study_Me \
  --remote https://github.com/example/Study_Me.git
```

The script:

1. copies the files an instance owns (`managed` and `seeded` in `core/ownership.json`) and
   leaves the template's maintenance material behind (its README, changelog, project
   definition, and update tools);
2. writes the instance's own `README.md`, `PROJECT.md`, `STATE.yaml`,
   `evidence/bootstrap-001/summary.md`, and `AGENTS.md` (the template's contract plus empty
   `## Local rules` and `## Owner directives`);
3. starts a fresh Git history on `main`, adds the remote, and keeps the learner's own git
   identity when one is configured;
4. switches `state/STUDYDD_MODE.yaml` to `mode: bootstrap`, keeping its comments;
5. records the template version and commit in `state/STUDYDD_TEMPLATE_VERSION.yaml` and a
   lock of the template files in `state/TEMPLATE_LOCK.json`, which `scripts/update_instance.py`
   uses later;
6. runs `python3 scripts/check_studydd.py` and prints the start prompt.

Nothing is committed or pushed. The instance's ProjectState gate
(`python3 scripts/projectstate_gate.py`) fails until the outcome and the first journey are
recorded. That is honest, not a fault.

## Initialize The Learner

Inside the new instance only:

1. Open `PROMPTS/coding_agent_start_prompt.md` and follow it.
2. Initialize the learner profile, first target, skill map, sources, and next action. Draft
   the User and Outcome in `PROJECT.md` from the learner's words and ask them to confirm.
3. Only after that, set `state/STUDYDD_MODE.yaml` to `mode: learner_instance` and run
   `python3 scripts/check_studydd.py` again.
4. Make the first commit, and push only if the learner explicitly asks:

   ```bash
   git add .
   git commit -m "chore: initialize StudyState learner instance"
   ```

## Bootstrap Mode

`bootstrap` means:

- The repo has left the template remote and its Git history has been reset.
- Required files, protocols, scripts, prompts, and the mode marker are present.
- The learner profile and first target are **not** initialized yet.
- Validation passes with a note that personalization is incomplete.

Do not switch to `learner_instance` until the learner profile, first target, skill map,
sources, and next action are initialized: the validator then expects the real learner state.

## Manual Fallback

Use this only when the script cannot run. A hand-made copy has no template lock, so
`update_instance.py` cannot tell your edits from stale text later. Prefer the script.

1. Clone the template into the new directory and enter it.
2. From `core/instance/`, copy `README.md`, `PROJECT.md`, `STATE.yaml`, and
   `evidence/bootstrap-001/summary.md` over their counterparts at the repository root.
3. In `AGENTS.md`, keep everything up to and including the `studystate:managed:end` line,
   then append `core/instance/AGENTS.local.md`.
4. Delete every file that `core/ownership.json` classifies as `template_only` (the template's
   changelog, maintenance notes, update tools, and their tests), including `core/` itself.
5. `rm -rf .git`, then `git init -b main` and `git remote add origin <url>`.
6. Set `mode: bootstrap` and add a `template_origin` line in `state/STUDYDD_MODE.yaml`, then run
   `python3 scripts/check_studydd.py`.

## After Instantiation

1. Confirm the new repo is a learner instance (`state/STUDYDD_MODE.yaml`).
2. Initialize the learner profile and first target only inside the new instance.
3. Never return to the template repo to make learner-specific edits.

## Smoke Test

```bash
python3 scripts/test_instantiate_template.py
python3 scripts/test_instance_journey.py
```

The first creates a temporary instance, simulates minimal learner initialization, switches to
`learner_instance`, and validates. The second runs the whole journey: cast, study, review,
source check, update.
