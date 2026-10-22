"""Detect completed Mongo moves that the repository has not ingested yet.

Compares the ESPN snapshot (data/espn_api/latest.json) and transaction log
(data/espn_api/transactions.json) with repository history (data/imports/ + seed):

  * James's EXECUTED ESPN adds/drops/claims with no matching data/imports record
  * roster differences between ESPN and the repository

Outputs (intelligence only — nothing is ingested, AGENTS.md "Mongo Brain roles" 2, 5):
  intelligence/reconcile/latest.json and latest.md
  intelligence/reconcile/pending/<day>-<add>-<drop>.json   draft import records for Codex

A draft is ESPN-authoritative evidence of a completed transaction (rules 4, 12), but it is
written to the repository's history only by the ingest step (`src/ffdb/seed.py` +
`data/imports/`), which also debits FAAB and validates.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mongo_names import name_key  # noqa: E402

ET = ZoneInfo("America/New_York")
MY_TEAM_ID = 2
MY_TEAM = "Tom Brady of Ass"


def _k(name, team=None, pos=None):
    return name_key(name, team, pos) if name else None


def _et_day(iso: str | None):
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET).date()


def logged_moves(root: Path) -> list[dict]:
    out = []
    for f in sorted((root / "data" / "imports").glob("*.json")):
        d = json.loads(f.read_text())
        if d.get("league") not in (None, "mongo"):
            continue
        day = (d.get("dedupe_key") or {}).get("calendar_day_ET")
        day = datetime.fromisoformat(day).date() if day else _et_day(d.get("observed_at"))
        etype = d.get("event_type") or ""
        add = d.get("player") if "ADD" in etype else None
        drop = d.get("dropped_player") or (d.get("player") if etype == "DROP" else None)
        out.append({"file": f.name, "day": day, "add": _k(add, d.get("nfl_team"), d.get("position")),
                    "drop": _k(drop, d.get("dropped_nfl_team"), d.get("dropped_position")), "type": etype})
    return out


def _matches(tx: dict, logged: list[dict]) -> str | None:
    day = _et_day(tx["processed_at"])
    adds = {_k(a["name"], a["nfl_team"], a["position"]) for a in tx["adds"]} or {None}
    drops = {_k(d["name"], d["nfl_team"], d["position"]) for d in tx["drops"]} or {None}
    for m in logged:
        if day and m["day"] and abs((m["day"] - day).days) > 1:
            continue
        if m["add"] in adds and m["drop"] in drops:
            return m["file"]
        # a grouped ESPN move may have been logged as two single-sided records
        if (m["add"] and m["add"] in adds and None in drops) or (m["drop"] and m["drop"] in drops and None in adds):
            return m["file"]
    return None


def _slug(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "none").lower()).strip("-")


def draft_import(tx: dict) -> dict:
    add = tx["adds"][0] if tx["adds"] else None
    drop = tx["drops"][0] if tx["drops"] else None
    waiver = tx["type"] == "WAIVER"
    etype = ("WAIVER_" if waiver else "") + ("ADD_DROP" if add and drop else "ADD" if add else "DROP")
    if not waiver and add and not drop:
        etype = "FREE_AGENT_ADD"
    et = datetime.fromisoformat(tx["processed_at"].replace("Z", "+00:00")).astimezone(ET)
    when = et.strftime("%a %b %-d, %-I:%M %p ET")
    desc = "; ".join([*(f"added {a['name']}, {a['nfl_team']} {a['position']}" + (f" from Waivers for ${tx['bid']}" if waiver else "")
                        for a in tx["adds"]), *(f"dropped {d['name']}, {d['nfl_team']} {d['position']}" for d in tx["drops"])])
    return {
        "status": "DRAFT_PENDING_INGEST",
        "event_type": etype, "league": "mongo", "fantasy_team": MY_TEAM,
        "player": add["name"] if add else (drop["name"] if drop and etype == "DROP" else None),
        "nfl_team": add["nfl_team"] if add else None, "position": add["position"] if add else None,
        "espn_id": add["espn_id"] if add else None,
        "faab_amount": tx["bid"] if waiver else 0,
        "dropped_player": drop["name"] if drop and add else None,
        "dropped_nfl_team": drop["nfl_team"] if drop and add else None,
        "dropped_position": drop["position"] if drop and add else None,
        "observed_at": tx["processed_at"],
        "dedupe_key": {"league": "mongo", "team": MY_TEAM, "type": etype,
                       "added": add["name"] if add else None, "dropped": drop["name"] if drop else None,
                       "calendar_day_ET": et.date().isoformat(), "faab_amount": tx["bid"] if waiver else 0},
        "sources": [{"type": "ESPN_API_TRANSACTION",
                     "statement": f"ESPN transaction log (read-only API), transaction {tx['id']} {tx['type']} {tx['status']} "
                                  f"processed {when}: {desc}."}],
        "notes": ("Drafted automatically by scripts/espn_reconcile.py from the ESPN API transaction log. "
                  "Not applied. Ingest = add to src/ffdb/seed.py + data/imports/, debit FAAB, rebuild, validate."),
    }


def reconcile(root: Path = ROOT, season_start: str = "2026-09-01") -> dict:
    snap = json.loads((root / "data" / "espn_api" / "latest.json").read_text())
    txp = root / "data" / "espn_api" / "transactions.json"
    txs = json.loads(txp.read_text())["transactions"] if txp.exists() else []
    logged = logged_moves(root)
    unlogged = []
    for tx in txs:
        if tx["team_id"] != MY_TEAM_ID or tx["status"] != "EXECUTED" or not tx["processed_at"]:
            continue
        if tx["processed_at"] < season_start or tx["type"] == "TRADE_PROPOSAL":
            continue
        if any(not i["name"] for i in tx["adds"] + tx["drops"]):
            unlogged.append({"transaction": tx, "draft": None, "problem": "player name not resolved from ESPN"})
            continue
        if not _matches(tx, logged):
            unlogged.append({"transaction": tx, "draft": draft_import(tx)})

    sys.path.insert(0, str(root / "scripts"))
    import mongo_board  # noqa: E402  (repository roster from seed history)
    repo = mongo_board.repo_state(root)
    espn_keys = {_k(r["name"], r["nfl_team"], r["position"]): r["name"] for r in snap["my_team"]["roster"]}
    repo_keys = {_k(r["name"], r.get("nfl_team"), r["position"]): r["name"] for r in repo["roster"]}
    roster_diff = {"on_espn_not_in_repo": sorted(espn_keys[k] for k in set(espn_keys) - set(repo_keys)),
                   "in_repo_not_on_espn": sorted(repo_keys[k] for k in set(repo_keys) - set(espn_keys))}
    faab_espn = snap["my_team"].get("faab_remaining")
    status = "IN_SYNC" if not unlogged and not any(roster_diff.values()) and (
        faab_espn is None or repo["faab"] is None or float(faab_espn) == float(repo["faab"])) else "NEEDS_INGEST"
    return {"league": "mongo", "espn_observed_at": snap["observed_at"], "repo_observed_at": repo["observed_at"],
            "status": status, "unlogged_moves": unlogged, "roster_diff": roster_diff,
            "faab": {"espn": faab_espn, "repository": repo["faab"]},
            "transactions_checked": len(txs)}


def to_markdown(r: dict) -> str:
    L = [f"# Mongo reconciliation — {r['status']}", "",
         f"ESPN {r['espn_observed_at']} vs repository (newest import {r['repo_observed_at']}). "
         f"Transactions checked: {r['transactions_checked']}.", ""]
    if r["unlogged_moves"]:
        L += ["## Completed on ESPN, not in the repository", ""]
        for u in r["unlogged_moves"]:
            tx = u["transaction"]
            moves = ", ".join([*(f"+{a['name']}" for a in tx["adds"]), *(f"-{d['name']}" for d in tx["drops"])])
            L.append(f"- {tx['processed_at']} {tx['type']} {moves}" + (f" (${tx['bid']})" if tx["type"] == "WAIVER" else "")
                     + (f" — {u['problem']}" if u.get("problem") else ""))
        L.append("")
    rd = r["roster_diff"]
    if any(rd.values()):
        L += ["## Roster differences", "", f"- On ESPN, not in repo: {', '.join(rd['on_espn_not_in_repo']) or '—'}",
              f"- In repo, not on ESPN: {', '.join(rd['in_repo_not_on_espn']) or '—'}", ""]
    L.append(f"FAAB: ESPN ${r['faab']['espn']} · repository ${r['faab']['repository']}")
    if r["status"] == "IN_SYNC":
        L += ["", "Repository matches ESPN."]
    else:
        L += ["", "Codex: ingest the drafts in intelligence/reconcile/pending/ (Mongo Live Check workflow)."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.parse_args(argv)
    r = reconcile()
    out = ROOT / "intelligence" / "reconcile"
    pending = out / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    for f in pending.glob("*.json"):       # pending = current gaps only; ingested drafts disappear
        f.unlink()
    for u in r["unlogged_moves"]:
        d = u.get("draft")
        if d:
            name = f"{d['dedupe_key']['calendar_day_ET']}-{_slug(d['dedupe_key']['added'])}-{_slug(d['dedupe_key']['dropped'])}.json"
            (pending / name).write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    (out / "latest.json").write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str) + "\n")
    md = to_markdown(r)
    (out / "latest.md").write_text(md)
    print(md)
    if r["status"] != "IN_SYNC":
        print(f"::warning title=Mongo reconcile::{len(r['unlogged_moves'])} ESPN move(s) not in the repository; "
              f"roster diff {r['roster_diff']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
