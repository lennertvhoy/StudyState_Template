#!/usr/bin/env python3
"""Shared next-activity decision logic for StudyState.

The planner and context-pack builder both use this module so the activity type,
auditable rule reason, and expected evidence cannot drift between surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from check_source_freshness import (
    target_freshness_summary,
)

CERTIFICATION_READINESS_THRESHOLD = 40
RECENT_INFO_CHECK_EVIDENCE = ["source_metadata", "short_summary", "answer_to_check_question"]


@dataclass(frozen=True)
class ActivityDecision:
    activity_type: str
    reason: str
    expected_evidence: list[str]
    rule_id: str
    signals: dict[str, Any] = field(default_factory=dict)


def target_is_volatile(target: dict[str, Any]) -> bool:
    return target.get("volatility") in {"moderate", "volatile", "live"} or target.get("requires_recent_info_check") is True


def recent_activity_types(activity_state: dict[str, Any], limit: int = 5) -> list[str]:
    recent = activity_state.get("recent_activities") or []
    return [a.get("type") for a in recent[:limit] if a.get("type")]


def activity_types_for_study_skill(
    study_skill: str | None,
    templates: list[dict[str, Any]],
) -> list[str]:
    """Return activity types whose templates list this study skill in best_for."""
    if not study_skill:
        return []
    matched: set[str] = set()
    for template in templates:
        best_for = template.get("best_for") or []
        if study_skill in best_for:
            activity_type = template.get("activity_type")
            if activity_type:
                matched.add(activity_type)
    return sorted(matched)


def count_due_reviews(review_state: dict[str, Any]) -> int:
    now = datetime.now(timezone.utc)
    count = 0
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
                count += 1
        except Exception:
            continue
    return count


def find_weakest_skill(skill_map: dict[str, Any]) -> dict[str, Any] | None:
    skills = skill_map.get("skills") or []
    candidates = [
        s for s in skills
        if s.get("status") in ("weak", "blocked", "pending")
    ]
    if not candidates:
        return None
    # Prefer blocked/weak repair work, then lowest readiness.
    candidates.sort(
        key=lambda s: (
            0 if s.get("status") == "blocked" else (1 if s.get("status") == "weak" else 2),
            int(s.get("readiness") or 0),
        )
    )
    return candidates[0]


def get_template_evidence(activity_type: str, templates: list[dict[str, Any]]) -> list[str]:
    for template in templates:
        if template.get("activity_type") == activity_type:
            return template.get("expected_evidence") or []
    return []


def choose_activity_decision(
    skill_id: str | None,
    due_reviews: int,
    weakest_skill: dict[str, Any] | None,
    low_energy: bool,
    target: dict[str, Any] | None,
    study_skill: str | None,
    recent_types: list[str],
    templates: list[dict[str, Any]],
    source_state: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> ActivityDecision:
    """Choose one learning activity and return its auditable decision record."""
    if now is None:
        now = datetime.now(timezone.utc)
    target = target or {}
    target_type = target.get("type") or ""
    target_id = target.get("id")
    target_volatile = target_is_volatile(target)
    recent_set = set(recent_types)
    matched_types = activity_types_for_study_skill(study_skill, templates)
    declared_volatility = target.get("volatility") or "stable"
    # A stable target that explicitly requires recent-info checks should use a
    # sensible freshness window instead of treating every source as perpetually fresh.
    effective_volatility = declared_volatility
    if target.get("requires_recent_info_check") and declared_volatility == "stable":
        effective_volatility = "moderate"
    signals: dict[str, Any] = {
        "due_reviews": due_reviews,
        "weakest_skill_id": weakest_skill.get("id") if weakest_skill else "",
        "weakest_skill_status": weakest_skill.get("status") if weakest_skill else "",
        "low_energy": low_energy,
        "target_type": target_type,
        "target_volatility": effective_volatility,
        "study_skill": study_skill or "",
        "recent_activity_types": recent_types,
        "matched_activity_types": matched_types,
        "source_freshness_checked": False,
        "source_freshness_status": "",
        "source_freshness_fresh_count": 0,
        "source_freshness_stale_count": 0,
        "source_freshness_missing_count": 0,
        "source_freshness_unverified_count": 0,
        "source_freshness_unknown_count": 0,
        "source_freshness_best_authority": "",
        "source_freshness_has_fresh_usable": False,
        "source_freshness_rule_id": "",
        "source_freshness_target_volatility": effective_volatility,
        "recent_info_check_in_recent_types": "recent_info_check" in recent_types,
        "source_freshness_recent_activity_fallback": False,
    }

    decision: ActivityDecision

    # 1. Spaced repetition is the highest-priority learning debt.
    if due_reviews > 0:
        decision = ActivityDecision(
            activity_type="spaced_review",
            reason=f"Rule: review-first doctrine — {due_reviews} due review item{'s' if due_reviews != 1 else ''}.",
            expected_evidence=["typed_answer", "transcript", "screenshot"],
            rule_id="review_first_due",
            signals=signals,
        )
        return _with_template_evidence(decision, templates)

    # 2. Recent-info check for volatile topics before authoritative questions.
    if target_id and target_volatile:
        summary = target_freshness_summary(
            target_id,
            effective_volatility,
            source_state,
            now,
        )
        rule_id = "source_freshness_satisfied"
        if not summary.has_fresh_usable:
            if source_state is None or not source_state.get("sources"):
                rule_id = "source_freshness_unavailable_recent_activity_fallback"
            elif summary.status == "stale":
                rule_id = "source_freshness_stale"
            elif summary.status in ("missing", "unknown"):
                rule_id = "source_freshness_missing"
            elif summary.status == "unverified":
                rule_id = "source_freshness_unverified"

        signals.update({
            "source_freshness_checked": True,
            "source_freshness_status": summary.status,
            "source_freshness_fresh_count": summary.fresh_count,
            "source_freshness_stale_count": summary.stale_count,
            "source_freshness_missing_count": summary.missing_count,
            "source_freshness_unverified_count": summary.unverified_count,
            "source_freshness_unknown_count": summary.unknown_count,
            "source_freshness_best_authority": summary.best_authority or "",
            "source_freshness_has_fresh_usable": summary.has_fresh_usable,
            "source_freshness_rule_id": rule_id,
            "source_freshness_target_volatility": effective_volatility,
            "recent_info_check_in_recent_types": "recent_info_check" in recent_types,
            "source_freshness_recent_activity_fallback": source_state is None or not source_state.get("sources"),
        })

        if not summary.has_fresh_usable and "recent_info_check" not in recent_set:
            if source_state is None or not source_state.get("sources"):
                reason = f"Rule: source freshness state unavailable for volatile target '{target_id}' — falling back to recent activity; no recent_info_check found, so verify freshness before an authoritative question."
            elif summary.status == "stale":
                reason = f"Rule: source freshness stale for volatile target '{target_id}' — {summary.stale_count} source(s) stale ({summary.reason}); verify freshness before an authoritative question."
            elif summary.status in ("missing", "unknown"):
                reason = f"Rule: source freshness missing for volatile target '{target_id}' — {summary.reason}; verify freshness before an authoritative question."
            elif summary.status == "unverified":
                reason = f"Rule: source freshness unverified for volatile target '{target_id}' — registered sources are marked unusable for questions; verify freshness before an authoritative question."
            else:
                reason = f"Rule: source freshness not satisfied for volatile target '{target_id}' — verify freshness before an authoritative question."
            decision = ActivityDecision(
                activity_type="recent_info_check",
                reason=reason,
                expected_evidence=RECENT_INFO_CHECK_EVIDENCE,
                rule_id=rule_id,
                signals=signals,
            )
            return _with_template_evidence(decision, templates)

    # 3. Lab / practical exercise when the domain fits.
    if "practical_lab" in matched_types or study_skill in {"practical_lab", "sysadmin", "cloud", "networking"}:
        if "practical_lab" not in recent_set:
            decision = ActivityDecision(
                activity_type="practical_lab",
                reason=f"Rule: study skill '{study_skill}' is hands-on — a lab produces stronger evidence than a chat question.",
                expected_evidence=["screenshot", "command_output", "explanation"],
                rule_id="hands_on_skill_practical_lab",
                signals=signals,
            )
            return _with_template_evidence(decision, templates)

    # 4. Diagram / visual explanation for conceptual domains.
    if "diagram_or_whiteboard" in matched_types or study_skill in {"philosophy", "conceptual_understanding"}:
        if "diagram_or_whiteboard" not in recent_set:
            decision = ActivityDecision(
                activity_type="diagram_or_whiteboard",
                reason=f"Rule: study skill '{study_skill}' benefits from visual explanation — draw the model before defending it.",
                expected_evidence=["whiteboard_diagram", "photo"],
                rule_id="conceptual_skill_diagram",
                signals=signals,
            )
            return _with_template_evidence(decision, templates)

    # 5. Exam-style question for certification/exam targets with practiced+ skills.
    if target_type in {"certification", "exam"}:
        skill_ready = weakest_skill is None or int(weakest_skill.get("readiness") or 0) >= CERTIFICATION_READINESS_THRESHOLD
        if skill_ready and "retrieval_question" not in recent_set:
            decision = ActivityDecision(
                activity_type="retrieval_question",
                reason=f"Rule: certification target '{target.get('title') or target_type}' — use an exam-style question.",
                expected_evidence=["typed_answer"],
                rule_id="certification_exam_retrieval",
                signals=signals,
            )
            return _with_template_evidence(decision, templates)

    if weakest_skill is not None and weakest_skill.get("status") == "weak":
        decision = ActivityDecision(
            activity_type="paper_exercise",
            reason=f"Rule: skill '{weakest_skill.get('label') or weakest_skill.get('id')}' is weak — a written exercise surfaces hidden gaps.",
            expected_evidence=["photo", "typed_answers"],
            rule_id="weak_skill_paper_exercise",
            signals=signals,
        )
        return _with_template_evidence(decision, templates)

    if weakest_skill is not None and weakest_skill.get("status") == "blocked":
        decision = ActivityDecision(
            activity_type="explain_back",
            reason=f"Rule: skill '{weakest_skill.get('label') or weakest_skill.get('id')}' is blocked — explain it back to repair the confusion.",
            expected_evidence=["written_explanation", "transcript"],
            rule_id="blocked_skill_explain_back",
            signals=signals,
        )
        return _with_template_evidence(decision, templates)

    if low_energy:
        decision = ActivityDecision(
            activity_type="explain_back",
            reason="Rule: low-energy mode — short explain-back task keeps the session small.",
            expected_evidence=["written_explanation"],
            rule_id="low_energy_explain_back",
            signals=signals,
        )
        return _with_template_evidence(decision, templates)

    if skill_id:
        decision = ActivityDecision(
            activity_type="retrieval_question",
            reason=f"Rule: focusing on skill '{skill_id}' — one targeted question is the fastest next move.",
            expected_evidence=["typed_answer"],
            rule_id="focused_skill_retrieval",
            signals=signals,
        )
        return _with_template_evidence(decision, templates)

    decision = ActivityDecision(
        activity_type="retrieval_question",
        reason="Rule: no stronger signal — start with one focused question.",
        expected_evidence=["typed_answer"],
        rule_id="default_retrieval",
        signals=signals,
    )
    return _with_template_evidence(decision, templates)


def _with_template_evidence(
    decision: ActivityDecision,
    templates: list[dict[str, Any]],
) -> ActivityDecision:
    template_evidence = get_template_evidence(decision.activity_type, templates)
    if not template_evidence:
        return decision
    return ActivityDecision(
        activity_type=decision.activity_type,
        reason=decision.reason,
        expected_evidence=template_evidence,
        rule_id=decision.rule_id,
        signals=decision.signals,
    )
