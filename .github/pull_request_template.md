## What changed?

## Why?

## How was it validated?

- [ ] `python3 scripts/check_studydd.py` passes
- [ ] `python3 scripts/run_tests.py` passes
- [ ] In the template repository: `python3 scripts/test_instance_journey.py`, `python3 scripts/run_tests.py --clock-offset-days 400`, and `python3 scripts/template_release.py check` pass
- [ ] No unrelated changes

## Does an instance have to do anything?

In the template repository: if this changes the contract block, a managed file, or a stable surface,
`CHANGELOG.md` states the instance action (`none`, `mechanical`, or `semantic`) and the version is bumped.

## Does this keep StudyState agent-native?

StudyState avoids web apps, databases, hosted services, and beginner CLI apps.
