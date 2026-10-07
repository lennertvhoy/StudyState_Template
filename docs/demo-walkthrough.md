# StudyState Five-Minute Demo Walkthrough

> **Run one command and watch the StudyState learning loop happen.**

```bash
python3 scripts/run_demo_replay.py   # from a checkout of the template
```

This guide is for students, teachers, hiring managers, and anyone who wants to understand what StudyState does without reading the full agent protocol.

---

## 1. What StudyState is

StudyState is a GitHub template that turns a coding agent into a disciplined tutor.

Instead of keeping your learning history inside a chat app or a proprietary database, StudyState keeps it in plain files inside a Git repo:

- `state/` — your current skills, readiness, and focus
- `targets/` — one folder per exam, certification, interview, or skill you are studying
- `reviews/` — spaced-repetition queue
- `sessions/` — session history
- `sources/` — trusted sources
- `NEXT_ACTIONS.md` — the single next thing to study

You own the files. You can inspect, diff, override, or move them anywhere.

---

## 2. Why serious learning should have state

Most AI tutors forget what you already know, inflate your confidence after one easy answer, and lose track of your weak areas.

StudyState fixes that by making learning state explicit:

- **Evidence, not encouragement.** A skill is only marked strong when there is concrete evidence in `state/EVIDENCE_LOG.md`.
- **Honest grading.** The agent grades what you actually said, not what it hoped you would say.
- **Weak areas are tracked.** A partial or wrong answer automatically creates a spaced-repetition review.
- **Override is recorded.** You can always skip a review, but the repo remembers the choice.

---

## 3. How to create a learner instance

The public template is the mold. A learner instance is a copy of the mold with your personal state.

Use the helper script:

```bash
python3 scripts/create_instance.py \
  --target ../Study_MyTopic \
  --remote https://github.com/example/Study_MyTopic.git
```

This:

1. copies the template
2. removes the template Git history
3. initializes a fresh Git repo
4. switches the mode from `template` to `bootstrap`
5. records the template origin for future upgrades

Then open the new folder in your coding agent and say: **"Start a StudyState session."**

---

## 4. How to start a StudyState session

When you ask for a session, the agent:

1. verifies the repo path and remote
2. runs `python3 scripts/check_studydd.py`
3. reads your current state
4. checks if any spaced-repetition reviews are due
5. recommends the next best action
6. asks exactly one question
7. waits for your answer

There is no flood of questions. One question at a time.

---

## 5. What files change after one answer

After you answer one question, the agent updates:

| File | What it records |
|------|-----------------|
| `state/EVIDENCE_LOG.md` | your answer, the verdict, and why |
| `state/SKILL_MAP.yaml` | skill status, readiness, and confidence |
| `reviews/REVIEW_STATE.yaml` | machine-readable review schedule |
| `reviews/REVIEW_QUEUE.md` | human-readable review list |
| `sessions/SESSION_LOG.md` | what was covered this session |
| `NEXT_ACTIONS.md` | the single next step |

You can read any of these files to see exactly how the agent reasoned about your learning state.

---

## 6. How spaced repetition works

StudyState treats due reviews as learning debt. At the start of every session, the agent runs:

```bash
python3 scripts/select_next_study_action.py
```

If a review is due or overdue, the agent says:

> **Recommended by StudyState: review first.** You can override, but this is the highest-retention move.

The scheduler uses a simple, transparent interval map:

| Result | Confidence | Next review |
|--------|------------|-------------|
| Wrong | low | same day |
| Wrong | medium/high | 1 day |
| Partial | any | 1 day |
| Correct | low | 2 days |
| Correct | medium | 4 days |
| Correct | high | 7 days |

A future version can swap in FSRS or SM-2 without changing the file surface.

---

## 7. How override works

You are in control. If you want to skip a due review and study something new, the agent accepts the override and records it in `reviews/REVIEW_OVERRIDES.md`:

- when it happened
- which review was skipped
- why you skipped it
- what you chose instead
- when to revisit it

This keeps the study state honest. Silent neglect is not allowed.

---

## 8. How validation proves the repo is healthy

Run the validator at any time:

```bash
python3 scripts/check_studydd.py
```

It checks:

- required files exist
- YAML parses correctly
- mode matches the repo type (template, bootstrap, or learner instance)
- evidence references point to real evidence
- review skills exist in the skill map
- readiness claims are backed by evidence
- no answer keys leak into learner-facing files

If validation passes, the repo is in a consistent, auditable state.

---

## 9. What to show in a five-minute demo

Run:

```bash
python3 scripts/run_demo_replay.py
```

You will see, in about a minute:

1. A learner instance is created from the template.
2. A fake learner profile is initialized.
3. A fake target is added: **AI Search Fundamentals Demo**.
4. The agent asks one question.
5. The learner gives a partial answer.
6. The agent grades it honestly: **partial**.
7. Evidence is written to `state/EVIDENCE_LOG.md`.
8. A review is scheduled for the next day.
9. The selector shows **review first** when the review is due.
10. An override is recorded with a reason.
11. Validation passes.

After the replay, open `EXAMPLES/demo_ai_search_exam/` to see the final state as plain files.

---

## What to try next

- Read the full agent contract in `AGENTS.md`.
- Create your own instance with `scripts/create_instance.py`.
- Start a real session in your coding agent and answer your first question.
