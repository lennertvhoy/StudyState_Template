# Interview Prep Prompt

Run a StudyState interview rehearsal session.

## Path Verification

1. Run `pwd` and `git rev-parse --show-toplevel`. Confirm the repo root.
2. Run `git remote -v` and confirm it matches the learner's StudyState repo.
3. Run `python3 scripts/check_studydd.py`.

## Setup

1. Follow `AGENTS.md` "Session start": read the context pack, not the repo. Load no other file until the task needs it (`protocols/README.md` indexes the protocols). Build it with `python3 scripts/build_context_pack.py --task start_session` and read `.studydd/context_pack.md`.
2. Identify the target role, company context, active focus, and weak areas.
3. Prepare a mix of behavioral and technical questions appropriate to the role.
4. Use `protocols/QUESTION_QUALITY.md` to design each question.

## Question Types

- **Behavioral** — past experience, conflict, leadership, failure, collaboration
- **Technical** — system design, coding, domain knowledge, tradeoff analysis
- **Role-specific** — product sense, metrics, stakeholder communication, roadmap prioritization

## During The Session

1. Ask one question at a time.
2. State the question ID, type, and expected answer format.
3. Let the learner answer fully before grading.
4. Grade the actual answer, not the answer you expected.
5. Tag mistakes using `protocols/MISTAKE_TAXONOMY.md`.
6. Give concrete feedback on structure, accuracy, clarity, missing details, and weak patterns.
7. Ask a focused repair question if the answer is incomplete.

## Weak Answer Patterns To Flag

- Vague claims without examples
- Missing metrics or outcomes
- Over-explaining or under-explaining
- Skipping the "what would you do differently" part
- Blaming others in behavioral answers
- Jargon without meaning

## Readiness Discipline

- Do not say "you are ready" after one good answer.
- Require repeated, varied evidence before marking a skill as `confirmed`.
- Track weak patterns across multiple answers.
- Update the skill map only from actual demonstrated answers.

## End Of Session

1. Summarize strengths and weak patterns.
2. List evidence items added.
3. Update `state/SKILL_MAP.yaml`.
4. Update `state/STUDY_STATE.yaml` and `sessions/SESSION_LOG.md`.
5. Add weak patterns to `reviews/REVIEW_QUEUE.md`.
6. Propose the next rehearsal question in `NEXT_ACTIONS.md`.
7. Run `python3 scripts/check_studydd.py`.
8. End with one clear next action for the learner.
