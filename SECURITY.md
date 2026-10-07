# Security and privacy

## Reporting a problem

If you find a vulnerability in the template's scripts, or learner data leaking through a script or a
document, please do not post the details in a public issue. Use GitHub's "Report a vulnerability"
button on the Security tab if it is shown. Otherwise open an issue that says only that you have a
security concern, with no details, and the maintainer will arrange a private channel. Include, once
you have one, what you ran, what you expected, and what happened.

## What the template promises

- **The template holds no learner data.** `scripts/check_studydd.py` fails if a learner file is
  populated here, and a test scans every file for private paths.
- **Your instance is yours.** `scripts/create_instance.py` copies files and starts a fresh Git history;
  it never contacts a network, installs software, or pushes. Nothing leaves your machine unless you push.
- **Scripts avoid surprises.** They use the standard library and PyYAML only, never run `sudo`, and
  install nothing without your explicit consent (`docs/setup.md`).
- **The updater cannot touch your state.** `scripts/update_instance.py` replaces only template-owned
  files, refuses to overwrite a file you edited, and refuses a damaged lock.

## What you should do

- Keep a learner instance private unless you have reviewed it. Run `python3 scripts/agent_privacy_check.py`
  before pushing an instance anywhere shared (`protocols/PRIVACY_REVIEW.md`).
- Remember that a coding agent reads your files. Do not put secrets, credentials, or other people's
  personal data in an instance.
