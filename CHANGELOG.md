# Changelog

Notable changes to the StudyState template. Every release states its **instance
action**, what an existing learner instance has to do:

- `none`: nothing.
- `mechanical`: `python3 scripts/update_instance.py` does it (see `docs/UPGRADING.md`).
- `semantic`: a person merges it once.

Older history is in Git (`git log`) and the pull requests of the repository. The
pre-0.12.0 evidence bundles and design plans were removed from the tree; they are
at the local tag `pre-v6-core` (`git show pre-v6-core:Evidence/`).

## 0.12.0 - 2026-10-07

Instance action: **semantic, once**. An instance cast before 0.12.0 has no
`studystate:managed` block in `AGENTS.md`, so `update_instance.py` refuses it. Merge
the block by hand as `docs/UPGRADING.md` ("Convert an older instance") describes;
every later release is then `mechanical`.

### Fixed

- **A documented scheduler call produced state the validator rejects.** `schedule_review.py`
  gives a wrong, low-confidence answer a same-day interval of `0`, as
  `protocols/SCHEDULE_REVIEW.md` says, but `check_studydd.py` required `interval_days > 0`
  and failed the repository. Zero is now valid.
- **Reviews could be created but never completed.** Nothing recorded a finished review or
  grew an interval, although the docs promised "double the interval". `schedule_review.py
  --review-id` now records the result: a correct recall doubles (cap 30 days or
  `--max-interval-days`), a shaky one repeats, a lapse resets and counts.
- **Source checks could be demanded but never recorded.** The router sent a stale target to
  `recent_info_check`, but nothing wrote the result back. `record_source_check.py` (from the
  open pull request for the source-check completion flow) now does, and
  `record_activity_result.py` can call it.
- `select_next_study_action.py` rewrote `reviews/REVIEW_STATE.yaml` on every call, dropping
  its comments. It now writes only when a status changed, keeps the header comments, sorts
  by due instant instead of by string, and names the command that closes the review.
- `build_context_pack.py` used `Any` without importing it; unused names and imports removed.
- Several tests recorded a fixed June date and then judged freshness on the real clock, so
  they could only pass within 30 days of that date. They now build timestamps relative to now.
- `create_instance.py` re-dumped the mode and version files and lost their lifecycle
  comments, forced a placeholder git identity onto the learner's commits, and copied the
  template's maintenance history (about 550 KB, with a private home path in it) into every
  instance. It no longer does any of these.
- CI never ran `test_create_instance.py`; it listed tests by hand. It now runs all of them.
- **The fast-path check could not pass.** `UPDATE_STATE.md` says to validate the touched evidence
  ID without compacting, but `validate_touched_state.py --evidence-id` looked only in the derived
  index that only compaction builds, so a fresh append always failed. It now falls back to one
  targeted parse of the audit log.
- **An instance inherited tests and CI that cannot pass inside it.** Of 20 test scripts shipped to
  an instance, 13 failed there (they cast instances from the checkout, which needs `mode: template`),
  and the copied CI ran them. Template-scenario tests and the template's CI are now `template_only`;
  an instance gets its own five tests and a small CI (`core/instance/validate.yml`).
- The onboarding docs told people to clone the template, open it in an agent, and say "initialize
  this copy", which a template-mode agent must refuse. They now start by casting an instance.
- Prose said "StudyDD" in files merged from older work; it says StudyState.

### Added

- **ProjectState v6 core** for the template itself: `PROJECT.md`, `STATE.yaml`,
  `evidence/<slice>/summary.md`, the vendored gate, and the managed contract block.
  New instances start with the same core, as honest placeholders.
- **A short contract.** `AGENTS.md` shrank from 33 KB, with a 58-file "Required First
  Actions" list (about 42,000 tokens, against a declared budget of 20 files), to a
  contract of about 115 lines. Start-up reads the context pack. The duplicated sections
  already lived in `protocols/`; material that did not moved to `docs/architecture.md`
  and `docs/worked-state-update.md`; `protocols/README.md` indexes the protocols.
- **Mechanical instance updates.** `core/ownership.json` classifies every file (`managed`,
  `seeded`, `composite`, `template_only`); `create_instance.py` records a lock of what it
  installed; `update_instance.py` (dry run by default) replaces only unedited template-owned
  files and the StudyState block in `AGENTS.md`, and refuses on local edits.
- The template/instance boundary (`boundary:` in `state/STATE_MANIFEST.yaml`, from the open
  pull request), now an **error** when learner data appears in the template.
- `scripts/run_tests.py` (discovers every test, refuses a test file that would pass without
  running; `--clock-offset-days N` runs the suite in the future and verifies the shift took effect), `scripts/template_release.py` (`check`, `sync`), `scripts/state_io.py`
  (comment-preserving state writes), and `scripts/review_state.py`.
- `scripts/test_instance_journey.py`, the primary journey: cast, study, review, source
  check, template change, update.
- `scripts/test_startup_budget.py` fails if a contract, prompt, or doc tells an agent to read
  everything, if the contract and `PERFORMANCE_BUDGET.yaml` disagree, if a protocol is missing from
  `protocols/README.md`, or if a fresh instance's start-up reading outgrows its budget.
- `.gitattributes` pins LF; the tools preserve a uniformly CRLF `AGENTS.md` and refuse mixed endings.
- `docs/UPGRADING.md`, `docs/architecture.md`, `docs/worked-state-update.md`, and ADRs.

### Changed

- `test_cross_platform_paths.py` scans every file in the tree for machine paths, with no
  exemptions.
- The five session prompts and the start prompt no longer tell agents to read the
  58-file list.
- The StudyState version is `0.12.0`.

### Removed

- `Evidence/` (97 files) and `docs/superpowers/` (7 files): historical records of how the
  template was built, containing machine paths. They remain in Git history.
