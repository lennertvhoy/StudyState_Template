#!/usr/bin/env python3
"""Focused tests for shared StudyState next-activity decision rules."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from next_activity_decision import choose_activity_decision
from check_source_freshness import classify_source


TEMPLATES = [
    {
        "activity_type": "recent_info_check",
        "best_for": ["volatile_topic", "it_certification", "live_topic"],
        "expected_evidence": ["source_metadata", "short_summary", "answer_to_check_question"],
    },
    {
        "activity_type": "practical_lab",
        "best_for": ["sysadmin", "cloud", "networking"],
        "expected_evidence": ["screenshot", "command_output", "explanation"],
    },
    {
        "activity_type": "diagram_or_whiteboard",
        "best_for": ["philosophy", "conceptual_understanding"],
        "expected_evidence": ["whiteboard_diagram", "photo"],
    },
]

NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def decide(**overrides):
    base = {
        "skill_id": None,
        "due_reviews": 0,
        "weakest_skill": None,
        "low_energy": False,
        "target": {"id": "target", "type": "skill", "title": "Target", "volatility": "stable"},
        "study_skill": "generic",
        "recent_types": [],
        "templates": TEMPLATES,
        "source_state": None,
        "now": NOW,
    }
    base.update(overrides)
    return choose_activity_decision(**base)


def _source(
    checked_offset_days: int | None = None,
    target_id: str = "target",
    **kwargs,
) -> dict:
    """Build a source dict for the requested target."""
    source = {
        "id": kwargs.get("id", "src1"),
        "target_ids": [target_id],
        "authority": kwargs.get("authority", "official"),
        "usable_for_questions": kwargs.get("usable_for_questions", True),
    }
    if checked_offset_days is not None:
        checked = NOW - timedelta(days=checked_offset_days)
        source["last_checked_at"] = checked.isoformat()
    if "expires_at" in kwargs:
        source["expires_at"] = kwargs["expires_at"]
    if "freshness_window_days" in kwargs:
        source["freshness_window_days"] = kwargs["freshness_window_days"]
    if "volatility" in kwargs:
        source["volatility"] = kwargs["volatility"]
    return source


def _source_state(*sources) -> dict:
    return {"sources": list(sources)}


def test_due_review_beats_everything() -> None:
    decision = decide(
        due_reviews=2,
        low_energy=True,
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="practical_lab",
        weakest_skill={"id": "weak", "label": "Weak Skill", "status": "weak", "readiness": 10},
    )
    assert decision.activity_type == "spaced_review"
    assert decision.rule_id == "review_first_due"
    assert "Rule: review-first doctrine" in decision.reason


def test_due_review_beats_source_freshness() -> None:
    decision = decide(
        due_reviews=1,
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=30, target_id="cert")),
    )
    assert decision.activity_type == "spaced_review"
    assert decision.rule_id == "review_first_due"


def test_volatile_target_routes_to_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_unavailable_recent_activity_fallback"
    assert decision.reason.startswith("Rule:")
    assert "source freshness state unavailable" in decision.reason


def test_recent_info_check_prevents_immediate_repeat() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        recent_types=["recent_info_check"],
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.rule_id == "certification_exam_retrieval"
    assert "Rule: certification target" in decision.reason


def test_fresh_source_allows_retrieval_question_for_volatile_target() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        weakest_skill={"id": "exam", "label": "Exam Skill", "status": "pending", "readiness": 45},
        source_state=_source_state(_source(checked_offset_days=1, target_id="cert")),
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.rule_id == "certification_exam_retrieval"


def test_stale_source_triggers_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=10, target_id="cert")),
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_stale"
    assert decision.reason.startswith("Rule:")
    assert "source freshness stale" in decision.reason


def test_missing_source_state_triggers_recent_info_check_when_no_recent_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=None,
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_unavailable_recent_activity_fallback"


def test_missing_source_state_obeys_recent_activity_fallback() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        weakest_skill={"id": "exam", "label": "Exam Skill", "status": "pending", "readiness": 45},
        recent_types=["recent_info_check"],
        source_state=None,
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.signals.get("source_freshness_recent_activity_fallback") is True


def test_malformed_timestamp_triggers_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state({
            "id": "src1",
            "target_ids": ["cert"],
            "authority": "official",
            "last_checked_at": "not-a-timestamp",
            "usable_for_questions": True,
        }),
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_missing"
    assert decision.reason.startswith("Rule:")


def test_unverified_source_triggers_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=1, target_id="cert", usable_for_questions=False)),
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_unverified"
    assert decision.reason.startswith("Rule:")


def test_moderate_target_missing_source_triggers_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Moderate Cert", "volatility": "moderate"},
        study_skill="it_certification",
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_unavailable_recent_activity_fallback"


def test_live_target_stale_source_triggers_recent_info_check() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Live Cert", "volatility": "live"},
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=2, target_id="cert")),
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_stale"


def test_stable_target_ignores_missing_source_state() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Stable Cert", "volatility": "stable"},
        study_skill="it_certification",
        weakest_skill={"id": "exam", "label": "Exam Skill", "status": "pending", "readiness": 45},
        source_state=None,
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.signals.get("source_freshness_checked") is False


def test_stable_explicit_requirement_triggers_recent_info_check() -> None:
    decision = decide(
        target={
            "id": "cert",
            "type": "certification",
            "title": "Stable Cert",
            "volatility": "stable",
            "requires_recent_info_check": True,
        },
        study_skill="it_certification",
        source_state=None,
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_unavailable_recent_activity_fallback"


def test_stable_with_requires_recent_info_and_stale_source_triggers_recent_info_check() -> None:
    decision = decide(
        target={
            "id": "cert",
            "type": "certification",
            "title": "Stable Cert",
            "volatility": "stable",
            "requires_recent_info_check": True,
        },
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=35, target_id="cert")),
    )
    assert decision.activity_type == "recent_info_check"
    assert decision.rule_id == "source_freshness_stale"
    assert "source freshness stale" in decision.reason


def test_empty_source_state_recent_activity_fallback() -> None:
    """An empty (rather than None) source_state still counts as unavailable."""
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state={"sources": []},
        weakest_skill={"id": "exam", "label": "Exam Skill", "status": "pending", "readiness": 45},
        recent_types=["recent_info_check"],
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.signals.get("source_freshness_recent_activity_fallback") is True


def test_freshness_window_days_override_shortens_window() -> None:
    source = {
        "id": "src1",
        "target_ids": ["target"],
        "authority": "official",
        "last_checked_at": (NOW - timedelta(days=5)).isoformat(),
        "usable_for_questions": True,
        "freshness_window_days": 3,
        "volatility": "volatile",
    }
    status, reason = classify_source(source, NOW, "volatile")
    assert status == "stale"
    assert reason is not None


def test_source_freshness_signals_populated() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state(
            _source(checked_offset_days=1, target_id="cert"),
            _source(checked_offset_days=10, target_id="cert", id="src2"),
        ),
    )
    assert decision.signals.get("source_freshness_checked") is True
    assert decision.signals.get("source_freshness_status") == "fresh"
    assert decision.signals.get("source_freshness_fresh_count") == 1
    assert decision.signals.get("source_freshness_stale_count") == 1
    assert decision.signals.get("source_freshness_best_authority") == "official"


def test_reason_starts_with_rule() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Volatile Cert", "volatility": "volatile"},
        study_skill="it_certification",
        source_state=_source_state(_source(checked_offset_days=10, target_id="cert")),
    )
    assert decision.reason.startswith("Rule:")


def test_template_mode_no_target_skips_source_freshness() -> None:
    decision = decide(target=None)
    assert decision.activity_type == "retrieval_question"
    assert decision.signals.get("source_freshness_checked") is False


def test_practical_skill_routes_to_practical_lab() -> None:
    decision = decide(study_skill="cloud")
    assert decision.activity_type == "practical_lab"
    assert decision.rule_id == "hands_on_skill_practical_lab"
    assert "hands-on" in decision.reason


def test_conceptual_skill_routes_to_diagram() -> None:
    decision = decide(study_skill="philosophy")
    assert decision.activity_type == "diagram_or_whiteboard"
    assert decision.rule_id == "conceptual_skill_diagram"
    assert "visual explanation" in decision.reason


def test_certification_practiced_routes_to_retrieval_question() -> None:
    decision = decide(
        target={"id": "cert", "type": "certification", "title": "Exam Target", "volatility": "stable"},
        study_skill="it_certification",
        weakest_skill={"id": "exam", "label": "Exam Skill", "status": "pending", "readiness": 45},
    )
    assert decision.activity_type == "retrieval_question"
    assert decision.rule_id == "certification_exam_retrieval"


def test_weak_skill_fallback_routes_to_paper_exercise() -> None:
    decision = decide(
        weakest_skill={"id": "weak", "label": "Weak Skill", "status": "weak", "readiness": 20}
    )
    assert decision.activity_type == "paper_exercise"
    assert decision.rule_id == "weak_skill_paper_exercise"
    assert "Rule: skill 'Weak Skill' is weak" in decision.reason


def test_blocked_skill_fallback_routes_to_explain_back() -> None:
    decision = decide(
        weakest_skill={"id": "blocked", "label": "Blocked Skill", "status": "blocked", "readiness": 10}
    )
    assert decision.activity_type == "explain_back"
    assert decision.rule_id == "blocked_skill_explain_back"
    assert "Rule: skill 'Blocked Skill' is blocked" in decision.reason


def test_low_energy_fallback_routes_to_explain_back() -> None:
    decision = decide(low_energy=True)
    assert decision.activity_type == "explain_back"
    assert decision.rule_id == "low_energy_explain_back"
    assert "Rule: low-energy mode" in decision.reason


def main() -> int:
    tests = [
        test_due_review_beats_everything,
        test_due_review_beats_source_freshness,
        test_volatile_target_routes_to_recent_info_check,
        test_recent_info_check_prevents_immediate_repeat,
        test_fresh_source_allows_retrieval_question_for_volatile_target,
        test_stale_source_triggers_recent_info_check,
        test_missing_source_state_triggers_recent_info_check_when_no_recent_check,
        test_missing_source_state_obeys_recent_activity_fallback,
        test_malformed_timestamp_triggers_recent_info_check,
        test_unverified_source_triggers_recent_info_check,
        test_moderate_target_missing_source_triggers_recent_info_check,
        test_live_target_stale_source_triggers_recent_info_check,
        test_stable_target_ignores_missing_source_state,
        test_stable_explicit_requirement_triggers_recent_info_check,
        test_stable_with_requires_recent_info_and_stale_source_triggers_recent_info_check,
        test_empty_source_state_recent_activity_fallback,
        test_freshness_window_days_override_shortens_window,
        test_source_freshness_signals_populated,
        test_reason_starts_with_rule,
        test_template_mode_no_target_skips_source_freshness,
        test_practical_skill_routes_to_practical_lab,
        test_conceptual_skill_routes_to_diagram,
        test_certification_practiced_routes_to_retrieval_question,
        test_weak_skill_fallback_routes_to_paper_exercise,
        test_blocked_skill_fallback_routes_to_explain_back,
        test_low_energy_fallback_routes_to_explain_back,
    ]
    for test in tests:
        print(f"Running {test.__name__}")
        test()
    print("Next activity decision tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
