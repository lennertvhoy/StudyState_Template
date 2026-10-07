# TEMPLATE_INSTANCE_BOUNDARY — The Mold And The Cast

## What the boundary is

`StudyState_Template` is the public factory mold. A learner instance is a separate cast made from that mold.

There are two complementary maps. Use the one that answers your question.

**What may a file contain?** `state/STATE_MANIFEST.yaml` declares a `boundary` for every state file:

- `template` — generic repo infrastructure: mode markers, the manifest, activity templates. It stays identical and unpersonalized in every clone.
- `instance` — learner-specific state: targets, skills, evidence, sessions, reviews, sources, activity history, the learner profile. In the template these must stay empty placeholders.
- `generated` — derived context and indexes produced by `compact_state.py` and `build_context_pack.py`, and the template lock. Scripts write them; nobody hand-edits learner data into them.

**Who owns a file when the template changes?** `core/ownership.json` (in the template only) classifies every shipped file as `managed` (replaced by `scripts/update_instance.py`), `seeded` (copied once, then the instance's), `composite`, or `template_only` (never copied). See `docs/UPGRADING.md`.

## Enforcement

- `scripts/check_studydd.py` reads `boundary`. In template mode it **fails** if any `boundary: instance` file contains learner-specific data. A violation is an error, not a warning: the template is public.
- `scripts/template_release.py check` fails if a shipped file has no owner class, and `create_instance.py` refuses to cast from a template in that state.

## Agent rule

Before writing any state file, check `state/STATE_MANIFEST.yaml` for its `boundary`.

- `boundary: instance` and the repo is in template mode: **stop.** Do not add learner data. Use `scripts/create_instance.py` to create a learner copy, or explain the workflow in `protocols/INSTANTIATE_TEMPLATE.md`.
- `boundary: template`: keep the file generic and public-safe.
- `boundary: generated`: let the generation scripts update it.

## How to recover if the boundary is violated

1. Stop writing state.
2. Identify the touched `boundary: instance` files (`python3 scripts/check_studydd.py` names them).
3. Either revert those files to the template's generic placeholders, or copy the work to a new learner instance with `scripts/create_instance.py` and then sanitize the template repo.
4. Run `python3 scripts/check_studydd.py` in the template repo and confirm it passes.
5. Review `protocols/PRIVACY_REVIEW.md` before pushing anything that may have touched learner data.

## Cross-links

- `protocols/INSTANTIATE_TEMPLATE.md` — create a learner instance from the template.
- `protocols/UPGRADE_INSTANCE_FROM_TEMPLATE.md` — bring an instance up to a newer template.
- `protocols/PRIVACY_REVIEW.md` — scan a learner instance before pushing it publicly.
- `protocols/WRONG_REPO_RECOVERY.md` — what to do if you are in the wrong repo or mode.
