# Study Session Prompt

Run a focused StudyState study session.

## Path Verification

1. Run `pwd` and `git rev-parse --show-toplevel`. Confirm the repo root.
2. Run `git remote -v` and confirm it matches the learner's StudyState repo.
3. Run `python3 scripts/check_studydd.py`.

## Setup

1. Follow `AGENTS.md` "Session start": read the context pack, not the repo. Load no other file until the task needs it (`protocols/README.md` indexes the protocols).
2. Choose session mode: deep, normal, low-energy, or recovery.
3. Identify the active target, active focus, weakest skill, pending topic, or due review.
4. Select the next best question using `protocols/SELECT_NEXT_ACTION.md`.

## During The Session

1. Ask one question at a time.
2. State the active question ID and expected answer format.
3. Wait for the learner's answer.
4. Grade the actual answer against the answer key.
5. Explain the verdict in plain language.
6. Tag mistakes using `protocols/MISTAKE_TAXONOMY.md`.
7. If needed, ask a repair question.
8. Close the question before opening the next.

## Question Selection Rules

- Prioritize weak areas and due reviews.
- Mix conceptual and applied questions across a session.
- Match difficulty to the learner's current readiness estimate.
- Avoid asking the same question repeatedly.
- Use trusted sources from `sources/SOURCE_INDEX.md` when writing or checking questions.

## End Of Session

1. Summarize what was covered.
2. List evidence items.
3. Identify weak areas.
4. Propose updates to the skill map and state.
5. Add review items for weak or repaired answers using `protocols/SCHEDULE_REVIEW.md`.
6. Propose the next study action in `NEXT_ACTIONS.md`.
7. Run `python3 scripts/check_studydd.py`.
8. Leave a clean worktree and truthful handoff.
