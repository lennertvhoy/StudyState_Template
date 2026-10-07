# Agent-Native Quickstart

StudyState is easiest when you use it with a coding agent. You do not need to edit YAML by hand.

## What You Need

- Python 3.10 or newer and Git. PyYAML is the only dependency, and nothing is installed
  without your consent (`docs/setup.md`).
- A coding agent such as Codex, Claude Code, Kimi Code, Cursor, or similar.
- A checkout of this template. Do not study inside it: it is the mold, and an agent that
  finds it in `mode: template` will stop and send you to the next step.

## Steps

1. **Cast your own learner instance** from the template checkout:

   ```bash
   python3 scripts/create_instance.py \
     --target ../Study_Me \
     --remote https://github.com/example/Study_Me.git
   ```

   The remote is optional (leave `--remote` out if you have none yet); it is where you may later push. Nothing is pushed. The script copies only what a
   learner needs, starts a fresh Git history, and validates the result.

2. **Open the new folder** (`Study_Me`) in your coding agent.

3. **Copy the start prompt.** Open `PROMPTS/coding_agent_start_prompt.md` and paste the
   whole thing into the agent chat.

4. **Tell the agent what you want to learn.** For example:

   > Initialize this StudyState instance for me. I want to prepare for a certification
   > exam. Ask me only the essential setup questions first.

5. **Let the agent build the first target.** It reads the contract, asks only the essential
   questions, creates the first target folder, registers trusted sources, builds a
   conservative skill map, and sets `NEXT_ACTIONS.md`.

6. **Answer one question at a time.** Review each proposed state update; confirm or correct it.

7. **Run validation.**

   ```bash
   python3 scripts/check_studydd.py
   ```

## What The Agent Maintains

- `state/STUDY_STATE.yaml` — current truth
- `state/SKILL_MAP.yaml` — skills and readiness
- `state/EVIDENCE_LOG.md` — demonstrated evidence
- `state/STUDY_STATUS.md` — human-readable snapshot
- `targets/` — one folder per study target
- `reviews/REVIEW_QUEUE.md` — spaced repetition queue
- `sessions/SESSION_LOG.md` — session history
- `sources/SOURCE_INDEX.md` — trusted source registry
- `NEXT_ACTIONS.md` — what to do next

You can inspect these files whenever you want. They are plain Markdown and YAML.

## Next Steps

- Read `docs/studydd-principles.md` to understand the rules.
- Read `docs/inspect-and-override-state.md` to learn how to correct the agent.
- Read a platform guide such as `docs/how-to-use-with-codex.md` for workflow tips.
- When the template improves, bring your instance up to date with `docs/UPGRADING.md`.
