"""Offline tests for the Mongo Brain scripts (no network, temporary files only)."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import espn_sync  # noqa: E402
import fp_weekly  # noqa: E402
import mongo_board  # noqa: E402
import record_decision  # noqa: E402
from ffdb.learning import LearningValidationError, materialize_decisions  # noqa: E402


def _stat(period, source, total):
    return {"scoringPeriodId": period, "statSourceId": source, "statSplitTypeId": 1, "appliedTotal": total}


def _pl(pid, name, pos, team, period, proj=None, actual=None, pct=None, inj="ACTIVE"):
    stats = []
    if proj is not None:
        stats.append(_stat(period, 1, proj))
    if actual is not None:
        stats.append(_stat(period, 0, actual))
    return {"id": pid, "fullName": name, "defaultPositionId": pos, "proTeamId": team, "injuryStatus": inj,
            "stats": stats, "ownership": {"percentOwned": pct} if pct is not None else {}}


def _entry(player, slot):
    return {"playerId": player["id"], "lineupSlotId": slot, "playerPoolEntry": {"player": player}}


def espn_raw(period=7):
    me = [
        _entry(_pl(1, "Kyler Murray", 1, 16, period, proj=17.0), 20),
        _entry(_pl(2, "Jameis Winston", 1, 19, period, proj=15.0), 0),
        _entry(_pl(3, "Bijan Robinson", 2, 1, period, proj=19.5), 2),
        _entry(_pl(4, "Jaleel McLaughlin", 2, 7, period, proj=7.0), 2),
        _entry(_pl(5, "Kendre Miller", 2, 18, period, proj=9.0), 20),
        _entry(_pl(6, "CeeDee Lamb", 3, 6, period, proj=18.0), 4),
        _entry(_pl(7, "Tetairoa McMillan", 3, 29, period, proj=13.0), 4),
        _entry(_pl(8, "Tyler Higbee", 4, 14, period, proj=6.0), 6),
        _entry(_pl(9, "Josh Downs", 3, 11, period, proj=10.0), 23),
        _entry(_pl(10, "Luther Burden III", 3, 3, period, proj=8.0), 23),
        _entry(_pl(11, "Saints D/ST", 16, 18, period, proj=5.0), 16),
        _entry(_pl(12, "Dylan Sampson", 2, 5, period, inj="INJURY_RESERVE"), 21),
    ]
    other = [_entry(_pl(50, "Brock Bowers", 4, 13, period, proj=14.0), 6)]
    league = {
        "seasonId": 2026, "scoringPeriodId": period, "status": {"currentMatchupPeriod": period},
        "settings": {"acquisitionSettings": {"acquisitionBudget": 100, "minimumBid": 0, "isUsingAcquisitionBudget": True}},
        "teams": [
            {"id": 2, "name": "Tom Brady of Ass", "abbrev": "JDD", "record": {"overall": {"wins": 3, "losses": 3, "ties": 0}},
             "transactionCounter": {"acquisitionBudgetSpent": 34}, "roster": {"entries": me}},
            {"id": 5, "name": "Rival", "abbrev": "RIV", "transactionCounter": {"acquisitionBudgetSpent": 10},
             "roster": {"entries": other}},
        ],
    }
    pool = {"players": [
        {"id": 60, "status": "FREEAGENT", "onTeamId": 0, "player": _pl(60, "Tucker Kraft", 4, 9, period, proj=11.5, pct=40.0)},
        {"id": 61, "status": "WAIVERS", "onTeamId": 0, "player": _pl(61, "Bucky Irving", 2, 27, period, proj=12.0, pct=55.0)},
        {"id": 50, "status": "FREEAGENT", "onTeamId": 0, "player": _pl(50, "Brock Bowers", 4, 13, period, proj=14.0)},
    ]}
    last = {"teams": [{"id": 2, "roster": {"entries": [
        _entry(_pl(3, "Bijan Robinson", 2, 1, period - 1, actual=24.3), 2),
        _entry(_pl(5, "Kendre Miller", 2, 18, period - 1, actual=15.1), 20),
        _entry(_pl(4, "Jaleel McLaughlin", 2, 7, period - 1, actual=3.2), 2),
    ]}}]}
    return {"league": league, "pool": pool, "last_week": last}


def test_espn_normalize_roster_faab_pool_and_last_week():
    snap = espn_sync.normalize(espn_raw(), "2026-10-21T15:00:00Z")
    me = snap["my_team"]
    assert me["faab_remaining"] == 66 and me["record"] == "3-3-0"
    slots = {r["name"]: r["slot"] for r in me["roster"]}
    assert slots["Kyler Murray"] == "BN" and slots["Josh Downs"] == "FLEX" and slots["Dylan Sampson"] == "IR"
    assert {r["nfl_team"] for r in me["roster"] if r["name"] == "Saints D/ST"} == {"NO"}
    names = {a["name"]: a["status"] for a in snap["available"]}
    # Bowers is listed in the pool but rostered by teamId 5: roster wins
    assert names == {"Tucker Kraft": "FREEAGENT", "Bucky Irving": "WAIVERS"}
    assert snap["last_week"]["week"] == 6 and snap["last_week"]["starter_points"] == 27.5


def test_espn_rejects_response_without_my_team():
    raw = espn_raw()
    raw["league"]["teams"] = raw["league"]["teams"][1:]
    with pytest.raises(espn_sync.EspnError):
        espn_sync.normalize(raw, "2026-10-21T15:00:00Z")


def test_espn_write_and_readback(tmp_path):
    snap = espn_sync.normalize(espn_raw(), "2026-10-21T15:00:00Z")
    dated = espn_sync.write(snap, tmp_path)
    assert dated.name == "2026-10-21T1500Z.json"
    assert json.loads((tmp_path / "latest.json").read_text()) == snap


def _repo_copy(tmp_path) -> Path:
    root = tmp_path / "repo"
    (root / "data").mkdir(parents=True)
    shutil.copytree(ROOT / "data" / "imports", root / "data" / "imports")
    wdir = fp_weekly.week_dir(7, root)
    wdir.mkdir(parents=True)
    fp = {"season": 2026, "week": 7, "pulled_at": "2026-10-21T13:10:00+00:00", "players": [
        {"name": "Tucker Kraft", "position": "TE", "nfl_team": "GB", "proj_ppr": 11.0, "ros_rank": 60, "waiver_rank": 3},
        {"name": "Bucky Irving", "position": "RB", "nfl_team": "TB", "proj_ppr": 12.5, "ros_rank": 40, "waiver_rank": 2},
        {"name": "Brock Bowers", "position": "TE", "nfl_team": "LV", "proj_ppr": 14.0, "ros_rank": 20},
        {"name": "Bijan Robinson", "position": "RB", "nfl_team": "ATL", "proj_ppr": 19.0, "ros_rank": 2},
        {"name": "Tyler Higbee", "position": "TE", "nfl_team": "LAR", "proj_ppr": 6.0, "ros_rank": 150},
        {"name": "Kaelon Black", "position": "RB", "nfl_team": "SF", "proj_ppr": 4.0, "ros_rank": 160},
    ]}
    (wdir / "players.json").write_text(json.dumps(fp))
    return root


def test_board_without_espn_marks_targets_unknown_and_uses_repo_roster(tmp_path):
    root = _repo_copy(tmp_path)
    b = mongo_board.build_board(7, root, now=datetime(2026, 10, 21, 15, tzinfo=timezone.utc))
    assert b["generated_from"]["roster_source"] == "REPOSITORY_HISTORY"
    assert b["faab"]["balance"] is not None
    roster = {p["name"] for p in b["roster"]}
    assert "Kyler Murray" in roster and "Mark Andrews" not in roster   # Oct 21 waiver result
    assert b["waiver_targets"] and all(t["availability"] == "UNKNOWN" for t in b["waiver_targets"])
    assert "Bijan Robinson" not in {t["name"] for t in b["waiver_targets"]}      # never recommend own player
    assert [s["slot"] for s in b["lineup"]["suggested"]] == mongo_board.STARTER_SLOTS
    assert any("No ESPN snapshot" in n for n in b["roster_notes"])
    assert "K" not in mongo_board.STARTER_SLOTS


def test_board_with_espn_uses_pool_and_skips_rostered(tmp_path):
    root = _repo_copy(tmp_path)
    # Snapshot must be newer than any repository import, whatever gets ingested later.
    espn_sync.write(espn_sync.normalize(espn_raw(), "2099-01-01T14:00:00Z"), root / "data" / "espn_api")
    b = mongo_board.build_board(7, root, now=datetime(2099, 1, 1, 15, tzinfo=timezone.utc))
    assert b["generated_from"]["roster_source"] == "ESPN_API"
    avail = {t["name"]: t["availability"] for t in b["waiver_targets"]}
    assert avail.get("Bucky Irving") == "ESPN_WAIVERS" and avail.get("Tucker Kraft") == "ESPN_FREE_AGENT"
    assert "Brock Bowers" not in avail
    lineup = {s["player"] for s in b["lineup"]["suggested"]}
    assert "Dylan Sampson" not in lineup and "Kyler Murray" in lineup     # IR out; best QB starts
    assert b["lineup"]["changes"] == {"start": ["Kendre Miller", "Kyler Murray"], "bench": ["Jaleel McLaughlin", "Jameis Winston"]}
    md = mongo_board.to_markdown(b)
    assert "Week 6 (ESPN league scoring)" in md and "Kendre Miller 15.1" in md


def _decision(**over):
    d = {"decision_id": "mongo-2026-w07-waiver-test-001", "week": 7, "decision_type": "WAIVER_BID",
         "subject": "Bucky Irving", "recommendation": "Claim Bucky Irving for $9, drop Kaelon Black",
         "confidence": 3, "urgency": "HIGH", "decision_deadline": "2026-10-28T03:00:00-04:00",
         "information_available_at_decision": {"board": "test"}, "key_supporting_signals": ["role"],
         "key_risk_factors": ["committee"], "alternative_considered": "pass"}
    d.update(over)
    return d


def test_record_decision_and_review_roundtrip(tmp_path):
    ledger, card = tmp_path / "ledger.jsonl", tmp_path / "card.json"
    ledger.write_text("")
    ev = record_decision.record_decision(_decision(), ledger, card)
    assert ev["system"] == "CLAUDE_MONGO_BRAIN" and ev["timestamp_et"][-6:] in ("-04:00", "-05:00")
    assert [d["decision_id"] for d in record_decision.open_decisions(7, ledger)] == [ev["decision_id"]]
    with pytest.raises(LearningValidationError):
        record_decision.record_decision(_decision(), ledger, card)          # immutable / no duplicates
    record_decision.record_review({
        "decision_id": ev["decision_id"], "actual_user_action": {"disposition": "followed", "detail": None},
        "final_pre_deadline_state": {}, "outcome": {"actual_acquisition": True}, "outcome_grade": "B",
        "process_grade": "A", "result_notes": "x", "error_category": [], "lesson": "y",
        "future_rule_adjustment": None}, ledger, card)
    assert record_decision.open_decisions(None, ledger) == []
    scorecard = json.loads(card.read_text())
    assert scorecard["system_performance"]["CLAUDE_MONGO_BRAIN"]["reviewed_count"] == 1
    assert len(ledger.read_text().splitlines()) == 2


def test_record_decision_rejects_bad_confidence(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("")
    with pytest.raises(LearningValidationError):
        record_decision.record_decision(_decision(confidence=9), ledger, None)
    assert ledger.read_text() == ""


def test_repository_ledger_still_materializes():
    assert len(materialize_decisions(ROOT / "learning" / "decision_ledger.jsonl")) >= 6
