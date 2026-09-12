from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SYSTEM = "PRIME_MONGO_FANTASY_WATCH"
CONFIDENCE_LEVELS = {1, 2, 3, 4, 5}
URGENCY_LEVELS = {"LOW", "MEDIUM", "HIGH", "IMMEDIATE"}
GRADES = {"A", "B", "C", "D", "F"}
GRADE_POINTS = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
PULSE_USEFULNESS_GRADES = {
    "HIGHLY_USEFUL", "USEFUL", "ACCURATE_NOT_ACTIONABLE", "DUPLICATIVE",
    "TOO_LATE", "MISLEADING", "WRONG", "UNRESOLVED",
}
PULSE_FACT_CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
ERROR_CATEGORIES = {
    "STALE_DATA", "OWNERSHIP_ERROR", "ROSTER_STATE_ERROR", "INJURY_MISREAD",
    "DEPTH_CHART_MISREAD", "ROLE_PROJECTION_ERROR", "MATCHUP_OVERWEIGHTED",
    "MATCHUP_UNDERWEIGHTED", "VOLUME_PROJECTION_ERROR", "EFFICIENCY_PROJECTION_ERROR",
    "GAME_SCRIPT_ERROR", "WEATHER_ERROR", "NEWS_REACTION_TOO_SLOW",
    "NEWS_REACTION_TOO_AGGRESSIVE", "RECENCY_BIAS", "SMALL_SAMPLE_ERROR",
    "MARKET_PRICE_IGNORED", "LINE_MOVEMENT_IGNORED", "CORRELATION_ERROR",
    "CONTEST_SELECTION_ERROR", "FAAB_OVERPAY", "FAAB_UNDERBID", "DROP_ERROR",
    "START_SIT_ERROR", "PLAYER_EVALUATION_ERROR", "RISK_NOT_PRICED",
    "PROCESS_GOOD_VARIANCE_BAD", "OTHER",
}

DECISION_FIELDS = (
    "decision_id", "system", "timestamp_et", "week", "decision_type", "subject",
    "recommendation", "confidence", "urgency", "decision_deadline",
    "information_available_at_decision", "key_supporting_signals", "key_risk_factors",
    "alternative_considered", "actual_user_action", "final_pre_deadline_state", "outcome",
    "outcome_grade", "process_grade", "result_notes", "error_category", "lesson",
    "future_rule_adjustment", "reviewed_at",
    "pulse_used", "pulse_id", "pulse_information_event_id", "pulse_source",
    "pulse_detected_at_et", "pulse_category", "pulse_fact_confidence", "pulse_urgency",
    "pulse_relevance", "pulse_information_lead_time", "pulse_changed_decision",
    "pulse_confirmed_existing_thesis", "pulse_created_new_thesis",
    "pulse_conflicted_with_other_evidence", "pulse_usefulness_grade", "pulse_result_notes",
)

REVIEW_FIELDS = {
    "actual_user_action", "final_pre_deadline_state", "outcome", "outcome_grade",
    "process_grade", "result_notes", "error_category", "lesson",
    "future_rule_adjustment", "reviewed_at",
    "pulse_usefulness_grade", "pulse_result_notes",
}

PULSE_BOOLEAN_FIELDS = {
    "pulse_used", "pulse_changed_decision", "pulse_confirmed_existing_thesis",
    "pulse_created_new_thesis", "pulse_conflicted_with_other_evidence",
}


class LearningValidationError(ValueError):
    pass


def _parse_et(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise LearningValidationError(f"{field} must be an ISO-8601 timestamp") from exc
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() not in {-4 * 3600, -5 * 3600}:
        raise LearningValidationError(f"{field} must use an America/New_York UTC offset")
    return parsed


def validate_decision(record: dict[str, Any]) -> None:
    missing = [field for field in DECISION_FIELDS if field not in record]
    if missing:
        raise LearningValidationError("missing decision fields: " + ", ".join(missing))
    if record.get("record_type", "DECISION") != "DECISION":
        raise LearningValidationError("new recommendations must use record_type=DECISION")
    if record["system"] != SYSTEM:
        raise LearningValidationError("learning records in this repository must be Mongo-only")
    if not isinstance(record["decision_id"], str) or not record["decision_id"].strip():
        raise LearningValidationError("decision_id is required")
    if not isinstance(record["week"], int) or record["week"] < 1:
        raise LearningValidationError("week must be a positive integer")
    if record["confidence"] not in CONFIDENCE_LEVELS:
        raise LearningValidationError("confidence must be 1 through 5")
    if record["urgency"] not in URGENCY_LEVELS:
        raise LearningValidationError("invalid urgency")
    _parse_et(record["timestamp_et"], "timestamp_et")
    _parse_et(record["decision_deadline"], "decision_deadline")
    if not isinstance(record["key_supporting_signals"], list):
        raise LearningValidationError("key_supporting_signals must be a list")
    if not isinstance(record["key_risk_factors"], list):
        raise LearningValidationError("key_risk_factors must be a list")
    if record["outcome_grade"] is not None and record["outcome_grade"] not in GRADES:
        raise LearningValidationError("invalid outcome_grade")
    if record["process_grade"] is not None and record["process_grade"] not in GRADES:
        raise LearningValidationError("invalid process_grade")
    errors = record["error_category"]
    if errors is not None:
        if not isinstance(errors, list) or not set(errors).issubset(ERROR_CATEGORIES):
            raise LearningValidationError("invalid error_category")
    if any(not isinstance(record[field], bool) for field in PULSE_BOOLEAN_FIELDS):
        raise LearningValidationError("Pulse flags must be true or false booleans")
    pulse_detail_fields = {
        "pulse_information_event_id", "pulse_source", "pulse_detected_at_et",
        "pulse_category", "pulse_fact_confidence", "pulse_urgency", "pulse_relevance",
        "pulse_information_lead_time",
    }
    if record["pulse_id"] is not None:
        required = pulse_detail_fields - {"pulse_source"}
        missing = sorted(field for field in required if record[field] in {None, ""})
        if missing:
            raise LearningValidationError("Pulse lineage missing: " + ", ".join(missing))
        _parse_et(record["pulse_detected_at_et"], "pulse_detected_at_et")
    elif (
        record["pulse_used"]
        or any(record[field] for field in PULSE_BOOLEAN_FIELDS - {"pulse_used"})
        or any(record[field] is not None for field in pulse_detail_fields)
    ):
        raise LearningValidationError("Pulse lineage requires pulse_id")
    if record["pulse_used"] and not record["pulse_id"]:
        raise LearningValidationError("pulse_used requires pulse_id")
    fact_confidence = record["pulse_fact_confidence"]
    if (
        fact_confidence is not None
        and fact_confidence not in CONFIDENCE_LEVELS
        and fact_confidence not in PULSE_FACT_CONFIDENCE_LEVELS
    ):
        raise LearningValidationError("pulse_fact_confidence must be LOW, MEDIUM, HIGH, or 1 through 5")
    if record["pulse_urgency"] is not None and record["pulse_urgency"] not in URGENCY_LEVELS:
        raise LearningValidationError("invalid pulse_urgency")
    lead_time = record["pulse_information_lead_time"]
    if lead_time is not None and (
        not isinstance(lead_time, (int, float)) or isinstance(lead_time, bool) or lead_time < 0
    ):
        raise LearningValidationError("pulse_information_lead_time must be nonnegative numeric minutes")
    grade = record["pulse_usefulness_grade"]
    if grade is not None and grade not in PULSE_USEFULNESS_GRADES:
        raise LearningValidationError("invalid pulse_usefulness_grade")


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise LearningValidationError(f"invalid JSONL at line {number}") from exc
    return events


def append_decision(path: Path, record: dict[str, Any]) -> None:
    record = {"record_type": "DECISION", **record}
    validate_decision(record)
    if any(event.get("decision_id") == record["decision_id"] for event in read_events(path)):
        raise LearningValidationError(f"duplicate decision_id: {record['decision_id']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def append_review(path: Path, decision_id: str, review: dict[str, Any]) -> None:
    if set(review) != REVIEW_FIELDS:
        missing = REVIEW_FIELDS - set(review)
        extra = set(review) - REVIEW_FIELDS
        raise LearningValidationError(f"review fields mismatch; missing={sorted(missing)} extra={sorted(extra)}")
    decisions = materialize_decisions(path)
    if decision_id not in decisions:
        raise LearningValidationError(f"unknown decision_id: {decision_id}")
    if review["outcome_grade"] not in GRADES or review["process_grade"] not in GRADES:
        raise LearningValidationError("review requires valid outcome and process grades")
    if not isinstance(review["error_category"], list) or not set(review["error_category"]).issubset(ERROR_CATEGORIES):
        raise LearningValidationError("invalid error_category")
    pulse_considered = decisions[decision_id].get("pulse_id") is not None
    if pulse_considered and review["pulse_usefulness_grade"] not in PULSE_USEFULNESS_GRADES:
        raise LearningValidationError("Pulse-considered review requires pulse_usefulness_grade")
    if not pulse_considered and (
        review["pulse_usefulness_grade"] is not None or review["pulse_result_notes"] is not None
    ):
        raise LearningValidationError("non-Pulse review must not grade Pulse")
    _parse_et(review["reviewed_at"], "reviewed_at")
    event = {"record_type": "REVIEW", "decision_id": decision_id, **review}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def materialize_decisions(path: Path) -> dict[str, dict[str, Any]]:
    materialized: dict[str, dict[str, Any]] = {}
    for event in read_events(path):
        kind, decision_id = event.get("record_type"), event.get("decision_id")
        if kind == "DECISION":
            validate_decision(event)
            if decision_id in materialized:
                raise LearningValidationError(f"duplicate decision_id: {decision_id}")
            materialized[decision_id] = dict(event)
        elif kind == "REVIEW":
            if decision_id not in materialized:
                raise LearningValidationError(f"review precedes decision: {decision_id}")
            materialized[decision_id].update({key: event[key] for key in REVIEW_FIELDS})
        else:
            raise LearningValidationError(f"unknown record_type: {kind}")
    return materialized


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def build_scorecard(path: Path, season: int = 2026) -> dict[str, Any]:
    rows = list(materialize_decisions(path).values())
    reviewed = [row for row in rows if row.get("reviewed_at")]
    outcomes = Counter(row["outcome_grade"] for row in reviewed)
    processes = Counter(row["process_grade"] for row in reviewed)
    confidence: dict[str, Any] = {}
    decision_types: dict[str, Any] = {}
    signals: dict[str, Any] = {}

    for level in range(1, 6):
        bucket = [row for row in rows if row["confidence"] == level]
        confidence[str(level)] = _decision_bucket(bucket)
    for kind in sorted({row["decision_type"] for row in rows}):
        decision_types[kind] = _decision_bucket([row for row in rows if row["decision_type"] == kind])
    signal_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for signal in set(row["key_supporting_signals"]):
            signal_rows[signal].append(row)
    for signal, bucket in sorted(signal_rows.items()):
        reviewed_bucket = [row for row in bucket if row.get("reviewed_at")]
        metrics = _decision_bucket(bucket)
        metrics["false_positive_rate"] = (
            round(sum(row["outcome_grade"] in {"D", "F"} for row in reviewed_bucket) / len(reviewed_bucket), 3)
            if reviewed_bucket else None
        )
        metrics["false_negative_rate"] = None
        metrics["false_negative_note"] = "Derived from explicit missed-opportunity entries in weekly reviews after outcomes are known."
        signals[signal] = metrics

    action_groups = {"followed": [], "ignored": [], "overrode": []}
    for row in reviewed:
        action = row.get("actual_user_action") or {}
        disposition = action.get("disposition") if isinstance(action, dict) else None
        if disposition in action_groups:
            action_groups[disposition].append(row)

    errors = Counter(error for row in reviewed for error in row.get("error_category", []))
    return {
        "schema_version": 1,
        "system": SYSTEM,
        "season": season,
        "total_decisions": len(rows),
        "reviewed_decisions": len(reviewed),
        "pending_decisions": len(rows) - len(reviewed),
        "wins": outcomes["A"] + outcomes["B"],
        "losses": outcomes["D"] + outcomes["F"],
        "neutral": outcomes["C"],
        "outcome_grade_distribution": dict(sorted(outcomes.items())),
        "process_grade_distribution": dict(sorted(processes.items())),
        "confidence_calibration": confidence,
        "decision_type_performance": decision_types,
        "signal_performance": signals,
        "major_error_counts": dict(errors.most_common()),
        "timing_failures": errors["NEWS_REACTION_TOO_SLOW"],
        "data_quality_failures": errors["STALE_DATA"] + errors["OWNERSHIP_ERROR"] + errors["ROSTER_STATE_ERROR"],
        "user_action_performance": {key: _decision_bucket(value) for key, value in action_groups.items()},
        "mongo_outcome_metrics": _mongo_outcome_metrics(reviewed),
        "nfl_pulse_performance": _pulse_performance(rows),
    }


def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "success_rate": round(sum(row["outcome_grade"] in {"A", "B"} for row in rows) / len(rows), 3) if rows else None,
        "average_outcome_grade": _average([GRADE_POINTS[row["outcome_grade"]] for row in rows]),
        "average_process_grade": _average([GRADE_POINTS[row["process_grade"]] for row in rows]),
    }


def _decision_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = [row for row in rows if row.get("reviewed_at")]
    metrics = _bucket(reviewed)
    metrics["count"] = len(rows)
    metrics["reviewed_count"] = len(reviewed)
    return metrics


def _mongo_outcome_metrics(reviewed: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_fields = (
        "recommended_faab", "actual_faab_cost", "winning_faab", "next_highest_bid",
        "faab_saved_or_overspent", "points_added_above_replacement",
        "starter_bench_differential", "weeks_retained", "roster_value_improvement",
    )
    values: dict[str, list[float]] = {field: [] for field in numeric_fields}
    actual_acquisitions = 0
    for row in reviewed:
        outcome = row.get("outcome")
        if not isinstance(outcome, dict):
            continue
        if outcome.get("actual_acquisition"):
            actual_acquisitions += 1
        for field in numeric_fields:
            value = outcome.get(field)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[field].append(float(value))
    return {
        "reviewed_decisions": len(reviewed),
        "actual_acquisitions": actual_acquisitions,
        "tracked_value_count": {field: len(items) for field, items in values.items()},
        "averages": {
            field: round(sum(items) / len(items), 3) if items else None
            for field, items in values.items()
        },
    }


def _pulse_performance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    considered = [row for row in rows if row.get("pulse_id")]
    used = [row for row in considered if row["pulse_used"]]
    changed = [row for row in used if row["pulse_changed_decision"]]
    reviewed_changed = [row for row in changed if row.get("reviewed_at")]
    reviewed_pulse = [row for row in considered if row.get("reviewed_at")]

    # The event ID represents the underlying NFL fact, so repeated reports and Pulse IDs
    # for the same fact count once in considered/used/rejected information-event totals.
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in considered:
        events[row["pulse_information_event_id"]].append(row)
    used_events = {event_id for event_id, bucket in events.items() if any(row["pulse_used"] for row in bucket)}
    rejected_events = set(events) - used_events

    usefulness = Counter(
        row["pulse_usefulness_grade"] for row in reviewed_pulse if row.get("pulse_usefulness_grade")
    )
    lead_times = [
        float(row["pulse_information_lead_time"])
        for row in used
        if isinstance(row.get("pulse_information_lead_time"), (int, float))
        and not isinstance(row.get("pulse_information_lead_time"), bool)
    ]
    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in considered:
        category_rows[row.get("pulse_category") or "UNSPECIFIED"].append(row)
        source_rows[row.get("pulse_source") or "UNSPECIFIED"].append(row)

    return {
        "pulses_considered": len(events),
        "pulses_used": len(used_events),
        "pulses_rejected": len(rejected_events),
        "decision_lineages_considered": len(considered),
        "decision_lineages_used": len(used),
        "actions_changed_by_pulse": len(changed),
        "successful_actions_changed_by_pulse": sum(row["outcome_grade"] in {"A", "B"} for row in reviewed_changed),
        "unsuccessful_actions_changed_by_pulse": sum(row["outcome_grade"] in {"D", "F"} for row in reviewed_changed),
        "average_information_lead_time_minutes": round(sum(lead_times) / len(lead_times), 3) if lead_times else None,
        "highly_useful_pulses": usefulness["HIGHLY_USEFUL"],
        "misleading_pulses": usefulness["MISLEADING"] + usefulness["WRONG"],
        "too_late_pulses": usefulness["TOO_LATE"],
        "usefulness_grade_distribution": dict(sorted(usefulness.items())),
        "pulse_category_performance": {
            key: _pulse_bucket(bucket) for key, bucket in sorted(category_rows.items())
        },
        "pulse_source_performance": {
            key: _pulse_bucket(bucket) for key, bucket in sorted(source_rows.items())
        },
    }


def _pulse_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviewed = [row for row in rows if row.get("reviewed_at")]
    grades = Counter(row.get("pulse_usefulness_grade") for row in reviewed if row.get("pulse_usefulness_grade"))
    return {
        **_decision_bucket(rows),
        "used_count": sum(row["pulse_used"] for row in rows),
        "changed_decision_count": sum(row["pulse_changed_decision"] for row in rows),
        "usefulness_grade_distribution": dict(sorted(grades.items())),
    }
