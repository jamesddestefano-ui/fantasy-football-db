"""Append Mongo Brain decisions and reviews to learning/decision_ledger.jsonl safely.

Used by Claude's Mongo Brain sessions (docs/brain_playbook.md). Wraps ffdb.learning so
every event passes the repository validator. Never edits existing lines (AGENTS.md
learning rule 2); after each append the season scorecard is rebuilt from the ledger.

  python scripts/record_decision.py decision path/to/decision.json
  python scripts/record_decision.py review   path/to/review.json
  python scripts/record_decision.py open [--week 7]   # DECISIONs with no REVIEW yet
  python scripts/record_decision.py scorecard         # rebuild learning/season_scorecard.json

decision.json needs: decision_id, week, decision_type, subject, recommendation,
confidence (1-5), urgency, decision_deadline (ET offset), information_available_at_decision,
key_supporting_signals, key_risk_factors, alternative_considered. Pulse lineage fields are
optional (defaults: not used). system and timestamp_et are set here.

review.json needs: decision_id, actual_user_action, final_pre_deadline_state, outcome,
outcome_grade, process_grade, result_notes, error_category (list), lesson,
future_rule_adjustment, and pulse_usefulness_grade/pulse_result_notes when Pulse was
considered. reviewed_at is set here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ffdb.learning import (BRAIN_SYSTEM, DECISION_FIELDS, REVIEW_FIELDS, LearningValidationError,  # noqa: E402
                           append_decision, append_review, build_scorecard, materialize_decisions)

ET = ZoneInfo("America/New_York")
LEDGER = ROOT / "learning" / "decision_ledger.jsonl"
SCORECARD = ROOT / "learning" / "season_scorecard.json"
_OUTCOME_FIELDS = {"actual_user_action", "final_pre_deadline_state", "outcome", "outcome_grade",
                   "process_grade", "result_notes", "error_category", "lesson",
                   "future_rule_adjustment", "reviewed_at", "pulse_usefulness_grade", "pulse_result_notes"}
_PULSE_FALSE = {"pulse_used", "pulse_changed_decision", "pulse_confirmed_existing_thesis",
                "pulse_created_new_thesis", "pulse_conflicted_with_other_evidence"}


def now_et() -> str:
    return datetime.now(timezone.utc).astimezone(ET).replace(microsecond=0).isoformat()


def write_scorecard(ledger: Path = LEDGER, out: Path = SCORECARD) -> dict:
    card = build_scorecard(ledger)
    out.write_text(json.dumps({"generated_at": now_et(), **card}, indent=2, sort_keys=False) + "\n")
    return card


def record_decision(d: dict, ledger: Path = LEDGER, scorecard: Path | None = SCORECARD) -> dict:
    record = {f: (False if f in _PULSE_FALSE else None) for f in DECISION_FIELDS}
    record.update({k: v for k, v in d.items() if k not in _OUTCOME_FIELDS})
    record["system"] = BRAIN_SYSTEM
    record["timestamp_et"] = now_et()
    append_decision(ledger, record)
    if scorecard:
        write_scorecard(ledger, scorecard)
    return record


def record_review(r: dict, ledger: Path = LEDGER, scorecard: Path | None = SCORECARD) -> dict:
    decision_id = r.get("decision_id")
    review = {f: r.get(f) for f in REVIEW_FIELDS}
    review["reviewed_at"] = now_et()
    append_review(ledger, decision_id, review)
    if scorecard:
        write_scorecard(ledger, scorecard)
    return {"decision_id": decision_id, **review}


def open_decisions(week: int | None = None, ledger: Path = LEDGER) -> list[dict]:
    return [d for d in materialize_decisions(ledger).values()
            if not d.get("reviewed_at") and (week is None or d.get("week") == week)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("decision", "review"):
        sub.add_parser(name).add_argument("json_file")
    sub.add_parser("open").add_argument("--week", type=int)
    sub.add_parser("scorecard")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "open":
            for d in open_decisions(args.week):
                print(f"W{d['week']} {d['decision_id']} [{d['decision_type']}] {d['system']} "
                      f"conf={d['confidence']}: {str(d['recommendation'])[:120]}")
            return 0
        if args.cmd == "scorecard":
            card = write_scorecard()
            print(f"SCORECARD decisions={card['total_decisions']} reviewed={card['reviewed_decisions']}")
            return 0
        payload = json.loads(Path(args.json_file).read_text())
        if args.cmd == "decision":
            ev = record_decision(payload)
            print(f"RECORDED DECISION {ev['decision_id']}")
        else:
            ev = record_review(payload)
            print(f"RECORDED REVIEW {ev['decision_id']}")
    except LearningValidationError as exc:
        print(f"REJECTED (ledger unchanged): {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
