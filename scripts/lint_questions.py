#!/usr/bin/env python3
"""Question quality linter for StudyState question banks.

Validates question files under targets/ and EXAMPLES/*/targets/ for schema,
source freshness, answer-key leakage, option position bias, and quality-gate
consistency. Does not perform web search or any network calls.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from check_source_freshness import classify_source, VOLATILITY_MAX_AGE_DAYS

ROOT = Path(__file__).resolve().parent.parent
SOURCE_STATE_PATH = ROOT / "sources" / "SOURCE_STATE.yaml"
TARGETS_DIR = ROOT / "targets"
EXAMPLES_DIR = ROOT / "EXAMPLES"

TRANSFER_COGNITIVE_LEVELS = {"apply", "troubleshoot", "choose-best", "explain", "design"}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover
        print("Error: PyYAML is required.")
        sys.exit(1)

    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        print(f"Error reading {path}: {exc}")
        sys.exit(1)


def parse_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def read_source_state(target_root: Path) -> list[dict[str, Any]]:
    """Read sources/SOURCE_STATE.yaml relative to the target root's repo root.

    For example fixtures, the source state lives under EXAMPLES/<example>/sources/.
    For the main repo, it lives under ROOT/sources/.
    """
    source_state_path = target_root.parent / "sources" / "SOURCE_STATE.yaml"
    data = load_yaml(source_state_path)
    return data.get("sources") or []


def find_source(source_id: str, sources: list[dict[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        if source.get("id") == source_id:
            return source
    return None


def read_target_volatility(target_id: str, target_root: Path) -> str:
    target_yaml = target_root / target_id / "TARGET.yaml"
    if not target_yaml.is_file():
        return "moderate"
    data = load_yaml(target_yaml)
    volatility = data.get("volatility")
    if volatility in VOLATILITY_MAX_AGE_DAYS or volatility == "stable":
        return str(volatility)
    return "moderate"



def question_volatility(question: dict[str, Any], target_volatility: str) -> str:
    volatility = question.get("volatility")
    if volatility in VOLATILITY_MAX_AGE_DAYS or volatility == "stable":
        return str(volatility)
    return target_volatility


def has_fresh_source(
    question: dict[str, Any],
    sources: list[dict[str, Any]],
    target_volatility: str,
    now: datetime,
) -> bool:
    source_ids = question.get("source_ids") or []
    if not source_ids:
        return False
    for sid in source_ids:
        source = find_source(sid, sources)
        if source is None:
            return False
        status, _ = classify_source(source, now, target_volatility)
        if status != "fresh":
            return False
    return True


def source_statuses(
    question: dict[str, Any],
    sources: list[dict[str, Any]],
    target_volatility: str,
    now: datetime,
) -> list[tuple[str, str, str]]:
    """Return list of (source_id, status, reason) for each source_id."""
    result: list[tuple[str, str, str]] = []
    source_ids = question.get("source_ids") or []
    for sid in source_ids:
        source = find_source(sid, sources)
        if source is None:
            result.append((sid, "missing", "source_id not in SOURCE_STATE.yaml"))
            continue
        status, reason = classify_source(source, now, target_volatility)
        result.append((sid, status, reason or ""))
    return result


def extract_answer_key_text(answer_key: Any) -> list[str]:
    """Extract searchable text fragments from a string or structured answer key."""
    fragments: list[str] = []
    if isinstance(answer_key, str):
        fragments.append(answer_key)
    elif isinstance(answer_key, dict):
        for value in answer_key.values():
            if isinstance(value, str):
                fragments.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        fragments.append(item)
                    elif isinstance(item, dict):
                        for sub in item.values():
                            if isinstance(sub, str):
                                fragments.append(sub)
    return fragments


def _normalize(text: str) -> str:
    """Lowercase and collapse non-alphanumeric characters to spaces."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _ngrams(words: list[str], min_n: int) -> list[str]:
    """Return all word n-grams of length min_n or greater."""
    result: list[str] = []
    for n in range(min_n, len(words) + 1):
        for i in range(len(words) - n + 1):
            result.append(" ".join(words[i : i + n]))
    return result


def detect_leakage(question: dict[str, Any]) -> list[str]:
    """Return leakage findings as a list of messages."""
    findings: list[str] = []
    public_prompt = str(question.get("public_prompt", ""))
    if not public_prompt:
        return findings

    normalized_prompt = _normalize(public_prompt)
    if not normalized_prompt:
        return findings

    answer_key = question.get("private_answer_key")
    fragments = extract_answer_key_text(answer_key)
    for fragment in fragments:
        text = fragment.strip()
        if len(text) < 8:
            # Skip very short fragments to avoid false positives from common words.
            continue

        # Whole-fragment match.
        if _normalize(text) in normalized_prompt:
            findings.append("private answer key text appears in public_prompt")
            break

        # N-gram match: any 3+ word phrase shared between key and prompt.
        words = _normalize(text).split()
        if len(words) >= 3:
            for phrase in _ngrams(words, 3):
                if phrase in normalized_prompt:
                    findings.append("private answer key text appears in public_prompt")
                    break
            else:
                continue
            break

    return findings


def _label_to_index(label: str) -> int | None:
    label = str(label).upper().strip()
    if len(label) == 1 and "A" <= label <= "Z":
        return ord(label) - ord("A")
    return None


def _extract_position(question: dict[str, Any]) -> tuple[int, int] | None:
    """Return (correct_index, total_options) if the question has fixed options."""
    options = question.get("options") or question.get("choices")
    if not isinstance(options, list) or len(options) < 2:
        return None

    total = len(options)

    # Direct index fields.
    for key in ("correct_index", "correct_option_index"):
        value = question.get(key)
        if isinstance(value, int):
            return value, total

    # Label fields.
    for key in ("correct_label", "correct_option_label", "answer_label"):
        value = question.get(key)
        idx = _label_to_index(value)
        if idx is not None:
            return idx, total

    # Nested in private_answer_key.
    answer_key = question.get("private_answer_key")
    if isinstance(answer_key, dict):
        for key in ("correct_index", "correct_option_index"):
            value = answer_key.get(key)
            if isinstance(value, int):
                return value, total
        for key in ("correct_label", "correct_option_label", "answer_label"):
            value = answer_key.get(key)
            idx = _label_to_index(value)
            if idx is not None:
                return idx, total

    return None


def discover_question_files(target_id: str | None = None) -> list[tuple[Path, Path]]:
    """Return list of (question_path, target_root) for all discovered questions."""
    found: list[tuple[Path, Path]] = []

    roots: list[Path] = []
    if TARGETS_DIR.is_dir():
        roots.append(TARGETS_DIR)
    if EXAMPLES_DIR.is_dir():
        for example_dir in sorted(EXAMPLES_DIR.iterdir()):
            if not example_dir.is_dir() or example_dir.name.startswith("."):
                continue
            example_targets = example_dir / "targets"
            if example_targets.is_dir():
                roots.append(example_targets)

    for target_root in roots:
        for questions_dir in target_root.rglob("questions"):
            if not questions_dir.is_dir():
                continue
            tid = questions_dir.parent.name
            if target_id is not None and tid != target_id:
                continue
            for question_file in sorted(questions_dir.glob("*.yaml")):
                if question_file.is_file():
                    found.append((question_file, target_root))

    return found


def _quality_gate_value(question: dict[str, Any]) -> str | None:
    quality = question.get("question_quality")
    if isinstance(quality, dict):
        return quality.get("quality_gate")
    return question.get("quality_gate")


def _quality_gate_reason(question: dict[str, Any]) -> str | None:
    quality = question.get("question_quality")
    if isinstance(quality, dict):
        return quality.get("quality_gate_reason")
    return question.get("quality_gate_reason")


def _generated_from_memory_allowed(question: dict[str, Any]) -> bool | None:
    quality = question.get("question_quality")
    if isinstance(quality, dict):
        value = quality.get("generated_from_memory_allowed")
        if value is not None:
            return bool(value)
    value = question.get("generated_from_memory_allowed")
    if value is not None:
        return bool(value)
    return None


def _question_mode(question: dict[str, Any]) -> str | None:
    return question.get("question_mode")


def _readiness_impact(question: dict[str, Any]) -> bool:
    quality = question.get("question_quality")
    if isinstance(quality, dict) and quality.get("readiness_impact") is not None:
        return bool(quality.get("readiness_impact"))
    if question.get("readiness_impact") is not None:
        return bool(question.get("readiness_impact"))
    if question.get("can_affect_readiness") is not None:
        return bool(question.get("can_affect_readiness"))
    return False


def lint_question(
    question: dict[str, Any],
    target_id: str,
    target_root: Path,
    sources: list[dict[str, Any]],
    now: datetime,
    snapshot_exempt: bool = False,
) -> tuple[list[str], list[str]]:
    """Return (failures, warnings) for a single question.

    ``snapshot_exempt`` marks reference fixtures under EXAMPLES/ evaluated
    without an explicit --now clock: their timestamps are deterministic test
    metadata, so wall-clock "stale" results are not failures. Structural
    problems (missing timestamps, unusable sources) still fail.
    """
    failures: list[str] = []
    warnings: list[str] = []

    qid = question.get("id") or "<unknown>"

    # 1. Missing required identifiers.
    for required in ("id", "target_id", "skill_id"):
        if not question.get(required):
            failures.append(f"missing required field '{required}'")

    # Resolve volatility and question mode.
    target_volatility = read_target_volatility(target_id, target_root)
    volatility = question_volatility(question, target_volatility)
    question_mode = _question_mode(question)

    has_source_ref = bool(question.get("source_ref"))
    source_ids = question.get("source_ids")
    has_source_ids = isinstance(source_ids, list) and bool(source_ids)

    # 2. Missing source_ids for moderate/volatile/live topics.
    if volatility in ("moderate", "volatile", "live"):
        if not has_source_ids:
            if has_source_ref:
                warnings.append(
                    f"Question {qid} uses legacy source_ref only. "
                    "Volatile/current questions should use source_ids tied to SOURCE_STATE.yaml."
                )
            else:
                warnings.append(
                    "moderate/volatile/live topic question missing source_ids tied to SOURCE_STATE.yaml"
                )

    # 3 & 7. Volatile/live authoritative_current with stale/missing source.
    if volatility in ("volatile", "live") and question_mode == "authoritative_current":
        if not has_source_ids:
            failures.append(
                "authoritative_current volatile/live question has no source_ids; set quality_gate: fail"
            )
        else:
            statuses = source_statuses(question, sources, volatility, now)
            stale_or_missing = [(sid, status, reason) for sid, status, reason in statuses if status != "fresh"]
            for sid, status, reason in stale_or_missing:
                if snapshot_exempt and status == "stale":
                    continue
                failures.append(
                    f"authoritative_current volatile/live question source '{sid}' is {status}"
                    + (f" ({reason})" if reason else "")
                    + "; set quality_gate: fail"
                )

    # 4. Answer-key leakage in public_prompt.
    leakage = detect_leakage(question)
    failures.extend(leakage)

    # 6. generated_from_memory_allowed permission mismatch.
    gfm = _generated_from_memory_allowed(question)
    if (
        volatility in ("moderate", "volatile", "live")
        and question_mode == "authoritative_current"
        and has_source_ids
        and has_fresh_source(question, sources, volatility, now)
    ):
        if gfm is True:
            failures.append(
                "authoritative_current question with fresh sources must set generated_from_memory_allowed: false"
            )

    # 8. quality_gate_reason required for warn/fail.
    gate = _quality_gate_value(question)
    if gate in ("warn", "fail"):
        reason = _quality_gate_reason(question)
        if not reason:
            failures.append(f"quality_gate is '{gate}' but quality_gate_reason is missing")

    # 10. No transfer probe before readiness upgrade.
    if _readiness_impact(question) and not question.get("transfer_probe"):
        warnings.append("question claims readiness impact but has no transfer_probe")

    return failures, warnings


def check_skill_question_balance(
    questions: list[tuple[dict[str, Any], str, Path]],
) -> dict[str, list[str]]:
    """Return per-skill warnings for recall-heavy question banks."""
    skill_levels: dict[str, list[str]] = defaultdict(list)
    for question, _target_id, _target_root in questions:
        skill_id = question.get("skill_id")
        level = question.get("cognitive_level")
        if skill_id and level:
            skill_levels[skill_id].append(str(level))

    warnings: dict[str, list[str]] = defaultdict(list)
    for skill_id, levels in skill_levels.items():
        recall_count = sum(1 for level in levels if level == "recall")
        non_recall = any(level in TRANSFER_COGNITIVE_LEVELS for level in levels)
        if recall_count >= 3 and not non_recall:
            warnings[skill_id].append(
                f"skill '{skill_id}' has {recall_count} recall-only questions and no application/transfer questions"
            )
    return warnings


def check_option_position_patterns(
    questions: list[tuple[dict[str, Any], str, Path]],
) -> dict[str, list[str]]:
    """Return per-skill warnings when correct options always share the same position."""
    skill_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for question, _target_id, _target_root in questions:
        skill_id = question.get("skill_id")
        if not skill_id:
            continue
        position = _extract_position(question)
        if position is not None:
            skill_positions[skill_id].append(position)

    warnings: dict[str, list[str]] = defaultdict(list)
    for skill_id, positions in skill_positions.items():
        if len(positions) < 2:
            continue
        indices = [idx for idx, _total in positions]
        if len(set(indices)) == 1:
            warnings[skill_id].append(
                f"skill '{skill_id}' correct option is always in position {indices[0] + 1} across {len(positions)} choose-best questions"
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint StudyState question files")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--target-id", help="Limit lint to a single target ID")
    parser.add_argument("--now", default=None, help="ISO 8601 timestamp with timezone for deterministic checks")
    args = parser.parse_args()

    now = parse_now(args.now)

    question_files = discover_question_files(args.target_id)

    per_question_results: list[tuple[str, list[str], list[str]]] = []
    loaded_questions: list[tuple[dict[str, Any], str, Path]] = []

    for question_file, target_root in question_files:
        try:
            question = load_yaml(question_file)
        except Exception as exc:
            qid = question_file.stem
            per_question_results.append((qid, [f"could not parse YAML: {exc}"], []))
            continue

        if not isinstance(question, dict):
            qid = question_file.stem
            per_question_results.append((qid, ["question file is not a YAML mapping"], []))
            continue

        sources = read_source_state(target_root)
        target_id = question.get("target_id") or question_file.parent.parent.name
        qid = question.get("id") or question_file.stem
        snapshot_exempt = (
            EXAMPLES_DIR in question_file.parents and args.now is None
        )
        failures, warnings = lint_question(
            question, target_id, target_root, sources, now, snapshot_exempt=snapshot_exempt
        )
        per_question_results.append((qid, failures, warnings))
        loaded_questions.append((question, target_id, target_root))

    # Cross-question heuristics.
    recall_warnings = check_skill_question_balance(loaded_questions)
    position_warnings = check_option_position_patterns(loaded_questions)

    # Attach cross-question warnings to the first question for each skill so they are surfaced.
    skill_seen: set[str] = set()
    for idx, (question, _target_id, _target_root) in enumerate(loaded_questions):
        skill_id = question.get("skill_id")
        if not skill_id or skill_id in skill_seen:
            continue
        skill_seen.add(skill_id)
        qid, failures, warnings = per_question_results[idx]
        warnings.extend(recall_warnings.get(skill_id, []))
        warnings.extend(position_warnings.get(skill_id, []))
        per_question_results[idx] = (qid, failures, warnings)

    total_failures = sum(1 for _, failures, _ in per_question_results if failures)
    total_warnings = sum(1 for _, failures, warnings in per_question_results if warnings and not failures)
    total_passed = len(per_question_results) - total_failures - total_warnings

    print("Question lint")
    print("")
    print(f"Checked: {len(per_question_results)} question file(s)")
    print("")

    for qid, failures, warnings in per_question_results:
        if failures:
            status = "fail"
        elif warnings:
            status = "warn"
        else:
            status = "pass"
        print(f"{qid}: {status}")
        for msg in failures + warnings:
            print(f"  - {msg}")

    print("")
    print(f"Summary: {total_passed} passed, {total_warnings} warned, {total_failures} failed")

    if total_failures:
        return 1
    if args.strict and total_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
