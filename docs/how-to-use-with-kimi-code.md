# How To Use StudyState With Kimi Code

## Setup

1. From a checkout of `StudyState_Template`, cast your own instance:
   `python3 scripts/create_instance.py --target ../Study_Me --remote https://github.com/example/Study_Me.git`.
   Do not study in the template itself; it is the mold (`docs/agent-native-quickstart.md`).
2. Open the new `Study_Me` folder in Kimi Code.

## Start A Study Session

1. Open `PROMPTS/coding_agent_start_prompt.md`.
2. Copy the entire prompt.
3. Paste it into Kimi Code.
4. Ask Kimi Code to initialize your instance.

Example:

```text
[paste the start prompt here]

Initialize this StudyState instance for me. I want to prepare for an interview. Ask only the essential setup questions first.
```

## During The Session

- Answer one question at a time.
- If the agent's grading feels wrong, challenge it.
- Ask the agent to show you the active question ID and answer key after you answer if needed.

## End Of Session

- Let the agent propose state updates.
- Confirm or correct them.
- Ask the agent to run `python3 scripts/check_studydd.py`.
- Inspect `NEXT_ACTIONS.md` for the next study move.

## Tips

- Kimi Code can read and edit the state files directly. Let it.
- If context resets, re-paste the start prompt.
- Use `PROMPTS/exam_drill_prompt.md` before an exam.
- Use `PROMPTS/reflection_prompt.md` to capture what still feels uncertain.
