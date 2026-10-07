# Upgrading a learner instance

A learner instance is cast from the template and then lives on its own. When the
template improves, `scripts/update_instance.py` brings the instance up to date by
replacing exactly what the template owns and nothing the learner owns. It is a dry
run until you pass `--apply`, it never commits, and it refuses to overwrite a file
you edited.

Each release in the template's `CHANGELOG.md` states its **instance action**:

| Action | Meaning |
| --- | --- |
| `none` | Nothing to do. |
| `mechanical` | `update_instance.py` does it. |
| `semantic` | A person merges it once (for example the first conversion below). |

## Who owns what

`core/ownership.json` in the template classifies every file it ships:

| Class | What it is | What an update does |
| --- | --- | --- |
| `managed` | scripts, protocols, prompts, docs, study skills, examples, the CI workflow, the state manifest | replaced when the template changed and you have not edited it |
| `seeded` | learner state, targets, reviews, sessions, sources, `NEXT_ACTIONS.md`, issue templates, the vendored ProjectState gate | copied once when the instance was cast; never touched again |
| `composite` | `AGENTS.md` and `state/STUDYDD_TEMPLATE_VERSION.yaml` | the template's block in `AGENTS.md` is replaced; the version file is merged; everything else is yours |
| `template_only` | the template's own README, changelog, project definition, maintenance notes, update tools | never copied into an instance |

An instance's own `PROJECT.md`, `STATE.yaml`, `evidence/`, and `## Local rules` are never
touched. The ProjectState gate and its contract block are updated with ProjectState's
own `projectstate_update.py`, not by this tool.

## Update an instance

Run the tool from the template checkout. An instance never updates itself.

1. Start the instance from a clean checkout on a private branch:

   ```bash
   git -C /path/to/instance switch -c studystate/update
   ```

2. Dry run from the template checkout. It writes nothing:

   ```bash
   python3 scripts/update_instance.py --target /path/to/instance
   ```

3. Read the report (below) and resolve anything it refuses.
4. Apply:

   ```bash
   python3 scripts/update_instance.py --target /path/to/instance --apply
   ```

5. In the instance, read `git diff`, run `python3 scripts/check_studydd.py` and the
   instance's own checks, then commit. The tool never commits and never creates a branch.
6. Merge the branch when you are satisfied. Undoing an update means dropping the branch.

`--check` is a dry run that exits `1` when a change is needed, which suits automation.
`--json` prints the plan as JSON.

## Read the report

Each line is one file, or `AGENTS.md#studystate-block` for the block in `AGENTS.md`.

| Kind | Meaning |
| --- | --- |
| `add` | the template has a new file the instance lacks |
| `replace` | the file changed upstream and the instance still has exactly what the template installed |
| `REPLACE EDITED` | the instance edited the file since it was installed |
| `REPLACE UNKNOWN` | the instance has a different file, and there is no record of what the template installed (no lock entry) |
| `remove` | the template dropped the file and the instance still has it unedited |
| `keep (edited)` | the template dropped the file but the instance edited it; it stays, untracked |

The tool knows what it installed because `create_instance.py` and every update record
the sha256 of each managed file in `state/TEMPLATE_LOCK.json`. Comparing the lock, the
instance, and the template tells an edit from a stale copy. Line endings are ignored,
so a Windows checkout does not look edited.

## Refusals and flags

On any refusal the tool writes nothing, and the dry run exits `2` exactly when
`--apply` with the same flags would. A flag says you have read the report; it does
not make the change safe.

| Flag | Refused because | What the flag costs |
| --- | --- | --- |
| `--replace-edited` | `REPLACE EDITED`/`REPLACE UNKNOWN` files, or an edited contract block | the edits, which then survive only in Git history |
| `--allow-dirty` | a file the update would write has uncommitted changes, or Git cannot report status | uncommitted edits in those files are lost |

Refusals without a flag, because the tool cannot make them safe: a target that is not
a StudyState instance (no `state/STUDYDD_MODE.yaml`) or is in `template` mode or is the
template itself; a symlink in the target; an `AGENTS.md` with CR or CRLF line endings
(convert it to LF so local text can be kept byte for byte), with malformed markers, or
with no StudyState block (see "Convert an older instance"); and a template with a file
that `core/ownership.json` does not classify.

The dirty-tree guard applies only when the update would write something, so a second
`--check` right after an uncommitted `--apply` simply says there is nothing left to do.

## What it touches

It replaces the `managed` files, the StudyState block in `AGENTS.md`, and merges
`state/STUDYDD_TEMPLATE_VERSION.yaml` (template version, last upgrade, and one
`upgrade_history` entry; the comments and the creation origin stay). It then refreshes
`state/TEMPLATE_LOCK.json`. It does not run the instance's checks or judge the result;
steps 5 and 6 are yours.

`--apply` writes each file atomically (a temporary file renamed over the original) and
writes the lock last, so an interrupted run is finished by running `--apply` again.

## Convert an older instance (once)

An instance cast before 0.12.0 has no `studystate:managed` block in `AGENTS.md` and no
lock, so `update_instance.py` refuses it. This is the one semantic step; every release
after it is mechanical.

1. On a private branch, copy the template's `core/AGENTS.studystate.md` into the instance's
   `AGENTS.md` between these markers, using the template's current version for `release=`:

   ```text
   <!-- studystate:managed:start release=0.12.0 -->
   ...contents of core/AGENTS.studystate.md...
   <!-- studystate:managed:end -->
   ```

2. Replace the rest of the old contract with that block. Keep only what is specific to
   this learner or repository under `## Local rules`, and standing instructions under
   `## Owner directives`. Sections that duplicated template text (the mode check, the
   loop, the learning laws, and the old long start-up reading list) are in the block now.
   If the instance already follows ProjectState v6, its own managed block stays above.
3. Run the dry run. Every template-owned file that differs from the template shows as
   `REPLACE UNKNOWN`, because there is no lock yet.
4. Read that list. A file the instance customized is the instance's decision to make:
   - a change that is generic belongs upstream, in the template;
   - a change that is specific to this learner belongs outside template-owned files
     (in `targets/`, `state/`, `## Local rules`, or a script of its own name);
   - anything else is dropped by the update.
5. When the list holds only differences you are happy to lose, apply with `--replace-edited`.
   The tool writes the lock, and later updates tell edits from stale copies.

An instance that has diverged heavily from the template, with many edited scripts, is a
fork in practice. Reconcile it by hand once, following step 4, before relying on
mechanical updates; replacing a customized validator wholesale would be the wrong
outcome, and the refusals exist to stop it.

## Truth at handoff

Report separately: what the template checkout contained (version and commit), what was
changed in the instance's working tree, the instance's own validation result, and whether
anything was committed or pushed. A local update is complete without being pushed; say so.
