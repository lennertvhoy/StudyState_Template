# RECORD_SOURCE_CHECK — Recording Completed Source Freshness Checks

> **Agent rule.** When a `recent_info_check` activity is completed, the checked source metadata must be written back to `sources/SOURCE_STATE.yaml`. Prefer to pass the source metadata to `scripts/record_activity_result.py` when recording the activity result; it calls the canonical writer `scripts/record_source_check.py` automatically. Only invoke `scripts/record_source_check.py` directly when you are not also recording an activity result.

## When to run this script

Run `scripts/record_source_check.py` immediately after a learner or agent completes a source freshness check for a `moderate`, `volatile`, or `live` target. Typical triggers:

- The learner returned from checking an official documentation page, exam guide, or certification page.
- The learner answered a check question such as "What changed in the latest exam guide?"
- The agent verified a cached source against an authoritative reference.

Do not run the script before the check is complete, and do not record a check from memory or assumption.

## Automatic handoff from activity results

When a completed activity is a `recent_info_check`, `scripts/record_activity_result.py` can write the source check automatically. Supply `--source-id` and any desired source metadata flags (`--source-outcome`, `--source-summary`, `--source-authority`, `--source-volatility`, `--source-checked-at`, `--source-expires-at`, `--source-usable-for-questions` / `--source-not-usable-for-questions`). The activity result is recorded first; then `record_source_check(...)` is called with the activity's `target_id`, `activity_id`, and `evidence_id`. If the source-check call fails, the activity result is kept and a warning is printed.

If `--source-id` is not provided for a `recent_info_check`, `record_activity_result.py` behaves exactly as before and does not touch `sources/SOURCE_STATE.yaml`.

## Usage

```bash
python3 scripts/record_source_check.py <source_id> [flags]
```

Common flags:

- `--target-id` — required when `source_id` does not already exist.
- `--outcome` — `fresh`, `stale`, `missing`, `unverified`, or `unknown` (default `fresh`).
- `--summary` — short public-safe summary of what was verified.
- `--evidence-id` — evidence reference from `state/EVIDENCE_LOG.md`.
- `--activity-id` — activity reference from `state/ACTIVITY_STATE.yaml`.
- `--checked-by` — `agent` or `learner` (default `agent`).
- `--checked-at` — ISO 8601 timestamp (default UTC now).
- `--expires-at` — optional explicit expiration, must be `>= checked_at`.
- `--authority` — one of `official`, `high_authority`, `instructor`, `textbook`, `learner_notes`, `unverified`.
- `--volatility` — one of `stable`, `slow_changing`, `moderate`, `volatile`, `live`.
- `--freshness-window-days` — positive integer override.
- `--usable-for-questions` / `--not-usable-for-questions`.
- `--dry-run` — print what would be written, no write.
- `--demo` — print a fake example, no write.

## Schema

Each source entry in `sources/SOURCE_STATE.yaml` keeps the existing fields (`id`, `target_ids`, `authority`, `usable_for_questions`, `volatility`, `freshness_window_days`, `last_checked_at`, `expires_at`) and adds:

```yaml
last_check:
  checked_at: "2026-06-27T10:00:00+00:00"
  outcome: fresh          # fresh | stale | missing | unverified | unknown
  summary: "..."
  evidence_id: ""
  activity_id: ""
  checked_by: agent       # agent | learner
```

Rules:

- `last_check.checked_at` mirrors source-level `last_checked_at` only when `outcome == fresh`.
- If `outcome != fresh`, do **not** bump source-level `last_checked_at`; preserve the previous freshness signal.
- Update `metadata.last_updated` and `metadata.updated_by` on every write.

## What to collect

Record only public-safe, auditable metadata:

- Source identifier and authority level.
- Target(s) the source applies to.
- Volatility class and freshness window.
- Outcome of the check.
- One-sentence summary of what changed or was confirmed.
- Cross-references to evidence and activity IDs.
- Who performed the check and when.

## What not to record

Do **not** store in `sources/SOURCE_STATE.yaml`:

- Private URLs, credentials, API keys, or login tokens.
- Learner answers, transcripts, or screenshots (those belong in `state/EVIDENCE_LOG.md` and `activities/ACTIVITY_LOG.md`).
- Full copies of copyrighted source text.
- Personal identifiers or contact information.

## Mode gate

The script refuses to write unless the repo is in `learner_instance` mode. In `template` or `bootstrap` mode it exits with code `2`. Use `--dry-run` or `--demo` for read-only output in the public template.

## Suppressing repeated source checks

Only `outcome: fresh` updates the source-level freshness signal and suppresses repeated `recent_info_check` recommendations. A `stale`, `missing`, `unverified`, or `unknown` outcome records the attempt but leaves the target's freshness unresolved, so the next activity decision will still ask for a fresh source check before authoritative-current questions.

## Learner override

If the learner disagrees with a freshness outcome (for example, the agent marked a source stale but the learner believes it is still current):

1. Do **not** falsify the `outcome` field.
2. Record the learner's override in `state/EVIDENCE_LOG.md` and `activities/ACTIVITY_LOG.md`.
3. Optionally record a second `last_check` entry after the learner provides new evidence, with `checked_by: learner` and a summary explaining the override.
4. Keep `sources/SOURCE_STATE.yaml` truthful: if the override changes the classification, run `record_source_check.py` again with the new evidence and outcome.

## Idempotency

The script updates an existing source by `source_id`. Running it twice for the same source never creates duplicate entries; the latest check overwrites the previous `last_check` block.

## Return codes

- `0` — success, dry-run, or demo.
- `1` — validation or runtime error (invalid timestamp, enum, etc.).
- `2` — write refused because the repo is not a learner instance.
- `3` — source_id not found and `--target-id` was not provided.
