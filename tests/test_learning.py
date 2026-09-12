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


def test_pending_decisions_count_toward_signal_usage_before_review(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    scorecard = build_scorecard(ledger)
    assert scorecard["pending_decisions"] == 1
    assert scorecard["confidence_calibration"]["4"]["count"] == 1
    assert scorecard["confidence_calibration"]["4"]["reviewed_count"] == 0
    assert scorecard["signal_performance"]["authenticated league state"]["count"] == 1
    assert scorecard["signal_performance"]["authenticated league state"]["false_positive_rate"] is None
    assert scorecard["signal_performance"]["authenticated league state"]["false_negative_rate"] is None


def test_ledger_is_valid_jsonl(tmp_path: Path):
    ledger = tmp_path / "ledger.jsonl"
    append_decision(ledger, decision())
    assert json.loads(ledger.read_text())["record_type"] == "DECISION"


def test_repository_scorecard_matches_empty_ledger_baseline():
    ledger = Path("learning/decision_ledger.jsonl")
    stored = json.loads(Path("learning/season_scorecard.json").read_text())
    stored.pop("generated_at", None)
    assert stored == build_scorecard(ledger)
