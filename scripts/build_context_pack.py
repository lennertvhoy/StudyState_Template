#!/usr/bin/env python3
"""Build a task-specific StudyState context pack.

The context pack is the agent's normal runtime context. It loads compact state,
relevant evidence, and task-specific files while skipping raw audit logs unless
the task is audit or references cannot be resolved.

This script supports fast-path tutoring by allowing the caller to narrow the
context to a single skill, question, or review. It prints file counts and warns
if the configured performance budget is exceeded.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from check_source_freshness import VOLATILITY_MAX_AGE_DAYS
from next_activity_decision import (
    choose_activity_decision,
    count_due_reviews,
    find_weakest_skill,
    recent_activity_types,
)

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_PACK_DIR = ROOT / ".studydd"
CONTEXT_PACK_PATH = CONTEXT_PACK_DIR / "context_pack.md"
STATE_CACHE_PATH = CONTEXT_PACK_DIR / "state_cache.json"
PERFORMANCE_BUDGET_PATH = ROOT / "state" / "PERFORMANCE_BUDGET.yaml"

CANONICAL_STATE_FILES = [
    "state/STUDY_STATE.yaml",
    "state/SKILL_MAP.yaml",
    "reviews/REVIEW_STATE.yaml",
    "state/STUDYDD_MODE.yaml",
    "state/STUDYDD_TEMPLATE_VERSION.yaml",
    "state/STATE_MANIFEST.yaml",
    "state/PERFORMANCE_BUDGET.yaml",
    "state/ACTIVITY_STATE.yaml",
]

SUMMARY_FILES = [
    "state/CURRENT_CONTEXT.md",
    "state/EVIDENCE_INDEX.yaml",
    "sessions/SESSION_SUMMARIES.md",
    "NEXT_ACTIONS.md",
]

RAW_AUDIT_FILES = [
    "state/EVIDENCE_LOG.md",
    "sessions/SESSION_LOG.md",
    "reviews/REVIEW_OVERRIDES.md",
]


def load_yaml(path: Path) -> dict:
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
        print(f"Warning: could not read {path}: {exc}")
        return {}


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def read_text(path: Path, max_chars: int | None = None) -> str:
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"[Error reading {path}: {exc}]"
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + f"\n\n[... truncated at {max_chars} characters; full file in {path.relative_to(ROOT)}]"
    return text


def active_target_id(study_state: dict) -> str | None:
    return study_state.get("active_target_id") or None


def active_target_path(study_state: dict) -> Path | None:
    tid = active_target_id(study_state)
    if not tid:
        return None
    path = ROOT / "targets" / tid / "TARGET.yaml"
    if path.is_file():
        return path
    return None


def active_study_skill(target_path: Path | None) -> str | None:
    if not target_path:
        return None
    data = load_yaml(target_path)
    return data.get("study_skill") or None


def import_check_source_freshness() -> object:
    """Import helper functions from scripts/check_source_freshness.py."""
    spec = importlib.util.spec_from_file_location(
        "check_source_freshness", ROOT / "scripts" / "check_source_freshness.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_source_freshness"] = module
    spec.loader.exec_module(module)
    return module


def build_source_freshness_section(target_id: str, csf: object) -> tuple[list[str], str]:
    """Return (lines, volatility_class) for the active target."""
    volatility, declared, warning = csf.read_target_volatility(target_id)
    source_state = load_yaml(ROOT / "sources" / "SOURCE_STATE.yaml")
    all_sources = source_state.get("sources") or []
    target_sources = [s for s in all_sources if target_id in s.get("target_ids", [])]

    now = datetime.now(timezone.utc)
    fresh: list[dict] = []
    stale: list[tuple[dict, str | None]] = []
    unverified: list[tuple[dict, str | None]] = []
    missing_ts: list[tuple[dict, str | None]] = []

    for source in target_sources:
        status, reason = csf.classify_source(source, now, volatility)
        if status == "fresh":
            fresh.append(source)
        elif status == "stale":
            stale.append((source, reason))
        elif status == "unverified":
            unverified.append((source, reason))
        else:
            missing_ts.append((source, reason))

    lines: list[str] = [
        "## Source freshness status",
        "",
        f"- **Target volatility:** {volatility}"
        + ("" if declared else " (defaulted)"),
    ]
    if warning:
        lines.append(f"- **Warning:** {warning}")

    lines.extend(["", "**Fresh usable sources:**"])
    if fresh:
        sorted_fresh = sorted(fresh, key=lambda s: csf.authority_rank(s.get("authority")))
        for source in sorted_fresh[:3]:
            lines.append(
                f"- {source.get('id', '<unknown>')} ({source.get('authority', 'unknown')})"
            )
    else:
        lines.append("- (none)")

    problematic = stale + unverified + missing_ts
    lines.extend(["", "**Stale / missing / unverified sources:**"])
    if problematic:
        for source, reason in problematic[:3]:
            reason_text = f" — {reason}" if reason else ""
            lines.append(f"- {source.get('id', '<unknown>')}{reason_text}")
    else:
        lines.append("- (none)")

    fresh_official = [s for s in fresh if s.get("authority") in ("official", "high_authority")]
    if fresh_official:
        best = min(fresh_official, key=lambda s: csf.authority_rank(s.get("authority")))
        rec = f"Use fresh authoritative source {best.get('id')} for new authoritative-current questions."
    elif fresh:
        best = min(fresh, key=lambda s: csf.authority_rank(s.get("authority")))
        rec = f"Use fresh source {best.get('id')} for new questions, but verify authority."
    else:
        rec = "No fresh usable sources. Generate conceptual-practice questions only until sources are refreshed."
    if volatility in ("volatile", "live"):
        rec += " Do not generate product-current questions from memory."

    lines.extend(["", f"**Recommendation:** {rec}", ""])
    return lines, volatility


def _last_checked_for_target(source_state: dict, target_id: str | None) -> str:
    if not target_id:
        return "none"
    sources = (source_state or {}).get("sources") or []
    checked: list[str] = []
    for source in sources:
        if target_id in source.get("target_ids", []):
            ts = source.get("last_checked_at")
            if ts:
                checked.append(str(ts))
    return max(checked) if checked else "none"


def build_next_activity_source_freshness_section(
    decision: Any,
    target_data: dict,
    target_id: str | None,
    source_state: dict,
) -> list[str]:
    signals = decision.signals
    if not signals.get("source_freshness_checked"):
        return [
            "Source freshness:",
            "- Status: not_required",
            f"- Rule ID: {decision.rule_id}",
            "- Why: No active target/source freshness decision required.",
        ]

    status = signals.get("source_freshness_status") or "unknown"
    rule_id = signals.get("source_freshness_rule_id") or decision.rule_id
    volatility = (
        signals.get("source_freshness_target_volatility")
        or target_data.get("volatility")
        or "stable"
    )
    window = 365 if volatility == "stable" else VOLATILITY_MAX_AGE_DAYS.get(volatility, 90)
    last_checked = _last_checked_for_target(source_state, target_id)

    if decision.activity_type == "recent_info_check":
        why = decision.reason
    elif status == "fresh" and signals.get("source_freshness_has_fresh_usable"):
        why = (
            f"Source freshness satisfied for target '{target_id}' — "
            f"{signals.get('source_freshness_fresh_count', 0)} fresh source(s); moved to next rule."
        )
    elif signals.get("source_freshness_recent_activity_fallback") and signals.get(
        "recent_info_check_in_recent_types"
    ):
        why = "recent_info_check already appears in recent activities; skipping to next rule."
    else:
        why = f"Source freshness status is {status}, but a higher-priority rule applied first."

    return [
        "Source freshness:",
        f"- Status: {status}",
        f"- Rule ID: {rule_id}",
        f"- Volatility: {volatility}",
        f"- Freshness window: {window} days",
        f"- Last checked: {last_checked}",
        f"- Why: {why}",
    ]


def _adjustment_message(tag: str, count: int) -> str:
    topic = tag.replace("-", " ")
    if topic.endswith(" confusion"):
        topic = topic[: -len(" confusion")]
    strength = "strong" if count >= 3 else "moderate"
    if tag == "service-boundary-confusion":
        adjustment = "Do two short comparison drills before adding new material."
    else:
        adjustment = "Do a focused review drill before adding new material."
    return (
        f"You keep missing {topic} questions.\n"
        f"Recommended adjustment: {adjustment}\n"
        f"Why: The last {count} weak evidence items relate to {topic}.\n"
        f"Strength: {strength}. You can accept, modify, or override this."
    )


def _overdue_review_message(count: int) -> str:
    return (
        f"You have {count} overdue review item{'s' if count != 1 else ''}.\n"
        "Recommended adjustment: Do your due reviews before adding new material.\n"
        "Why: Spaced repetition is most effective when reviews are on time.\n"
        "Strength: moderate. You can accept, modify, or override this."
    )


def emulate_suggest_study_adjustment(evidence_index: dict, review_state: dict) -> str:
    """Emulate scripts/suggest_study_adjustment.py using compact indexes only."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)
    weak_verdicts = {"partial", "incorrect", "unclear", "wrong"}
    tag_counts: dict[str, int] = {}

    for item in evidence_index.get("items") or []:
        verdict = str(item.get("verdict", "")).lower()
        if verdict not in weak_verdicts:
            continue
        date_str = item.get("date", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(str(date_str))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                continue
        tags = item.get("mistake_type") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.replace(",", " ").split() if t.strip()]
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    strong_tag: str | None = None
    moderate_tag: str | None = None
    # Deterministic ordering: highest count first, then alphabetical.
    for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
        if count >= 3:
            strong_tag = tag
            break
        if count == 2 and moderate_tag is None:
            moderate_tag = tag

    if strong_tag:
        return _adjustment_message(strong_tag, tag_counts[strong_tag])

    overdue_count = 0
    for item in review_state.get("review_items") or []:
        status = item.get("status")
        if status in ("completed", "suspended"):
            continue
        due_at_str = item.get("due_at")
        if not due_at_str:
            continue
        try:
            due_at = datetime.fromisoformat(str(due_at_str))
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)
            if due_at <= now:
                overdue_count += 1
        except Exception:
            continue

    if overdue_count > 0:
        return _overdue_review_message(overdue_count)

    if moderate_tag:
        return _adjustment_message(moderate_tag, tag_counts[moderate_tag])

    return "No recommendation: insufficient evidence."


def build_learner_adaptation_section(evidence_index: dict, review_state: dict) -> list[str]:
    """Build learner adaptation summary from compact state."""
    profile = load_yaml(ROOT / "state" / "LEARNER_PROFILE.yaml")
    prefs = profile.get("learner_preferences") or {}
    adaptation = profile.get("adaptation_state") or {}

    source_refresh_pref = prefs.get("source_refresh_preference") or "not set"
    recurring_friction = adaptation.get("recurring_friction") or []

    suggestion = emulate_suggest_study_adjustment(evidence_index, review_state)

    lines: list[str] = [
        "## Learner adaptation summary",
        "",
        f"- **Source refresh preference:** {source_refresh_pref}",
        "",
        "**Current study adjustment recommendation:**",
        "",
    ]
    lines.extend(suggestion.splitlines())
    lines.extend([
        "",
        "**Recent recurring friction:**",
    ])
    if recurring_friction:
        for item in recurring_friction[:3]:
            lines.append(f"- {item}")
    else:
        lines.append("- None recorded.")
    lines.append("")
    return lines


def build_question_quality_section(volatility: str) -> list[str]:
    """Build question quality requirements for the active target."""
    if volatility in ("volatile", "live"):
        freshness_req = (
            "A fresh official or high-authority source is required for authoritative-current questions."
        )
        mode_guidance = (
            "Authoritative-current questions are gated; fall back to conceptual-practice "
            "or source-grounded recall if no fresh source exists."
        )
    elif volatility == "moderate":
        freshness_req = (
            "A fresh source (within the moderate volatility window) is required for authoritative-current questions."
        )
        mode_guidance = (
            "Prefer source-grounded questions; mark memory-generated product-current questions as practice-only."
        )
    else:
        freshness_req = (
            "Stale sources are acceptable for stable topics, but prefer fresh authoritative sources."
        )
        mode_guidance = (
            "Authoritative-current questions are generally safe; still verify against trusted sources."
        )

    return [
        "## Question quality requirements",
        "",
        f"- **Target volatility:** {volatility}",
        f"- **Required source freshness for authoritative_current:** {freshness_req}",
        f"- **Question mode guidance:** {mode_guidance}",
        "- **Quality gate reminder:** Use `protocols/QUESTION_QUALITY_GOVERNOR.md` for every generated question. Keep the answer key private until grading.",
        "",
    ]


def load_performance_budget() -> dict:
    data = load_yaml(PERFORMANCE_BUDGET_PATH)
    return data.get("budgets") or {}


def mode_for_task(task: str) -> str:
    data = load_yaml(PERFORMANCE_BUDGET_PATH)
    rule = (data.get("rules") or {}).get(task)
    if rule and isinstance(rule, dict):
        return rule.get("mode", "fast_path")
    if task in ("start_session", "close_session"):
        return "session_boundary"
    if task in ("audit", "repair", "upgrade_instance"):
        return "deep_audit"
    return "fast_path"


def relevant_skill_ids(
    study_state: dict,
    skill_map: dict,
    review_state: dict,
    active_skill_filter: str | None,
) -> set[str]:
    relevant: set[str] = set()

    if active_skill_filter:
        relevant.add(active_skill_filter)

    active_focus = study_state.get("active_focus") or {}
    if active_focus.get("current_topic"):
        # Heuristic: include skills whose label/id/topic appears in current_topic.
        topic = active_focus["current_topic"].lower()
        for skill in skill_map.get("skills") or []:
            tokens = " ".join(
                filter(
                    None,
                    [
                        str(skill.get("id", "")),
                        str(skill.get("label", "")),
                        str(skill.get("next_validation_question", "")),
                    ],
                )
            ).lower()
            if any(part in tokens for part in topic.split()):
                relevant.add(skill.get("id"))

    for skill in skill_map.get("skills") or []:
        if skill.get("status") in ("weak", "blocked"):
            relevant.add(skill.get("id"))

    for item in review_state.get("review_items") or []:
        sid = item.get("skill_id")
        if sid:
            relevant.add(sid)

    return relevant


def relevant_evidence_excerpts(
    evidence_index: dict,
    skill_ids: set[str],
    active_question: str | None,
    max_items: int = 5,
) -> list[dict]:
    items = evidence_index.get("items") or []
    relevant = [
        item for item in items
        if item.get("skill_id") in skill_ids
        or (active_question and item.get("question_id") == active_question)
    ]
    # Prefer weak/partial verdicts and most recent.
    relevant.sort(
        key=lambda item: (
            item.get("verdict", "") not in ("partial", "incorrect", "weak"),
            item.get("date", ""),
        ),
        reverse=True,
    )
    return relevant[:max_items]


def relevant_reviews(review_state: dict, review_id: str | None, skill_ids: set[str]) -> list[dict]:
    items = review_state.get("review_items") or []
    if review_id:
        return [item for item in items if item.get("id") == review_id]
    return [item for item in items if item.get("skill_id") in skill_ids]


def cache_used() -> bool:
    return STATE_CACHE_PATH.is_file()


def build_context_pack(
    task: str,
    active_skill: str | None = None,
    active_question: str | None = None,
    review_id: str | None = None,
    skill_id: str | None = None,
) -> tuple[str, list[tuple[str, str]], list[tuple[str, str]], dict]:
    """Return (pack body, included list, skipped list, metadata)."""
    included: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []
    body_lines: list[str] = []
    metadata: dict = {
        "task": task,
        "mode": mode_for_task(task),
        "files_included": 0,
        "files_skipped": 0,
        "raw_log_files_loaded": 0,
        "cache_used": cache_used(),
    }

    generated_at = datetime.now(timezone.utc).isoformat()

    body_lines.extend([
        "# StudyState Context Pack",
        "",
        f"- **Task:** {task}",
        f"- **Mode:** {metadata['mode']}",
        f"- **Generated at:** {generated_at}",
        f"- **Repo root:** {ROOT}",
        "",
        "## Loading policy",
        "",
        "This pack loads compact canonical state and derived summaries first. "
        "Raw append-only audit logs are referenced only when needed for the task.",
        "",
    ])

    # Load canonical state.
    study_state: dict = {}
    skill_map: dict = {}
    review_state: dict = {}
    mode_data: dict = {}

    for rel in CANONICAL_STATE_FILES:
        path = ROOT / rel
        if path.is_file():
            included.append((rel, "canonical state or manifest"))
        else:
            skipped.append((rel, "file missing"))

    study_state = load_yaml(ROOT / "state" / "STUDY_STATE.yaml")
    skill_map = load_yaml(ROOT / "state" / "SKILL_MAP.yaml")
    review_state = load_yaml(ROOT / "reviews" / "REVIEW_STATE.yaml")
    mode_data = load_yaml(ROOT / "state" / "STUDYDD_MODE.yaml")
    evidence_index = load_yaml(ROOT / "state" / "EVIDENCE_INDEX.yaml")

    target_path = active_target_path(study_state)
    study_skill = active_study_skill(target_path)
    if active_skill:
        study_skill = active_skill

    body_lines.extend([
        "## Mode and remote",
        "",
        f"- **Mode:** {mode_data.get('mode', 'unknown')}",
        f"- **Template remote:** {mode_data.get('template_remote', 'unknown')}",
        f"- **Public safe:** {mode_data.get('public_safe', 'unknown')}",
        f"- **Context pack cache used:** {metadata['cache_used']}",
        "",
        "## Active target",
        "",
    ])

    if target_path:
        included.append((str(target_path.relative_to(ROOT)), "active target metadata"))
        body_lines.append(f"- **Target ID:** {active_target_id(study_state)}")
        body_lines.append(f"- **Target file:** {target_path.relative_to(ROOT)}")
        target_data = load_yaml(target_path)
        body_lines.append(f"- **Target type:** {target_data.get('type', 'not set')}")
        if study_skill:
            body_lines.append(f"- **Study skill:** {study_skill}")
            skill_file = ROOT / "study_skills" / study_skill / "SKILL.md"
            if skill_file.is_file():
                included.append((str(skill_file.relative_to(ROOT)), f"active study skill policy for {study_skill}"))
            else:
                body_lines.append(f"- **Warning:** declared study skill '{study_skill}' has no SKILL.md at {skill_file.relative_to(ROOT)}")
                skipped.append((str(skill_file.relative_to(ROOT)), "declared study skill file missing"))
        else:
            body_lines.append("- **Study skill:** generic (none declared)")
            generic_file = ROOT / "study_skills" / "generic" / "SKILL.md"
            if generic_file.is_file():
                included.append((str(generic_file.relative_to(ROOT)), "generic fallback study skill"))
    else:
        body_lines.append("- **Target ID:** none")
        skipped.append(("targets/<active>/TARGET.yaml", "no active target"))

    body_lines.append("")

    # Active activity and recent effectiveness.
    activity_state = load_yaml(ROOT / "state" / "ACTIVITY_STATE.yaml")
    templates_data = load_yaml(ROOT / "activities" / "ACTIVITY_TEMPLATES.yaml")
    templates = templates_data.get("templates") or []
    target_data = load_yaml(target_path) if target_path else {}
    source_state = load_yaml(ROOT / "sources" / "SOURCE_STATE.yaml")
    now = datetime.now(timezone.utc)
    weakest_skill = find_weakest_skill(skill_map)
    decision = choose_activity_decision(
        skill_id=skill_id or active_skill,
        due_reviews=count_due_reviews(review_state),
        weakest_skill=weakest_skill,
        low_energy=False,
        target=target_data,
        study_skill=study_skill,
        recent_types=recent_activity_types(activity_state),
        templates=templates,
        source_state=source_state,
        now=now,
    )
    body_lines.extend([
        "## Active activity",
        "",
    ])
    active_activity = activity_state.get("active_activity") or {}
    if active_activity.get("id"):
        body_lines.append(f"- **Activity ID:** {active_activity.get('id')}")
        body_lines.append(f"- **Type:** {active_activity.get('type')}")
        body_lines.append(f"- **Status:** {active_activity.get('status')}")
        body_lines.append(f"- **Reason:** {active_activity.get('reason')}")
        body_lines.append(f"- **Expected evidence:** {', '.join(active_activity.get('expected_evidence') or [])}")
    else:
        body_lines.append("- No active activity assigned.")
    body_lines.append("")

    body_lines.extend([
        "## Next activity recommendation",
        "",
        f"- **Recommended activity:** {decision.activity_type}",
        f"- **Rule ID:** {decision.rule_id}",
        f"- **Reason:** {decision.reason}",
        f"- **Expected evidence:** {', '.join(decision.expected_evidence) if decision.expected_evidence else 'typed answer or transcript'}",
    ])
    if not target_path:
        body_lines.append("- **Scope:** generic template fallback; no learner target is active.")
    body_lines.append("- **Learner control:** You can accept, modify, or override this.")

    target_id = active_target_id(study_state)
    freshness_lines = build_next_activity_source_freshness_section(
        decision, target_data, target_id, source_state
    )
    body_lines.append("")
    body_lines.extend(freshness_lines)

    body_lines.extend([
        "",
        "## Recent activity effectiveness",
        "",
    ])
    recent = activity_state.get("recent_activities") or []
    if recent:
        for activity in recent[:5]:
            body_lines.append(
                f"- {activity.get('type')} ({activity.get('skill_id')}): {activity.get('result')}"
            )
    else:
        body_lines.append("- No recent activities recorded.")

    body_lines.extend([
        "",
        "## Learner activity preferences",
        "",
    ])
    prefs = activity_state.get("activity_preferences") or {}
    body_lines.append(f"- **Likes:** {', '.join(prefs.get('learner_likes') or ['(none)'])}")
    body_lines.append(f"- **Dislikes:** {', '.join(prefs.get('learner_dislikes') or ['(none)'])}")
    body_lines.append(f"- **Effective methods:** {', '.join(prefs.get('effective_methods') or ['(none)'])}")
    body_lines.append(f"- **Ineffective methods:** {', '.join(prefs.get('ineffective_methods') or ['(none)'])}")
    body_lines.append("")

    # Summary files.
    for rel in SUMMARY_FILES:
        path = ROOT / rel
        if path.is_file():
            included.append((rel, "derived summary or index"))
        else:
            skipped.append((rel, "derived summary missing"))

    # Relevant skills.
    relevant_filter = skill_id or active_skill or active_question
    relevant_ids = relevant_skill_ids(study_state, skill_map, review_state, skill_id or active_skill)
    body_lines.extend([
        "## Relevant skills for this task",
        "",
    ])
    if relevant_filter:
        body_lines.append(f"- **Filter:** {relevant_filter}")
    if relevant_ids:
        for skill in skill_map.get("skills") or []:
            if skill.get("id") in relevant_ids:
                body_lines.append(
                    f"- **{skill.get('id')}** ({skill.get('label') or 'no label'}): "
                    f"status {skill.get('status')}, readiness {skill.get('readiness')}, confidence {skill.get('confidence')}"
                )
    else:
        body_lines.append("- No specific skills selected for this task.")
    body_lines.append("")

    # Evidence excerpts for non-audit tasks.
    if task in ("audit",):
        included.append(("state/EVIDENCE_LOG.md", "full audit log required for audit task"))
        included.append(("sessions/SESSION_LOG.md", "full audit log required for audit task"))
        included.append(("reviews/REVIEW_OVERRIDES.md", "full audit log required for audit task"))
        metadata["raw_log_files_loaded"] = 3
    else:
        excerpts = relevant_evidence_excerpts(evidence_index, relevant_ids, active_question)
        body_lines.extend([
            "## Relevant evidence excerpts",
            "",
        ])
        if excerpts:
            for item in excerpts:
                body_lines.append(
                    f"- **{item.get('evidence_id') or 'unknown'}** "
                    f"({item.get('skill_id')}, {item.get('verdict')}, {item.get('date')}): "
                    f"see state/EVIDENCE_LOG.md"
                )
        else:
            body_lines.append("- No relevant evidence excerpts selected.")
        body_lines.append("")
        skipped.append(("state/EVIDENCE_LOG.md", "raw audit log; indexed evidence is enough"))
        skipped.append(("sessions/SESSION_LOG.md", "raw audit log; session summaries are enough"))
        skipped.append(("reviews/REVIEW_OVERRIDES.md", "raw audit log; not needed for this task"))

    # Relevant reviews for schedule_review and similar tasks.
    if task in ("schedule_review", "start_session", "close_session"):
        due_reviews = relevant_reviews(review_state, review_id, relevant_ids)
        body_lines.extend([
            "## Relevant reviews",
            "",
        ])
        if review_id:
            body_lines.append(f"- **Filter:** review_id={review_id}")
        if due_reviews:
            for item in due_reviews:
                body_lines.append(
                    f"- **{item.get('id')}** skill={item.get('skill_id')} due={item.get('due_at')} status={item.get('status')}"
                )
        else:
            body_lines.append("- No relevant reviews selected.")
        body_lines.append("")

    # Task-specific notes.
    body_lines.extend([
        "## Task-specific guidance",
        "",
    ])
    if task == "start_session":
        body_lines.append("Load the active target, due reviews, weak skills, last session summary, and current next action. Do not open full raw logs unless the validator reports a conflict.")
    elif task == "ask_question":
        body_lines.append(f"Include active target, weak skills, due reviews, and question bank metadata. Do not load unrelated target history or full evidence log. Active question: {active_question or 'not specified'}")
    elif task == "grade_answer":
        body_lines.append(f"Include active question, rubric, learner answer, and relevant skill evidence only. Skip unrelated skill history. Active question: {active_question or 'not specified'}")
    elif task == "schedule_review":
        body_lines.append(f"Include review state, confidence, grade, previous interval, and lapses for the relevant skill. Review: {review_id or 'not specified'}")
    elif task == "close_session":
        body_lines.append("Update compact state and summaries after writing logs. Run compact_state.py after appending evidence and session entries.")
    elif task == "upgrade_instance":
        body_lines.append("Load version/protocol files and generic template structure. Do not load learner logs.")
    elif task == "demo":
        body_lines.append("Load enough state to demonstrate the learning loop. Raw logs may be referenced for display but are not the default context.")
    elif task == "audit":
        body_lines.append("Open raw logs and scan indexes and references. Compare compact state against append-only audit trail. Report conflicts instead of guessing.")
    else:
        body_lines.append(f"No specific guidance for task '{task}'. Use the smallest context that contains the needed truth.")
    body_lines.append("")

    # Source freshness, learner adaptation, and question quality for the active target.
    if target_path:
        target_id = active_target_id(study_state)
        try:
            csf = import_check_source_freshness()
            freshness_lines, volatility = build_source_freshness_section(target_id, csf)
            body_lines.extend(freshness_lines)
        except Exception as exc:
            body_lines.extend([
                "## Source freshness status",
                "",
                f"- **Error:** could not build freshness section: {exc}",
                "",
            ])
            volatility = "moderate"
        body_lines.extend(build_learner_adaptation_section(evidence_index, review_state))
        body_lines.extend(build_question_quality_section(volatility))

    # File contents.
    body_lines.extend([
        "## Included file contents",
        "",
    ])

    def emit(rel_path: str, reason: str) -> None:
        path = ROOT / rel_path
        body_lines.append(f"### {rel_path}")
        body_lines.append(f"_Reason: {reason}_")
        body_lines.append("")
        body_lines.append(read_text(path))
        body_lines.append("")

    for rel, reason in included:
        emit(rel, reason)

    # Size estimate.
    total_size = sum(file_size(ROOT / rel) for rel, _ in included)
    rough_tokens = total_size // 4

    body_lines.extend([
        "## Pack summary",
        "",
        f"- **Files included:** {len(included)}",
        f"- **Files skipped:** {len(skipped)}",
        f"- **Approximate bytes loaded:** {total_size}",
        f"- **Rough token estimate:** {rough_tokens}",
        f"- **Cache used:** {metadata['cache_used']}",
        "",
        "### Included files",
        "",
    ])
    for rel, reason in included:
        body_lines.append(f"- `{rel}` — {reason}")
    body_lines.extend([
        "",
        "### Skipped files",
        "",
    ])
    for rel, reason in skipped:
        body_lines.append(f"- `{rel}` — {reason}")
    body_lines.append("")

    metadata["files_included"] = len(included)
    metadata["files_skipped"] = len(skipped)

    return "\n".join(body_lines), included, skipped, metadata


def check_budget(metadata: dict) -> list[str]:
    """Return budget warnings if limits are exceeded."""
    warnings: list[str] = []
    budgets = load_performance_budget()
    mode = metadata.get("mode", "fast_path")
    budget = budgets.get(mode) or {}

    max_files = budget.get("max_files_loaded")
    if max_files is not None and metadata.get("files_included", 0) > max_files:
        warnings.append(
            f"{mode} budget exceeded: {metadata['files_included']} files loaded, max {max_files}"
        )

    max_raw = budget.get("max_raw_log_files_loaded")
    if max_raw is not None and metadata.get("raw_log_files_loaded", 0) > max_raw:
        warnings.append(
            f"{mode} raw-log budget exceeded: {metadata['raw_log_files_loaded']} raw logs loaded, max {max_raw}"
        )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a task-specific StudyState context pack")
    parser.add_argument(
        "--task",
        required=True,
        choices=[
            "start_session",
            "ask_question",
            "grade_answer",
            "schedule_review",
            "close_session",
            "upgrade_instance",
            "demo",
            "audit",
        ],
        help="StudyState agent task",
    )
    parser.add_argument("--active-skill", help="Narrow context to this study skill ID")
    parser.add_argument("--active-question", help="Narrow context to this question ID")
    parser.add_argument("--review-id", help="Narrow context to this review ID")
    parser.add_argument("--skill-id", help="Alias for --active-skill")
    args = parser.parse_args()

    active_skill = args.active_skill or args.skill_id

    pack, included, skipped, metadata = build_context_pack(
        task=args.task,
        active_skill=active_skill,
        active_question=args.active_question,
        review_id=args.review_id,
    )

    CONTEXT_PACK_DIR.mkdir(parents=True, exist_ok=True)
    CONTEXT_PACK_PATH.write_text(pack, encoding="utf-8")

    print("StudyState context pack built.")
    print("")
    print(f"Task: {args.task}")
    print(f"Mode: {metadata['mode']}")
    print(f"Files included: {len(included)}")
    print(f"Files skipped: {len(skipped)}")
    print(f"Raw log files loaded: {metadata['raw_log_files_loaded']}")
    print(f"Cache used: {metadata['cache_used']}")
    budget_warnings = check_budget(metadata)
    for warning in budget_warnings:
        print(f"Budget warning: {warning}")
    print("")
    print("Included:")
    for rel, reason in included:
        print(f"- {rel}: {reason}")
    if skipped:
        print("")
        print("Skipped:")
        for rel, reason in skipped:
            print(f"- {rel}: {reason}")
    print("")
    print(f"Output: {CONTEXT_PACK_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
