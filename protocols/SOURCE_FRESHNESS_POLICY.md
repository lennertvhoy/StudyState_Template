# SOURCE_FRESHNESS_POLICY — Source Freshness Rules

This policy defines how fresh a source must be for a given study topic, and how agents must handle stale or uncertain information.

> **Canonical numeric windows live in `scripts/check_source_freshness.py`.**
> Keep this policy aligned with `VOLATILITY_MAX_AGE_DAYS` in that script so the
> documented defaults never drift from the implemented defaults again.

## Volatility Classes

```yaml
volatility_classes:
  stable:
    examples: [basic arithmetic, classical logic forms, long-established historical facts, basic grammar patterns]
    default_max_age_days: 3650
    source_required_for_new_questions: false
  slow_changing:
    examples: [general networking fundamentals, basic programming concepts, established philosophical arguments, standard mathematical techniques]
    default_max_age_days: 730
    source_required_for_new_questions: false
  moderate:
    examples: [certification objectives, school curriculum standards, cloud architecture best practices, software library behavior]
    default_max_age_days: 30
    source_required_for_new_questions: true
  volatile:
    examples: [Microsoft Azure services, cloud security products, vendor certification exam objectives, pricing, preview features, portal UI locations, product names, compliance features]
    default_max_age_days: 7
    source_required_for_new_questions: true
  live:
    examples: [current outages, current prices, current exam retirement dates, current product availability, breaking changes]
    default_max_age_days: 1
    source_required_for_new_questions: true
```

## Authority Levels

Freshness rules depend on source authority. Use the following levels, consistent with `protocols/SOURCE_TRUST.md` and recorded in `sources/SOURCE_STATE.yaml` once it exists:

- `official` — vendor exam guide, product documentation, certification page, official course syllabus.
- `high_authority` — current official sources or strongly trusted references such as employer materials, recruiter guidance, or interview rubrics.
- `instructor` — guidance from a known instructor, mentor, or training provider.
- `textbook` — published textbook or peer-reviewed reference.
- `learner_notes` — the learner's own notes, flashcards, or summaries.
- `unverified` — blog posts, forum threads, generated summaries, or any source whose authority has not been confirmed.

## Rules

- Targets should declare a volatility class in their `TARGET.yaml`. If the class is missing, the agent must default to `moderate` and warn the learner.
- Authoritative questions about volatile or live topics require fresh, usable official or `high_authority` sources before they may be treated as current.
- Stale sources may be used only with explicit learner override. Questions built from stale sources must be labelled as practice-only and not treated as authoritative.
- The agent must not hide uncertainty. If source freshness is unknown or borderline, the agent must disclose that to the learner.
- The learner may override freshness recommendations. Any override must be recorded in `state/EVIDENCE_LOG.md` and `sessions/SESSION_LOG.md`.
- Reference fixtures under `EXAMPLES/` are historical snapshots: their source timestamps are deterministic test metadata, not live freshness claims. The validator enforces structure there, but wall-clock staleness errors apply only to real targets under `targets/`, or everywhere when an explicit `--now` clock is passed to `scripts/check_studydd.py`.
- Deterministic tooling (`run_demo_replay.py`, tests) should pin its own clock with `--now` instead of editing fixture timestamps to chase the wall clock.
- A completed `recent_info_check` must be recorded via `scripts/record_source_check.py`. Only `outcome: fresh` suppresses repeated `recent_info_check` recommendations; any other outcome leaves the target's freshness unresolved.
