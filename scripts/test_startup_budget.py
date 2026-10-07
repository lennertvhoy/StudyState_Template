#!/usr/bin/env python3
"""Guards against the start-up reading growing back.

The contract once told agents to read 58 files (about 42,000 tokens) before the first
question, against a declared budget of 20, and every slice added to the list. These tests
fail when a contract, prompt, or protocol index drifts back that way.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import template_ownership as own  # noqa: E402
import testkit  # noqa: E402

ROOT = testkit.ROOT

# Phrases that tell an agent to load everything.
LOAD_EVERYTHING = re.compile(r"required first actions|read all (the )?files|read every file|read the entire repo", re.IGNORECASE)
INSTANCE_AGENTS_MAX_BYTES = 18_000


def instruction_files() -> list[Path]:
    paths = [ROOT / "AGENTS.md", ROOT / own.CORE_BLOCK_PATH, ROOT / "README.md"]
    for folder in ("PROMPTS", "protocols", "docs"):
        paths += sorted((ROOT / folder).glob("*.md"))
    return [p for p in paths if p.is_file()]


def test_nothing_tells_an_agent_to_read_everything() -> None:
    offenders = [
        p.relative_to(ROOT).as_posix()
        for p in instruction_files()
        if LOAD_EVERYTHING.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"these files tell an agent to load everything: {offenders}"


def test_the_contract_and_the_budget_agree() -> None:
    block = (ROOT / own.CORE_BLOCK_PATH).read_text(encoding="utf-8")
    budget = testkit.load_yaml(ROOT / "state" / "PERFORMANCE_BUDGET.yaml")["budgets"]["session_boundary"]["max_files_loaded"]
    assert f"{budget} files" in block, "the contract must state the session-boundary budget that PERFORMANCE_BUDGET.yaml declares"


def test_every_protocol_is_indexed() -> None:
    index = (ROOT / "protocols" / "README.md").read_text(encoding="utf-8")
    missing = [p.stem for p in sorted((ROOT / "protocols").glob("*.md")) if p.name != "README.md" and f"{p.stem}.md" not in index]
    assert not missing, f"protocols missing from protocols/README.md: {missing}"


def test_the_template_agents_md_stays_within_the_gates_size_limit() -> None:
    gate = testkit.script("projectstate_gate.py", cwd=ROOT, check=False)
    assert "WARN: AGENTS.md" not in gate.stdout, gate.stdout


def test_a_new_instances_start_up_reading_is_small() -> None:
    with testkit.tempdir("studystate-budget-") as tmp:
        inst = testkit.make_learner_instance(Path(tmp))
        size = (inst / "AGENTS.md").stat().st_size
        assert size <= INSTANCE_AGENTS_MAX_BYTES, f"a fresh instance's AGENTS.md is {size} bytes (limit {INSTANCE_AGENTS_MAX_BYTES})"

        testkit.script("compact_state.py", cwd=inst)
        pack = testkit.script("build_context_pack.py", "--task", "start_session", cwd=inst)
        match = re.search(r"Files included:\s*(\d+)", pack.stdout)
        assert match, pack.stdout
        budget = testkit.load_yaml(inst / "state" / "PERFORMANCE_BUDGET.yaml")["budgets"]["session_boundary"]["max_files_loaded"]
        assert int(match.group(1)) <= budget, f"the start-up context pack loads {match.group(1)} files; the budget is {budget}"


def test_every_script_parses_as_python_3_10() -> None:
    """The README promises Python 3.10 or newer. CI runs 3.10; this catches syntax slips sooner."""
    import ast

    failures = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))
        except SyntaxError as exc:
            failures.append(f"{path.name}: {exc.msg} (line {exc.lineno})")
    assert not failures, failures


def main() -> int:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed: list[tuple[str, BaseException]] = []
    for test in tests:
        print(f"Running {test.__name__}...")
        try:
            test()
            print("  passed")
        except BaseException as exc:  # noqa: BLE001 - report every failure, then exit non-zero
            print(f"  failed: {exc!r}")
            failed.append((test.__name__, exc))
    if failed:
        print("\nFailed tests:")
        for name, exc in failed:
            print(f"  - {name}: {exc!r}")
        return 1
    print("\nAll start-up budget tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
