# ADR-0001: Adopt the ProjectState v6 core and a short contract

**Status:** accepted by the agent that made it; the owner's acceptance of the slice is pending
**Date:** 2026-10-07
**Author:** agent, on the owner's instruction to make the template the best it can be

## Context

The template coordinated its own maintenance with a per-slice evidence folder
(`Evidence/`, five files per slice) and a long `AGENTS.md`, while the owner's other
repositories had moved to the ProjectState v6 core (one human-owned `PROJECT.md`, one
current slice in `STATE.yaml`, one evidence summary, a small gate, and a managed contract
block). Measured on the commit before this change:

- `AGENTS.md` was about 30 KB, with a "Required First Actions" list of 58 files (about
  169 KB, roughly 42,000 tokens) to read before the first question. The repository's own
  `state/PERFORMANCE_BUDGET.yaml` caps a session-boundary read at 20 files. The start prompt
  and five session prompts repeated the instruction, and `STATE_LOADING_POLICY.md` said the
  opposite ("fast path by default").
- The list only ever grew: an open pull request added a 59th entry.
- The same content lived twice: `AGENTS.md` repeated sections that `protocols/` already held
  (the question gate, mistake taxonomy, review fields, handoff, readiness bands).
- An instance cast from this template, checked with ProjectState's fleet doctor, had an
  `AGENTS.md` of 708 lines against the 200-line limit and a start-up reading flagged at about
  12,000 tokens. Template rules and instance rules had been interleaved in one file, so a
  template update had no clean place to land.
- The template itself was invisible to the fleet doctor (neither v6 nor v5), and the new
  `evidence/` directory a v6 repository needs would have collided with `Evidence/` on a
  case-insensitive filesystem (macOS, Windows), both of which the template supports.
- `Evidence/` and `docs/superpowers/` (104 files, about 550 KB) were copied into every
  instance and held machine-specific home paths in a public repository.

## Decision

1. The template is a ProjectState v6 repository: `PROJECT.md`, `STATE.yaml`,
   `evidence/<slice>/summary.md`, the vendored gate, and the ProjectState managed block, all
   installed with ProjectState's own `projectstate_update.py`.
2. `AGENTS.md` is three zones: the ProjectState block (owned by ProjectState), a StudyState
   block (owned by the template, generated from `core/AGENTS.studystate.md`), and the
   project's own `## Local rules` and `## Owner directives`. The StudyState block is about
   115 lines. The ProjectState gate warns above 150 lines outside its block, so a fresh
   instance stays warning-free.
3. Start-up reads the context pack and the active study skill, nothing else. Protocols are
   opened when their situation arises, through `protocols/README.md`. Material that existed
   only in `AGENTS.md` moved to `docs/worked-state-update.md` and `docs/architecture.md`.
4. New instances start with the same core as honest placeholders (`core/instance/`): the
   instance gate exits 1 until a human defines the outcome and a real journey is recorded.
5. Pre-v6 `Evidence/` and `docs/superpowers/` left the tree. They remain in Git history,
   and a local tag `pre-v6-core` points at the last commit that has them.

## Consequences

- An agent's start-up cost falls from about 50,000 tokens to the context pack plus a roughly
  115-line contract.
- An instance cast before this change has no StudyState block, so its first update is a
  one-time semantic merge (`docs/UPGRADING.md`, "Convert an older instance"). Later updates
  are mechanical (ADR-0002).
- The template depends on ProjectState only for the gate and block, which are vendored, so
  StudyState scripts never import or require them at runtime.
- `STATE.yaml` and `PROJECT.md` in the template are drafted by an agent and need the owner's
  confirmation; `human_acceptance` stays `pending` until the owner decides.

## Alternatives Considered

- **Keep one large `AGENTS.md` and trim it.** The list grew by one entry in an open pull
  request while this was being written; without a structural limit it regrows.
- **Several files an agent must read.** That is the 58-file list again.
- **Adopt v6 but keep the evidence bundles.** The case collision and the path leak remain.
- **Merge the ProjectState block into the StudyState block.** The two have different owners
  and different update tools; one file region per owner keeps each tool's refusals meaningful.

## Related

- Slice: `template-hardening-001`
- Evidence: `evidence/template-hardening-001/summary.md`
