# ADR-0002: Declare file ownership and update instances mechanically

**Status:** accepted by the agent that made it; the owner's acceptance of the slice is pending
**Date:** 2026-10-07
**Author:** agent

## Context

Bringing an instance up to a newer template was a prompt: an agent copied "generic files"
from the template by hand, merged the version file, and wrote a note in
`upgrade_history`. Nothing recorded what had been installed, so a later upgrade could not
tell a file the learner had edited from a stale copy of the template, and the protocol
listed `AGENTS.md` as a file to overwrite while real instances kept their own rules in it.
`scripts/create_instance.py` copied the whole tree (including the template's own
maintenance history), re-dumped the mode and version files through a YAML writer that
dropped their comments, and forced a placeholder git identity onto the learner's commits.

ProjectState solved the same problem for its two files: a managed block, recorded hashes,
a dry-run-first update command that refuses on edits, and a fleet report.

## Decision

- `core/ownership.json` classifies every shipped file as `managed`, `seeded`, `composite`,
  or `template_only`. The longest matching pattern wins. A file with no class fails
  `scripts/template_release.py check` and stops `create_instance.py`.
- `create_instance.py` copies only `managed`, `seeded`, and `composite` files, composes the
  instance's own README, project definition, state slice, and `AGENTS.md`, edits the mode and
  version files as text so their comments survive, keeps the learner's git identity, and
  writes `state/TEMPLATE_LOCK.json` (sha256 of each managed file and of the contract block).
- `scripts/update_instance.py` (template checkout only, dry run by default) compares the
  lock, the instance, and the template. It replaces an unedited managed file, refuses an
  edited one unless told `--replace-edited`, refuses over uncommitted work unless told
  `--allow-dirty`, never writes learner state, local rules, or the ProjectState files, never
  commits, writes atomically, and writes the lock last so an interrupted run is finished by
  running it again.
- The standard library only: the tools run on a bare machine.
- Digests ignore CRLF versus LF in text files, so a Windows checkout does not look edited.

## Consequences

- After the one-time conversion, an instance update is a reviewed dry run and an apply.
- A template maintainer must classify a new file and state each release's instance action in
  `CHANGELOG.md`.
- An instance that has forked heavily (many edited scripts) is told so: the tool refuses
  rather than overwriting, and `docs/UPGRADING.md` says to reconcile such an instance once.
- The ownership vocabulary extends the existing `boundary:` field (`template`, `instance`,
  `generated`) in `state/STATE_MANIFEST.yaml`; the two answer different questions.

## Alternatives Considered

- **Git history as the channel (subtree, submodule, merge of template history).** Instances
  deliberately start with a fresh, private history; the template's history stays behind.
- **A separate overlay manifest per instance** (as in an unmerged lifecycle-manifest line of
  work). More machinery than the problem needs; it can be adopted later without breaking this.
- **Replace files without a lock.** Cannot tell an edit from a stale copy, which is the failure
  the lock exists to prevent.

## Related

- Slice: `template-hardening-001`
- Evidence: `evidence/template-hardening-001/summary.md`
