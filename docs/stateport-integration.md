# StatePort Integration

How this template fits the StatePort framework — the local platform for
durable, user-owned Stateware applications (`StatePort` repository).

## Concept mapping

| StatePort concept | This template |
|---|---|
| Application | StudyState — the agent-operated study workspace |
| Template (StateSpec) | this repository, the reusable mold |
| Instance | a learner repo cast from this template (`scripts/create_instance.py`, `protocols/INSTANTIATE_TEMPLATE.md`) |
| Canonical state | `state/`, `targets/`, `reviews/`, `sources/` plain files |
| Evidence | `state/EVIDENCE_LOG.md`, session logs; `evidence/<slice>/summary.md` for repository work |
| Lifecycle modes | `template` → `bootstrap` → `learner_instance` in `state/STUDYDD_MODE.yaml` |
| Governance | validator gate (`scripts/check_studydd.py`), the ProjectState v6 gate (`scripts/projectstate_gate.py`), protocols, privacy review |

## What StatePort consumes today

- **Source mirror**: StatePort's local alpha installs instances from a mirror
  of this repository
  (`./stateport setup --source-mirror /path/to/StudyState_Template init`,
  or `STATEPORT_STUDYDD_MIRROR`). The installed identity records the exact
  source commit and digests.
- **Compatibility views**: StatePort's read-only adapter recognizes the mode
  and version markers (`state/STUDYDD_MODE.yaml`,
  `state/STUDYDD_TEMPLATE_VERSION.yaml`) as instance compatibility surfaces.
- **Naming policy**: StatePort's terminology policy lists StudyState (legacy
  StudyDD) as a product and treats `StudyDD_Template` / lowercase `studydd`
  as machine identifiers. This template follows that split: public naming has
  moved to StudyState; machine identifiers remain stable (see
  [naming-and-compatibility.md](naming-and-compatibility.md)).

## Stability contract

Consumer tooling depends on these staying stable across template releases:

1. mode marker path and keys;
2. template-version file path and keys;
3. the script entry points documented in `AGENTS.md` and `docs/architecture.md`;
4. `.studydd/` generated-context paths;
5. lifecycle mode values (`template`, `bootstrap`, `learner_instance`);
6. question/review/evidence schema identifiers;
7. the instance lock, `state/TEMPLATE_LOCK.json`, and its keys.

Breaking any of these is a versioned migration, never a side effect of prose
or feature work. `docs/UPGRADING.md` explains how an instance follows a release.

## Open alignment work (external boundaries)

These live in consumer repos and are intentionally not changed from here:

- StatePort's `config/terminology-policy.yaml` still lists
  `StudyDD_Template` among current machine identifiers for StudyState; update
  it to recognize `StudyState_Template` when the platform adopts this rename.
- A future lowercase `studydd` → `studystate` machine-identifier migration
  (paths, script names, schema IDs) remains open and must be coordinated with
  learner-instance upgrade tests and StatePort compat views.
