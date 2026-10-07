# Naming and Compatibility

StudyState is the public name of this learning application and template. It
was formerly called **StudyDD**. This aligns the template with the StatePort
naming framework (`StatePort/docs/NAMING.md`):

- **StudyState** — public product/template name (this repo).
- **StateSpec** — public name of the portable application specification
  formerly called StateDD.
- **State-Centric Engineering (SCE)** — the engineering method.
- **Stateware** — the software category: durable, inspectable state and
  governed lifecycle contracts form the application boundary; agents and
  models are opinionated execution providers.

## What physically changed

- The GitHub repository was renamed from `lennertvhoy/StudyDD_Template` to
  `lennertvhoy/StudyState_Template`. GitHub redirects the old URL, so existing
  clones and recorded origins keep working.
- Public prose (README, AGENTS.md, protocols, prompts, docs, script output)
  now says StudyState.
- New learner instances record
  `https://github.com/lennertvhoy/StudyState_Template.git` as their template
  origin.

## What deliberately did not change

Machine identifiers stay on their legacy `studydd` spellings until a
separately versioned migration retires each one, exactly as StatePort's
terminology policy prescribes. Existing instances keep working unchanged.

Legacy spellings still used as machine identifiers include:

| Legacy identifier | Role |
|---|---|
| `state/STUDYDD_MODE.yaml` | mode marker file |
| `state/STUDYDD_TEMPLATE_VERSION.yaml` | template version tracking |
| `.studydd/context_pack.md`, `.studydd/state_cache.json` | generated runtime context |
| `scripts/check_studydd.py` | repo health gate |
| `scripts/setup_studydd.py`, other `*_studydd*` names | setup tooling |
| `studydd.compatibility-view/v1` and similar schema strings | persisted schema IDs |
| lowercase `studydd` in package/import/schema IDs downstream | StatePort compatibility IDs |

Every remaining legacy occurrence is classified as a **machine identifier**
or a **historical record** (the pre-0.12.0 evidence bundles and design plans
left the tree and live in Git history, at the local tag `pre-v6-core`).
Unclassified legacy wording on a current user-facing surface is a migration
defect; fix it when found.

## Compatibility rules for agents

1. Prose should say StudyState unless it refers to an exact legacy path,
   script name, schema ID, or environment variable.
2. Template-mode detection accepts both remote names:
   `StudyState_Template` (canonical) and `StudyDD_Template` (legacy alias).
3. Do not rename paths, files, YAML keys, or schema IDs as part of prose
   edits. A physical machine-identifier migration must ship with aliases,
   upgrade tests, rollback notes, and coordinated changes in consumer repos
   (learner instances and StatePort), versioned separately.
