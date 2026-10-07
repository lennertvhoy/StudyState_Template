# UPGRADE_INSTANCE_FROM_TEMPLATE — Apply Template Improvements Safely

> **Agent action.** Use this protocol when a learner wants generic StudyState_Template
> improvements in their personal instance. The mechanism and its flags are in
> `docs/UPGRADING.md`; this is the agent's procedure.

## Law

- The learner instance is the source of truth for learner state.
- Template-owned files may be replaced from the template; learner state is never overwritten.
- The update runs from the template checkout. An instance never updates itself.
- Never commit a broken upgrade, and never push without an explicit instruction.

## Before you start

1. Confirm the instance is `mode: learner_instance` (or `bootstrap`) in `state/STUDYDD_MODE.yaml`.
   If it says `template`, stop.
2. Read `state/STUDYDD_TEMPLATE_VERSION.yaml` for the origin and last upgrade, and
   `state/TEMPLATE_LOCK.json` for what the template installed.
3. Confirm the template checkout with the learner. Read its `CHANGELOG.md`: each release
   states its instance action (`none`, `mechanical`, `semantic`).
4. Read `protocols/GIT_PROVENANCE.md` and `protocols/PRIVACY_REVIEW.md`.
5. Put the instance on a private branch with a clean worktree.

## Mechanical update

```bash
# from the template checkout
python3 scripts/update_instance.py --target /path/to/instance            # dry run, writes nothing
python3 scripts/update_instance.py --target /path/to/instance --apply
```

Read the dry-run report. Do not pass `--replace-edited` or `--allow-dirty` to make a
refusal go away: each refusal means a person's edit or uncommitted work is at stake. Show
the learner the files involved and let them decide (`docs/UPGRADING.md`, "Refusals and flags").

## Older instance without the StudyState block

The tool refuses an instance whose `AGENTS.md` has no `studystate:managed` block. That
conversion is a one-time semantic merge: `docs/UPGRADING.md`, "Convert an older instance".

## After applying

1. In the instance, read `git diff` and run `python3 scripts/check_studydd.py`.
2. If validation fails, stop and report; do not commit a broken upgrade.
3. Commit the upgrade separately from any study-session changes:

   ```bash
   git add -A
   git commit -m "chore: update StudyState from template vX.Y.Z"
   ```

4. Push only if the learner explicitly requests it.

## Final handoff

Report: the template source, version and commit; the instance's version before and after;
files added, replaced, removed, and kept; the dry-run refusals and how they were resolved;
validation before and after; whether anything was committed or pushed; any manual steps left.

## What not to do

- Do not upgrade learner state files automatically, or edit them to make the update pass.
- Do not run an upgrade inside the public template repo.
- Do not commit a broken upgrade, and do not push without explicit instruction.
- Do not copy template files by hand when the tool can do it: a hand copy leaves the lock stale.
