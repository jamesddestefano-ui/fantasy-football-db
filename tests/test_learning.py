import json
from pathlib import Path

import pytest

from ffdb.learning import (LearningValidationError, append_decision, append_review,
    build_scorecard, materialize_decisions)


def decision(decision_id="mongo-w1-001"):
    return {
        "decision_id": decision_id,
        "system": "PRIME_MONGO_FANTASY_WATCH",
        "timestamp_et": "2026-09-12T00:10:00-04:00",
        "week": 1,
        "decision_type": "ADD",
        "subject": "Player X",
        "recommendation": "Add Player X if authenticated ESPN confirms availability.",
        "confidence": 4,
        "urgency": "HIGH",
        "decision_deadline": "2026-09-13T12:55:00-04:00",
        "information_available_at_decision": {"repository_head": "abc", "espn_state": "AVAILABLE"},
        "key_supporting_signals": ["authenticated league state", "depth-chart promotion"],
        "key_risk_factors": ["small sample"],
        "alternative_considered": "Hold current roster",
        "actual_user_action": None,
        "final_pre_deadline_state": None,
        "outcome": None,
        "outcome_grade": None,
        "process_grade": None,
        "result_notes": None,
        "error_category": None,
        "lesson": None,
        "future_rule_adjustment": None,
        "reviewed_at": None,
        "pulse_used": False,
        "pulse_id": None,
        "pulse_information_event_id": None,
        "pulse_source": None,
        "pulse_detected_at_et": None,
        "pulse_category": None,
        "pulse_fact_confidence": None,
        "pulse_urgency": None,
        "pulse_relevance": None,
        "pulse_information_lead_time": None,
        "pulse_changed_decision": False,
        "pulse_confirmed_existing_thesis": False,
        "pulse_created_new_thesis": False,
        "pulse_conflicted_with_other_evidence": False,
        "pulse_usefulness_grade": None,
        "pulse_result_notes": None,
    }


def review():
    return {
        "actual_user_action": {"disposition": "followed", "detail": "Added for $0"},
        "final_pre_deadline_state": {"availability": "AVAILABLE"},
        "outcome": {"points_added_above_replacement": 8.2, "weeks_retained": 2},
        "outcome_grade": "A",
        "process_grade": "B",
        "result_notes": "Role materialized.",
        "error_category": [],
        "lesson": "Authenticated availability plus promotion was useful.",
        "future_rule_adjustment": None,
        "reviewed_at": "2026-09-22T09:00:00-04:00",
        "pulse_usefulness_grade": None,
        "pulse_result_notes": None,
    }


def test_append_is_event_sourced_and_preserves_original(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    original = ledger.read_text().splitlines()[0]
    append_review(ledger, "mongo-w1-001", review())
    assert ledger.read_text().splitlines()[0] == original
    assert len(ledger.read_text().splitlines()) == 2
    assert materialize_decisions(ledger)["mongo-w1-001"]["outcome_grade"] == "A"


def test_duplicate_decision_is_rejected(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    with pytest.raises(LearningValidationError, match="duplicate decision_id"):
        append_decision(ledger, decision())


def test_cross_system_record_is_rejected(tmp_path: Path):
    row = decision(); row["system"] = "PRIME_SPARTA_FANTASY_WATCH"
    with pytest.raises(LearningValidationError, match="Mongo-only"):
        append_decision(tmp_path / "ledger.jsonl", row)


def test_scorecard_tracks_confidence_signals_and_user_action(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    append_review(ledger, "mongo-w1-001", review())
    scorecard = build_scorecard(ledger)
    assert scorecard["wins"] == 1
    assert scorecard["confidence_calibration"]["4"]["success_rate"] == 1.0
    assert scorecard["signal_performance"]["depth-chart promotion"]["count"] == 1
    assert scorecard["user_action_performance"]["followed"]["count"] == 1


def test_ledger_is_valid_jsonl(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    assert json.loads(ledger.read_text())["record_type"] == "DECISION"


def test_pulse_lineage_and_usefulness_are_measurable_without_double_counting(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    first = decision("mongo-w1-pulse-001")
    first.update({
        "pulse_used": True,
        "pulse_id": "pulse-2026-09-12-001",
        "pulse_information_event_id": "nfl-fact-malik-davis-out-w1",
        "pulse_source": "official-injury-report",
        "pulse_detected_at_et": "2026-09-12T08:00:00-04:00",
        "pulse_category": "INJURY",
        "pulse_fact_confidence": 5,
        "pulse_urgency": "HIGH",
        "pulse_relevance": "Confirmed injury contingency.",
        "pulse_information_lead_time": 290,
        "pulse_changed_decision": True,
        "pulse_created_new_thesis": True,
    })
    second = decision("mongo-w1-pulse-002")
    second.update({
        "pulse_used": False,
        "pulse_id": "pulse-2026-09-12-002",
        "pulse_information_event_id": "nfl-fact-malik-davis-out-w1",
        "pulse_source": "repeat-national-report",
        "pulse_detected_at_et": "2026-09-12T08:20:00-04:00",
        "pulse_category": "INJURY",
        "pulse_fact_confidence": 4,
        "pulse_urgency": "MEDIUM",
        "pulse_relevance": "Duplicate of the same underlying fact.",
        "pulse_information_lead_time": 270,
    })
    append_decision(ledger, first)
    append_decision(ledger, second)
    graded = review()
    graded["pulse_usefulness_grade"] = "HIGHLY_USEFUL"
    graded["pulse_result_notes"] = "Arrived early and improved the contingency decision."
    append_review(ledger, first["decision_id"], graded)
    pulse = build_scorecard(ledger)["nfl_pulse_performance"]
    assert pulse["pulses_considered"] == 1
    assert pulse["pulses_used"] == 1
    assert pulse["pulses_rejected"] == 0
    assert pulse["decision_lineages_considered"] == 2
    assert pulse["actions_changed_by_pulse"] == 1
    assert pulse["highly_useful_pulses"] == 1


def test_pulse_influence_requires_traceable_information_event(tmp_path: Path):
    row = decision()
    row["pulse_used"] = True
    with pytest.raises(LearningValidationError, match="requires pulse_id"):
        append_decision(tmp_path / "ledger.jsonl", row)


def test_pulse_review_requires_usefulness_scale(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    row = decision()
    row.update({
        "pulse_used": True,
        "pulse_id": "pulse-1",
        "pulse_information_event_id": "fact-1",
        "pulse_detected_at_et": "2026-09-12T08:00:00-04:00",
        "pulse_category": "INJURY",
        "pulse_fact_confidence": "HIGH",
        "pulse_urgency": "HIGH",
        "pulse_relevance": "Changed the contingency recommendation.",
        "pulse_information_lead_time": 60,
    })
    append_decision(ledger, row)
    invalid = review()
    invalid["pulse_usefulness_grade"] = "A"
    with pytest.raises(LearningValidationError, match="requires pulse_usefulness_grade"):
        append_review(ledger, row["decision_id"], invalid)


def test_pulse_lineage_requires_complete_fields(tmp_path: Path):
    row = decision()
    row["pulse_id"] = "pulse-1"
    with pytest.raises(LearningValidationError, match="Pulse lineage missing"):
        append_decision(tmp_path / "ledger.jsonl", row)


def test_pulse_outcome_cannot_be_backfilled_into_decision(tmp_path: Path):
    row = decision()
    row["pulse_usefulness_grade"] = "USEFUL"
    with pytest.raises(LearningValidationError, match="until REVIEW"):
        append_decision(tmp_path / "ledger.jsonl", row)


def test_cross_system_pulse_cannot_override_mongo_system_guard(tmp_path: Path):
    row = decision(); row["system"] = "PRIME_NFL_DFS_WATCH"
    row.update({
        "pulse_used": True,
        "pulse_id": "pulse-1",
        "pulse_information_event_id": "shared-fact-1",
        "pulse_detected_at_et": "2026-09-12T08:00:00-04:00",
    })
    with pytest.raises(LearningValidationError, match="Mongo-only"):
        append_decision(tmp_path / "ledger.jsonl", row)


def test_repository_scorecard_matches_empty_ledger_baseline():
    ledger = Path("learning/decision_ledger.jsonl")
    stored = json.loads(Path("learning/season_scorecard.json").read_text())
    stored.pop("generated_at", None)
    assert stored == build_scorecard(ledger)
