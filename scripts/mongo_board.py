"""Mongo weekly board: James's lineup and waiver targets for the Mongo Brain.

Inputs (repository only):
  intelligence/fantasypros/weekly/<season>-wNN/players.json   (scripts/fp_weekly.py)
  data/espn_api/latest.json                                    (scripts/espn_sync.py, optional)
  Mongo repository state (src/ffdb seed history, rebuilt in a temporary database)

Outputs: intelligence/board/<season>-wNN.json, .md and latest.md

The board is intelligence for the Mongo Brain, not a recorded recommendation. Roster and
ownership come from the newer of (a) the ESPN snapshot and (b) repository history. A waiver
target is labelled:
  ESPN_FREE_AGENT / ESPN_WAIVERS  - listed in the ESPN pool at snapshot time (re-check before bidding)
  OWNED                          - on a Mongo roster (never shown as a target)
  UNKNOWN                        - no ESPN snapshot; AGENTS.md rule 3 forbids treating it as free
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))
import fp_weekly  # noqa: E402
from mongo_names import name_key  # noqa: E402

STARTER_SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "D/ST"]   # Mongo: no kicker
FLEX_OK = {"RB", "WR", "TE"}
POSITIONS = ["QB", "RB", "WR", "TE", "D/ST"]
OUT_STATUSES = {"O", "OUT", "IR", "INJURY_RESERVE", "IR-R", "PUP", "NA", "SUSP", "SUSPENSION", "D", "DOUBTFUL"}
ACTIVE_ROSTER_LIMIT = 16     # 9 starters + 7 bench; IR slot is extra
ESPN_STALE_HOURS = 30


def _pos(p: dict) -> str:
    pos = (p.get("position") or "").upper()
    return "D/ST" if pos in ("DST", "D/ST", "DEF") else pos


def _age_hours(iso: str | None, now: datetime) -> float | None:
    if not iso:
        return None
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return round((now - t).total_seconds() / 3600, 1)


def repo_state(root: Path = ROOT) -> dict:
    """James's roster and FAAB from repository history (seeded into a throwaway SQLite DB)."""
    from sqlalchemy.orm import Session
    from ffdb.db import make_engine
    from ffdb.models import Base
    from ffdb.seed import seed_mongo
    from ffdb.services import faab_balance, roster

    engine = make_engine(url="sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s, s.begin():
        seed_mongo(s)
        rows = [{"name": p.canonical_name, "position": _pos({"position": p.position}), "nfl_team": p.nfl_team,
                 "slot": None, "injury_status": None} for p, _ in roster(s, "mongo")]
        faab = faab_balance(s, "mongo")
    imports = sorted((root / "data" / "imports").glob("*.json"))
    observed = None
    for f in imports:
        o = json.loads(f.read_text()).get("observed_at")
        if o and (observed is None or o > observed):
            observed = o
    return {"source": "REPOSITORY_HISTORY", "observed_at": observed, "roster": rows,
            "faab": float(faab) if faab is not None else None}


def build_board(week: int, root: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fp = json.loads((fp_weekly.week_dir(week, root) / "players.json").read_text())
    by_key = {}
    for p in fp["players"]:
        k = name_key(p["name"], p.get("nfl_team"), _pos(p))
        if k:
            by_key[k] = p

    repo = repo_state(root)
    espn_path = root / "data" / "espn_api" / "latest.json"
    espn = json.loads(espn_path.read_text()) if espn_path.exists() else None
    use_espn = bool(espn) and (repo["observed_at"] is None or espn["observed_at"] >= repo["observed_at"])
    if use_espn:
        state = {"source": "ESPN_API", "observed_at": espn["observed_at"], "roster": espn["my_team"]["roster"],
                 "faab": espn["my_team"].get("faab_remaining")}
    else:
        state = repo
    espn_age = _age_hours(espn["observed_at"], now) if espn else None
    pool = {}
    if espn and espn_age is not None and espn_age <= ESPN_STALE_HOURS * 4:
        for a in espn.get("available", []):
            pool[name_key(a["name"], a.get("nfl_team"), a.get("position"))] = a
    owned_keys = set((espn or {}).get("owned_keys", {})) | {
        name_key(r["name"], r.get("nfl_team"), _pos(r)) for r in state["roster"]}

    # ---- James's players joined with FantasyPros (+ ESPN league-scored projection when present)
    mine = []
    for r in state["roster"]:
        pos = _pos(r) or "?"
        k = name_key(r["name"], r.get("nfl_team"), pos)
        f = by_key.get(k, {})
        status = (r.get("injury_status") or "").upper()
        if status == "ACTIVE":
            status = ""
        status = status or (f.get("injury_status") or "").upper()
        bye = str(f.get("bye_week") or "") == str(week)
        slot = r.get("slot")
        mine.append({
            "name": r["name"], "position": pos, "nfl_team": r.get("nfl_team"), "current_slot": slot,
            "status": status or None, "proj_espn": r.get("proj"), "proj_ppr": f.get("proj_ppr"),
            "ecr_rank": f.get("ecr_rank"), "ros_rank": f.get("ros_rank"), "opponent": f.get("opponent"),
            "matched_fantasypros": bool(f),
            "unavailable": status in OUT_STATUSES or bye or (slot or "") == "IR",
            "on_bye": bye,
        })

    def score(p):
        """Mongo-scored ESPN projection when available, else FantasyPros PPR, else a rank estimate."""
        for k in ("proj_espn", "proj_ppr"):
            if p.get(k) is not None:
                return p[k]
        if p.get("ecr_rank"):
            return max(0.0, 20.0 - p["ecr_rank"] / 8.0)
        return -1

    pool_sorted = sorted([p for p in mine if not p["unavailable"]], key=score, reverse=True)
    lineup, used = [], set()
    for slot in STARTER_SLOTS:
        allowed = FLEX_OK if slot == "FLEX" else {slot}
        pick = next((p for p in pool_sorted if p["name"] not in used and p["position"] in allowed), None)
        if pick:
            used.add(pick["name"])
        lineup.append({"slot": slot, "player": pick["name"] if pick else None,
                       "proj": round(score(pick), 2) if pick and score(pick) >= 0 else None,
                       "basis": ("espn" if pick and pick["proj_espn"] is not None else
                                 "fantasypros" if pick and pick["proj_ppr"] is not None else
                                 "ranking" if pick and pick["ecr_rank"] else "none")})
    known_slots = any(p["current_slot"] for p in mine)
    current = {p["name"] for p in mine if p["current_slot"] not in ("BN", "IR", None)}
    suggested = {s["player"] for s in lineup if s["player"]}
    by_name = {p["name"]: p for p in mine}
    changes = ({"start": sorted(suggested - current), "bench": sorted(current - suggested)}
               if known_slots else None)

    # ---- waiver targets
    starter_proj = {}
    for s in lineup:
        if s["player"]:
            pos = by_name[s["player"]]["position"]
            starter_proj[pos] = min(starter_proj.get(pos, 1e9), score(by_name[s["player"]]))
    active = [p for p in mine if (p["current_slot"] or "") != "IR"]
    weakest = {}
    for pos in POSITIONS:
        at = [p for p in active if p["position"] == pos]
        if at:
            weakest[pos] = min(at, key=lambda p: (p["ros_rank"] is None, -(p["ros_rank"] or 0), score(p)))
    candidates = {}
    for f in fp["players"]:
        candidates[name_key(f["name"], f.get("nfl_team"), _pos(f))] = dict(f, position=_pos(f))
    for k, a in pool.items():      # ESPN-pool players FantasyPros didn't list still count
        if k not in candidates:
            candidates[k] = {"name": a["name"], "position": a["position"], "nfl_team": a.get("nfl_team")}
    targets = []
    for k, f in candidates.items():
        pos = f["position"]
        if pos not in POSITIONS or k in owned_keys:
            continue
        a = pool.get(k)
        if espn and not a:
            continue          # ESPN pool shown and player not in it: rostered or not listed; skip
        proj = a.get("proj") if a and a.get("proj") is not None else f.get("proj_ppr")
        w = weakest.get(pos)
        ros_gain = (w["ros_rank"] - f["ros_rank"]) if (w and w.get("ros_rank") and f.get("ros_rank")) else None
        week_gain = (proj - starter_proj.get(pos, 0.0)) if proj is not None else None
        wr = f.get("waiver_rank")
        flex_list = (f.get("waiver_list") or "FLX") == "FLX"
        ros = f.get("ros_rank")
        # Beating James's worst bench body is not enough: a target must be a real asset
        # (top-150 ROS FLEX), help this week's lineup, or be on FantasyPros' waiver list.
        relevant_ros = bool(ros_gain and ros_gain > 0 and ros and ros <= 150)
        if not (relevant_ros or (week_gain and week_gain > 1.0) or (wr and wr <= 15)):
            continue
        if not flex_list and not (week_gain and week_gain > 0):
            tier = "STREAM"
        else:
            tier = ("HIGH" if (week_gain or 0) >= 6 or (flex_list and wr and wr <= 5)
                    or (ros and ros <= 60 and (ros_gain or 0) >= 40)
                    else "MEDIUM" if (week_gain or 0) >= 3 or (flex_list and wr and wr <= 12)
                    or (ros and ros <= 100 and (ros_gain or 0) >= 15)
                    else "LOW")
        availability = ({"FREEAGENT": "ESPN_FREE_AGENT"}.get(a["status"], f"ESPN_{a['status']}") if a else "UNKNOWN")
        targets.append({
            "name": f["name"], "position": pos, "nfl_team": f.get("nfl_team"), "proj": proj,
            "ros_rank": f.get("ros_rank"), "fp_waiver_rank": wr, "injury": f.get("injury_status") or (a or {}).get("injury_status"),
            "replaces": w["name"] if w else None, "ros_rank_gain": ros_gain,
            "week_proj_gain": round(week_gain, 2) if week_gain is not None else None, "priority": tier,
            "availability": availability,
            "espn_pct_owned": (a or {}).get("pct_owned", f.get("espn_rostered_pct")),
            "fp_waiver_note": f.get("waiver_note"),
        })
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "STREAM": 3}
    targets.sort(key=lambda t: (order[t["priority"]], t["fp_waiver_rank"] or 999, t["ros_rank"] or 9999, -(t["proj"] or 0)))

    notes = []
    roster_age = _age_hours(state["observed_at"], now)
    if roster_age is not None and roster_age > 72:
        notes.append(f"Roster data is {roster_age / 24:.1f} days old — get a fresh ESPN check before acting.")
    if not espn:
        notes.append("No ESPN snapshot: every waiver target is UNKNOWN availability (AGENTS.md rule 3). "
                     "Set ESPN_S2/ESPN_SWID secrets to make availability automatic.")
    elif espn_age is not None and espn_age > ESPN_STALE_HOURS:
        notes.append(f"ESPN snapshot is {espn_age:.0f}h old; re-check availability before bidding.")
    open_spots = max(0, ACTIVE_ROSTER_LIMIT - len(active))
    if open_spots:
        notes.append(f"{open_spots} open roster spot(s): a claim needs no drop.")
    ir_used = [p for p in mine if (p["current_slot"] or "") == "IR"]
    ir_eligible = [p for p in mine if (p["current_slot"] or "") != "IR" and (p["status"] or "") in ("IR", "INJURY_RESERVE", "PUP")]
    if ir_eligible and not ir_used and known_slots:
        notes.append("IR slot open; IR-eligible: " + ", ".join(p["name"] for p in ir_eligible) + ".")
    qbs = [p for p in mine if p["position"] == "QB" and not p["unavailable"]]
    if len(qbs) < 1:
        notes.append("No available QB this week — streaming QB is the priority.")
    return {
        "league": "mongo", "season": fp["season"], "week": week, "team": "Tom Brady of Ass (JDD)",
        "kind": "INTELLIGENCE_BOARD_NOT_A_RECORDED_RECOMMENDATION",
        "generated_from": {"fantasypros_pulled_at": fp.get("pulled_at"), "roster_source": state["source"],
                           "roster_observed_at": state["observed_at"],
                           "espn_observed_at": espn["observed_at"] if espn else None},
        "faab": {"balance": state["faab"]},
        "open_roster_spots": open_spots,
        "lineup": {"suggested": lineup, "changes": changes,
                   "proj_current_starters": round(sum(max(score(p), 0) for p in mine if p["name"] in current), 2) if known_slots else None,
                   "proj_suggested": round(sum(max(score(by_name[s["player"]]), 0) for s in lineup if s["player"]), 2)},
        "roster": sorted(mine, key=lambda p: (POSITIONS.index(p["position"]) if p["position"] in POSITIONS else 9, -score(p))),
        "waiver_targets": targets[:25],
        "unmatched_roster_players": [p["name"] for p in mine if not p["matched_fantasypros"]],
        "roster_notes": notes,
        "last_week": (espn or {}).get("last_week"),
        "matchup": (espn or {}).get("matchup"),
        "faab_market": _market_summary(root),
        "reconcile_status": _reconcile_status(root),
    }


def _market_summary(root: Path) -> dict | None:
    f = root / "intelligence" / "faab_market.json"
    if not f.exists():
        return None
    m = json.loads(f.read_text())
    return {"by_position": m.get("by_position"), "budgets": m.get("budgets", [])[:12],
            "median_overpay_vs_runner_up": m.get("median_overpay_vs_runner_up"), "observed_at": m.get("observed_at")}


def _reconcile_status(root: Path) -> dict | None:
    f = root / "intelligence" / "reconcile" / "latest.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text())
    return {"status": r.get("status"), "unlogged_moves": len(r.get("unlogged_moves") or []),
            "roster_diff": r.get("roster_diff")}


def _fmt(v, pct=False):
    if v is None:
        return "—"
    return f"{v:.0f}%" if pct else (f"{v:g}" if isinstance(v, (int, float)) else str(v))


def to_markdown(b: dict) -> str:
    g = b["generated_from"]
    L = [f"# Mongo Week {b['week']} board — {b['team']}", "",
         "_Intelligence for the Mongo Brain, not a recorded recommendation. Availability: "
         "ESPN_FREE_AGENT/ESPN_WAIVERS = in ESPN's pool at snapshot time; UNKNOWN = not verified._", "",
         f"FAAB: **${_fmt(b['faab']['balance'])}** · roster from {g['roster_source']} ({g['roster_observed_at']}) · "
         f"ESPN snapshot {g['espn_observed_at'] or 'none'} · FantasyPros {g['fantasypros_pulled_at']}",
         "", "## Lineup", "", "| Slot | Player | Proj | Basis |", "|---|---|---|---|"]
    for s in b["lineup"]["suggested"]:
        L.append(f"| {s['slot']} | {s['player'] or '—'} | {_fmt(s['proj'])} | {s['basis']} |")
    ch = b["lineup"]["changes"]
    if ch is None:
        L += ["", f"Suggested lineup projects **{b['lineup']['proj_suggested']}** (current ESPN slots unknown — compare on ESPN)."]
    else:
        L += ["", f"Projected: current **{b['lineup']['proj_current_starters']}** → suggested **{b['lineup']['proj_suggested']}**"]
        L.append(f"Changes: start {', '.join(ch['start']) or '—'}; bench {', '.join(ch['bench']) or '—'}"
                 if ch["start"] or ch["bench"] else "No lineup changes suggested.")
    L += ["", "## Waiver targets", "", "| Pri | Player | Pos | Proj | FP waiver # | ROS | ESPN % | Replaces | Availability |",
          "|---|---|---|---|---|---|---|---|---|"]
    for t in b["waiver_targets"]:
        L.append(f"| {t['priority']} | {t['name']} ({t['nfl_team'] or ''}) | {t['position']} | {_fmt(t['proj'])} | "
                 f"{_fmt(t['fp_waiver_rank'])} | {_fmt(t['ros_rank'])} | {_fmt(t['espn_pct_owned'], True)} | "
                 f"{t['replaces'] or '—'} | {t['availability']} |")
    if not b["waiver_targets"]:
        L.append("| — | No upgrades found | | | | | | | |")
    mu = b.get("matchup")
    if mu and mu.get("opponent"):
        edge = round((mu["my_proj"] or 0) - (mu["opponent_proj"] or 0), 1)
        L += ["", f"## Matchup — Week {mu['week']} vs {mu['opponent']} ({mu['opponent_record']})", "",
              f"ESPN projections (current slots): you **{mu['my_proj']}** vs **{mu['opponent_proj']}** "
              f"({'+' if edge >= 0 else ''}{edge}). "
              + ("Favored: prefer steady floors." if edge >= 8 else "Underdog: prefer upside where it's close." if edge <= -8
                 else "Close: start the best projection.")]
        L.append("Their starters: " + ", ".join(f"{p['name']} {_fmt(p['proj'])}" for p in mu.get("opponent_starters", [])))
    fm = b.get("faab_market")
    if fm and fm.get("by_position"):
        L += ["", "## FAAB market (league winning bids)", "",
              " · ".join(f"{pos} median {'$%g' % s['median'] if s['median'] is not None else '—'} / max "
                         f"{'$%g' % s['max'] if s['max'] is not None else '—'}" for pos, s in fm["by_position"].items())]
        rich = [f"{x['abbrev']} ${x['remaining']}" for x in fm["budgets"][:4]]
        if rich:
            L.append("Most FAAB left: " + ", ".join(rich))
    rs = b.get("reconcile_status")
    if rs and rs.get("status") != "IN_SYNC":
        L += ["", f"**Repository behind ESPN:** {rs['unlogged_moves']} unlogged move(s); roster diff {rs['roster_diff']}. "
                  "Use ESPN state for advice; Codex should ingest intelligence/reconcile/pending/."]
    lw = b.get("last_week")
    if lw:
        L += ["", f"## Week {lw['week']} (ESPN league scoring)", "",
              f"Starters scored **{lw['starter_points']}**."]
        bench = sorted([p for p in lw["players"] if p["slot"] == "BN" and p.get("actual") is not None],
                       key=lambda p: -p["actual"])[:3]
        if bench:
            L.append("Top bench: " + ", ".join(f"{p['name']} {p['actual']}" for p in bench))
    if b["roster_notes"]:
        L += ["", "## Notes", ""] + [f"- {n}" for n in b["roster_notes"]]
    if b["unmatched_roster_players"]:
        L += ["", f"Not matched to FantasyPros: {', '.join(b['unmatched_roster_players'])}"]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, default=None)
    args = ap.parse_args(argv)
    week = args.week or fp_weekly.current_week()
    b = build_board(week)
    out = ROOT / "intelligence" / "board"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{b['season']}-w{week:02d}.json").write_text(json.dumps(b, indent=1, ensure_ascii=False) + "\n")
    md = to_markdown(b)
    (out / f"{b['season']}-w{week:02d}.md").write_text(md)
    (out / "latest.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
