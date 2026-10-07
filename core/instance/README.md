# Study instance

A StudyState learner instance: a repo-native study brain that a coding agent
operates. It was cast from the public `StudyState_Template` and now holds this
learner's own state. Keep the repository private unless you have reviewed it with
`python3 scripts/agent_privacy_check.py`.

## Start

1. Open this folder in your coding agent (Codex, Claude Code, Kimi Code, Cursor, or similar).
2. Paste `PROMPTS/coding_agent_start_prompt.md`.
3. Say "Start a StudyState session."

The agent verifies the repository, reads a compact context pack, recommends one
activity, asks one question, grades your actual answer, and records the result.

## Where things live

| Path | Holds |
| --- | --- |
| `state/` | current learner truth: profile, skill map, evidence, status |
| `targets/` | one folder per study target |
| `reviews/` | the spaced-repetition queue |
| `sessions/` | session logs and summaries |
| `sources/` | trusted sources and their freshness |
| `NEXT_ACTIONS.md` | the single next study action |
| `AGENTS.md` | the agent's contract; learner-specific rules go under `## Local rules` |
| `PROJECT.md`, `STATE.yaml`, `evidence/` | ProjectState coordination for work on this repository |

Everything is plain Markdown and YAML. You can read or override any file; the
agent records an override instead of hiding it.

## Check health

```bash
python3 scripts/check_studydd.py      # study state and repository health
python3 scripts/projectstate_gate.py  # recorded outcome and evidence
```

The gate fails on a fresh instance until the outcome and the first journey are
recorded. That is expected.

## Stay current with the template

Run this from a checkout of the template, not from here:

```bash
python3 scripts/update_instance.py --target /path/to/this/instance          # dry run
python3 scripts/update_instance.py --target /path/to/this/instance --apply
```

It replaces only template-owned files and the template's block in `AGENTS.md`.
It never touches your state, targets, reviews, sessions, sources, or local rules.
