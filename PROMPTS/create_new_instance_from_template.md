# Create A New StudyState Instance From The Template

You are creating a new StudyState learner instance from the public template. **Do not personalize the template repo itself.** Personalization happens only inside the new instance, which `scripts/create_instance.py` casts with a fresh Git history.

## Hard Rules

- The template repo (`StudyState_Template`) is read-only except for template-maintenance tasks.
- The new instance must pass through `bootstrap` mode before `learner_instance` mode.
- Print `pwd`, `git rev-parse --show-toplevel`, `git remote -v`, and `cat state/STUDYDD_MODE.yaml` before editing any file, in the template and again in the new instance.
- Push nothing unless the learner explicitly asks.

## Before You Start

1. Confirm the source template:
   - repo path: the local checkout of the template (folder `StudyState_Template`; older checkouts may say `StudyDD_Template`)
   - remote: `https://github.com/lennertvhoy/StudyState_Template.git`
   - `state/STUDYDD_MODE.yaml` says `mode: template`
2. Ask the learner for the new instance directory and remote URL.
3. Confirm the target directory does not exist or is empty, and is outside the template repo.

## Cast The Instance

From the template checkout, with the learner's values:

```bash
python3 scripts/create_instance.py \
  --target ../Study_Me \
  --remote https://github.com/example/Study_Me.git
```

The script copies the instance's files, starts a fresh Git history, switches to `bootstrap` mode, records the template version and a lock, and runs the validator. Read its output. A bootstrap repo is expected to note that personalization is not complete; that is normal. If the script cannot run, use the manual fallback in `protocols/INSTANTIATE_TEMPLATE.md` and say so.

## Initialize The Learner

Move into the **new instance** (`cd ../Study_Me`), confirm the path, remote, and mode again, then:

1. Read `AGENTS.md` inside the new instance.
2. Ask the learner the essential setup questions.
3. Initialize the learner profile, first target, skill map, sources, reviews, sessions, and next action, **all inside the new instance only**.
4. Draft `PROJECT.md` (User, Outcome) from the learner's words and ask them to confirm.

## Switch To Learner Instance Mode

Only after the learner profile and first target are initialized, set `state/STUDYDD_MODE.yaml` in the new instance to:

```yaml
mode: learner_instance
personalized: true
public_safe: false_or_review_required
```

Keep the `template_origin` line and the file's comments. Then run `python3 scripts/check_studydd.py`.

**Warning:** Do not set `mode: learner_instance` before the learner profile and first target exist. The validator fails if the required learner state is missing.

## First Commit

```bash
git add .
git commit -m "chore: initialize StudyState learner instance"
```

Push only if the learner explicitly requests it: `git push -u origin main`.

## What Not To Do

- Do not edit the template repo except to read it.
- Do not initialize learner state in the template repo.
- Do not switch directly to `mode: learner_instance` without passing through `bootstrap`.
- Verify path and remote before every edit.
