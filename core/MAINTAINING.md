# Maintaining the StudyState template

For agents and people changing the mold itself. This file is template-only: it is
never copied into a learner instance. The contract for both is in `AGENTS.md`.

## What this repository is

The public mold. `state/STUDYDD_MODE.yaml` says `mode: template`. A learner never
studies here; an agent casts a learner instance with `scripts/create_instance.py`
and the instance lives on its own. Keep the repository generic and public-safe.

## Rules

- **Public and generic.** No real learner, target, exam, evidence, or private data;
  no machine paths; no private repository names. `scripts/test_cross_platform_paths.py`
  scans every file for paths, and `scripts/check_studydd.py` fails if an `instance`
  boundary file is populated.
- **Stable contract surfaces.** Consumers depend on the mode marker path and keys
  (`state/STUDYDD_MODE.yaml`), the template-version file path and keys, the
  documented script entry points, the `.studydd/` generated paths, the lifecycle
  mode values (`template`, `bootstrap`, `learner_instance`), and the question,
  review, and evidence schema identifiers. Machine identifiers keep their legacy
  `studydd` spellings. Changing one is a versioned migration with aliases and
  upgrade tests (`docs/naming-and-compatibility.md`, `docs/stateport-integration.md`).
- **Ownership is declared.** `core/ownership.json` classifies every file as
  `managed` (replaced on update), `seeded` (copied once), `composite`, or
  `template_only`. A new file must be classified, or
  `python3 scripts/template_release.py check` and `create_instance.py` refuse.
- **Tests never depend on the wall clock.** Pin a clock with `--now`, or build
  timestamps relative to now. `python3 scripts/run_tests.py --clock-offset-days 400`
  runs the whole suite 400 days ahead and must pass.
- **A new script** is listed in `docs/architecture.md`; **a new test** is
  `scripts/test_<name>.py`, so the runner and CI discover it without a CI edit.
- **Dependencies.** `requirements.txt` stays minimal. Anything that must run on a
  bare machine (the lifecycle scripts) uses only the standard library.

## The StudyState block and releases

The StudyState block inside `AGENTS.md` is generated from `core/AGENTS.studystate.md`
and carries the template version in its start marker. Do not edit it in
`AGENTS.md`. Edit the source, then:

```bash
python3 scripts/template_release.py sync     # rewrite the AGENTS.md block
python3 scripts/template_release.py check    # block, ownership, version, changelog agree
```

Changing the block, a managed file, or a contract surface is a release:

1. Bump `template_version` in `state/STUDYDD_TEMPLATE_VERSION.yaml`.
2. Add a `## <version>` entry to `CHANGELOG.md` that states the **instance action**:
   `none` (nothing to do), `mechanical` (`scripts/update_instance.py` does it), or
   `semantic` (a person merges it, as when an instance cast before 0.12.0 first
   gets its studystate block).
3. Run `template_release.py sync` so the block's marker names the new version.

The ProjectState gate (`scripts/projectstate_gate.py`) and managed block are not
edited here: update them with ProjectState's own `projectstate_update.py`.

## Verification before claiming a slice

```bash
python3 scripts/test_instance_journey.py          # the primary journey: cast, study, update
python3 scripts/run_tests.py                      # the whole suite, real clock
python3 scripts/run_tests.py --clock-offset-days 400
python3 scripts/template_release.py check
python3 scripts/projectstate_gate.py
```

A passing suite is not the journey. If the journey fails, nothing else makes the
slice green.

## Unmerged work

Feature lines that exist only on remote branches (fast-drill mode, the
lifecycle-manifest and portable-actions work) are not part of this template until
the owner decides to merge them. Do not port them piecemeal.
