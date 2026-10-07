# Contributing to StudyState_Template

Thank you for helping improve StudyState.

## What fits

- Bug fixes in state files, prompts, or validation script
- Clearer agent instructions
- New examples for certifications or interview prep
- Additional coding-agent platform guides
- Documentation improvements

## What does not fit yet

- Web apps, databases, hosted services, or beginner CLI apps
- Heavy frameworks
- Features that hide the state files from the learner
- Personal learner state in the root public template

## How to contribute

1. Fork the repository.
2. Create a feature branch.
3. Make focused changes.
4. In the template repository, read `core/MAINTAINING.md`: it holds the rules for changing the template.
5. Run `python3 scripts/run_tests.py` and `python3 scripts/check_studydd.py`, and fix any errors.
6. Commit with a clear message.
7. Open a pull request.

## Style

- Keep Markdown readable.
- Keep YAML valid and human-editable.
- Prefer clarity over cleverness.
- Do not inflate readiness in examples.
- Keep the root template generic; real learner instances belong in private copies or clearly marked example folders.
