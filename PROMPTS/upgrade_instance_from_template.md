# Upgrade A StudyState Learner Instance From The Template

You are bringing an existing learner instance up to a newer StudyState template. Do not
touch learner state. Use the tool; do not copy files by hand.

## Before you start

1. Verify repo path: `pwd`, `git rev-parse --show-toplevel`.
2. Verify remote and branch: `git remote -v`, `git branch --show-current`. Put the instance on a
   private branch with a clean worktree.
3. Read `state/STUDYDD_MODE.yaml` and confirm `mode` is `learner_instance` or `bootstrap`.
4. Read `state/STUDYDD_TEMPLATE_VERSION.yaml` and `protocols/UPGRADE_INSTANCE_FROM_TEMPLATE.md`.

## Locate the template source

Ask the learner for the template checkout (the public template is
`https://github.com/lennertvhoy/StudyState_Template.git`). Read its `CHANGELOG.md` for every
release since the instance's version and note each one's instance action.

## Run the update

From the template checkout:

```bash
python3 scripts/update_instance.py --target /path/to/instance            # dry run
python3 scripts/update_instance.py --target /path/to/instance --apply
```

Read the dry run before applying. If it refuses, report why and ask the learner; do not add
`--replace-edited` or `--allow-dirty` on your own. If the instance has no `studystate:managed`
block in `AGENTS.md`, follow "Convert an older instance" in `docs/UPGRADING.md`.

## Validate

In the instance, run `python3 scripts/check_studydd.py` and read `git diff`. Do not commit if
validation fails.

## Commit and push

Commit only when instructed, separately from study-session changes. Push only when the
learner explicitly asks.

## Report

List what was added, replaced, removed, and kept; any refusals and how they were resolved;
validation before and after; and what was committed or pushed.
