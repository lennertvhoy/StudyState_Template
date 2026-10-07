# Evidence: template-hardening-001

## Scope and authorization

The owner asked an agent to analyze this template, compare it with the other StatePort-family
templates and the ProjectState template ("the best one I got"), and change it however it saw fit to
make it the best it can be; then to push it and make sure the public repository is the best template
for anyone to use. `PROJECT.md` and this slice were drafted by the agent and need the owner's
confirmation. The decisions are recorded in `docs/adr/0001` to `0004`.

## Primary journey

- Environment: Linux x86_64 workstation, system Python 3.13.15 with PyYAML 6.0.3 and git 2.55.0; this checkout on branch studystate/v6-core-0.12.0 with all code committed and clean, cast into a throwaway directory.
- Command: `python3 scripts/test_instance_journey.py`
- Result: passed
- Exit code: 0

The journey ran 26 checks. It cast an instance from this checkout (validator green, its own ProjectState
gate honestly red with no size warning, no template maintenance files copied, a lock recorded); ran a
weak answer through a review that became due, was recorded correct (interval doubled to 2 days) and then
lapsed (reset to same-day), with the validator accepting every state; showed that a volatile target needs a
source check, that the validator refuses it until one is recorded, and that recording it ends the routing;
then released a change in a template copy and updated the instance, which changed template-owned files and
the contract block and left learner state, the ProjectState files, and a local rule byte-identical.

## Secondary checks

- `python3 scripts/run_tests.py`: 25 of 25 test scripts passed on the real clock (Python 3.13.15) and under
  Python 3.14. `python3 scripts/run_tests.py --clock-offset-days 400` passed 25 of 25; the runner verified in
  a child process that the shift took effect, which found and fixed a double shift of `date.today()` in
  the shim.
- Inside a cast instance, its own suite (5 tests) and its CI passed. Before, 13 of the 20 test scripts
  shipped to an instance failed there.
- `check_studydd.py`, `template_release.py check`, `lint_questions.py`, and the demo and source-check
  commands from CI exit 0. `ruff check scripts --select F,E9` is clean (it found an undefined name).
- `python3 scripts/projectstate_gate.py` exits 0. ProjectState's own `projectstate_update.py --check` reports the
  gate and contract at release 6.3.0, and its read-only fleet report lists this repository as v6 with gate
  and contract `current`, no notices, no size flag, and a start-up reading of 4,090 tokens.
- Mutation-style checks: 13 `update_instance` scenarios (edited file, edited block, uncommitted work, no lock,
  older instance, symlink, CRLF and mixed endings, unsafe targets, idempotence, two releases) and 11
  `template_release` scenarios pass; two of them found real defects while being written (a pseudo-path
  copied as a file; the dirty-tree guard firing when nothing would be written).

Measured before and after (the commit before this slice, `3bf1048`, against the working tree):

| | Before | After |
| --- | --- | --- |
| `AGENTS.md` | 30,252 bytes, 551 lines | 12,090 bytes, 228 lines including the 82-line ProjectState block |
| Mandatory start-up reading | 58 files, about 169 KB, roughly 42,000 tokens; budget 20 files | the contract, the context pack, one study skill |
| A fresh instance's `AGENTS.md` | the whole template contract | 11,354 bytes, 218 lines; no gate size warning |
| Tracked files | 281 | 221 (104 deleted, 49 modified, 31 new) |
| Tests run in CI | 15 of 16, listed by hand | 25 of 25, discovered |

## Artifacts

- The working tree: new `core/` (contract source, ownership, instance scaffolds, maintenance notes),
  `docs/UPGRADING.md`, `docs/architecture.md`, `docs/worked-state-update.md`, `docs/adr/`, `protocols/README.md`,
  `scripts/` additions (`update_instance.py`, `template_release.py`, `template_ownership.py`, `state_io.py`,
  `review_state.py`, `run_tests.py`, tests), the ProjectState core files and gate, and a rewritten README,
  CHANGELOG, CI workflow, and `AGENTS.md`.
- Local tag `pre-v6-core` at `3bf1048`: the removed `Evidence/` and `docs/superpowers/` are reachable with
  `git show pre-v6-core:Evidence/`.
- Backup of the three uncommitted refresh notices that were in `AGENTS.md` before this work (retired by the
  owner's decision D6) in the owner's ProjectState backup folder, with checksums.

## Delivery (a separate claim from the journey above)

- Pushed as branch `studystate/v6-core-0.12.0` and opened as pull request #7 against `main`. The tag
  `pre-v6-core` was pushed so the removed history is reachable from the remote.
- CI run on the final commit passed all four jobs: `validate` on ubuntu, windows and macos (Python 3.13: the
  whole suite, plus on ubuntu the suite 400 days ahead, the validator, the release check, the ProjectState gate,
  lint, and the demo commands) and `minimum-python` (Python 3.10). The first run found real Windows
  portability bugs that no local run could (the context pack and the evidence index used backslash paths);
  they are fixed in the same pull request.
- A fresh clone of the branch passed the journey, 25 of 25 tests on both clocks, the release check and the gate.

## Limitations

- The GitHub-side settings (the repository flagged as a template, topics) are changed after the merge and are
  not part of this slice's tree.
- Open pull requests were not merged as such. The source-check completion flow (#4) was ported by hand, with
  its clock-dependent tests fixed, so #4 is largely superseded. Fast-drill mode (#5), the transactional-hardening
  branch (#6), and the unmerged lifecycle-manifest and portable-actions branches were left alone: they are product
  decisions. StatePort's adapter binds to that lifecycle-manifest line, not to what is on `main`.
- Existing instances are not touched. One cast earlier has a 700-line `AGENTS.md` and many edited scripts; it needs
  the one-time conversion in `docs/UPGRADING.md` and a by-hand reconciliation of its edits before mechanical updates help.
- The interval rule is a simple map, not FSRS or SM-2. The new scheduler paths have synthetic tests, not a
  real learner's data.
- Human acceptance is pending. `PROJECT.md` is an agent draft.
