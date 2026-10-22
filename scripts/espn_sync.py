"""Read-only ESPN snapshot for Mongo (league 1470431049, James = teamId 2).

Pulls the league (teams, rosters, FAAB, settings, status), the free-agent/waiver pool
and last week's league-scored points, then writes a compact normalized snapshot:

  data/espn_api/latest.json            (newest snapshot)
  data/espn_api/<YYYY-MM-DDTHHMMZ>.json (dated copy, append-only history)

Authority (AGENTS.md rules 4-5, 8): an ESPN snapshot is "ESPN current ownership" evidence.
This script never mutates data/fantasy.db or seed history; ingesting a completed
transaction stays a separate, reviewed step. A player missing from every roster in the
snapshot is FREE_AGENT/WAIVERS only as of `observed_at` — re-check before bidding.

Credentials (repository secrets, never committed): ESPN_S2 and ESPN_SWID — the `espn_s2`
and `SWID` cookies from a signed-in espn.com browser session. Without them the script
tries an anonymous read, which works only if the league is viewable publicly.

  ESPN_S2=... ESPN_SWID={...} python scripts/espn_sync.py
  python scripts/espn_sync.py --from-raw dir/   # re-normalize saved raw responses (tests)
"""
from __future__ import annotations

import argparse
import re
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mongo_names import name_key, team_abbr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "espn_api"
LEAGUE_ID = "1470431049"
MY_TEAM_ID = 2
SEASON = 2026
BASE = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        "/segments/0/leagues/{league}")

POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
SLOTS = {0: "QB", 2: "RB", 3: "RB/WR", 4: "WR", 5: "WR/TE", 6: "TE", 7: "OP", 16: "D/ST", 17: "K",
         20: "BN", 21: "IR", 23: "FLEX"}
PRO_TEAMS = {0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET",
             9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN",
             17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC",
             25: "SF", 26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU"}
FREE_AGENT_FILTER = {"players": {
    "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
    "filterSlotIds": {"value": [0, 2, 4, 6, 16, 23]},
    "limit": 250,
    "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
}}


class EspnError(RuntimeError):
    pass


def clean_cookie(raw: str | None, name: str) -> str:
    """Return just the cookie value, even if a whole DevTools row was pasted
    ("espn_s2<TAB>AEB...<TAB>.espn.com<TAB>/ ..."). Never logs the value."""
    if not raw:
        return ""
    tokens = [t for t in re.split(r"\s+", raw.strip()) if t]
    tokens = [t for t in tokens if t.lower() != name.lower()]
    if tokens and "=" in tokens[0] and tokens[0].split("=", 1)[0].lower() == name.lower():
        tokens[0] = tokens[0].split("=", 1)[1]
    value = (tokens[0] if tokens else "").strip().strip('"').strip(";")
    if name.upper() == "SWID":
        value = value.replace("%7B", "{").replace("%7b", "{").replace("%7D", "}").replace("%7d", "}")
        if re.fullmatch(r"[0-9A-Fa-f-]{36}", value):
            value = "{" + value + "}"
    return value


def redact(text: str, secrets: list[str]) -> str:
    for sec in secrets:
        if sec and len(sec) >= 6:
            text = text.replace(sec, "[redacted]")
    text = re.sub(r"(espn_s2|SWID)=\S+", r"\1=[redacted]", text)
    return re.sub(r"[A-Za-z0-9%+/=]{40,}", "[redacted]", text)


PLAYERS_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"


def fetch(params: list[tuple[str, str]], cookies: dict[str, str] | None, headers: dict | None = None,
          timeout: int = 30, base: str | None = None):
    url = (base or BASE).format(season=SEASON, league=LEAGUE_ID) + "?" + urllib.parse.urlencode(params)
    h = {"Accept": "application/json", "User-Agent": "fantasy-football-db/1.0 (read-only)"}
    if cookies and cookies.get("espn_s2") and cookies.get("SWID"):
        h["Cookie"] = f"espn_s2={cookies['espn_s2']}; SWID={cookies['SWID']}"
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        hint = (" — league is private: set ESPN_S2 and ESPN_SWID secrets (or refresh them; they expire)"
                if exc.code in (401, 403) else "")
        raise EspnError(f"ESPN HTTP {exc.code}{hint}") from None
    try:
        return json.loads(body)  # dict for league views; list for the players endpoint
    except json.JSONDecodeError:
        raise EspnError("ESPN returned non-JSON (often an expired/invalid espn_s2 cookie)") from None


def fetch_all(cookies: dict | None, fetcher=fetch) -> dict:
    league = fetcher([("view", v) for v in ("mTeam", "mRoster", "mSettings", "mStatus", "mMatchup")], cookies)
    period = int(league.get("scoringPeriodId") or (league.get("status") or {}).get("currentMatchupPeriod") or 1)
    pool = fetcher([("view", "kona_player_info"), ("scoringPeriodId", str(period))], cookies,
                   {"X-Fantasy-Filter": json.dumps(FREE_AGENT_FILTER)})
    last = None
    if period > 1:
        last = fetcher([("view", "mRoster"), ("view", "mTeam"), ("scoringPeriodId", str(period - 1))], cookies)
    tx_pages, problems = [], []
    for p in range(1, period + 1):        # whole season every run: deterministic, ~8 small requests
        try:
            tx_pages.append(fetcher([("view", "mTransactions2"), ("scoringPeriodId", str(p))], cookies))
        except Exception as exc:  # transactions are an add-on; never block the snapshot
            problems.append(f"transactions week {p}: {type(exc).__name__}")
    known = _known_ids(league, pool)
    missing = sorted({i for page in tx_pages for t in (page.get("transactions") or [])
                      for i in (it.get("playerId") for it in (t.get("items") or [])) if i and i not in known})
    lookup = []
    for k in range(0, len(missing), 100):
        try:
            flt = {"players": {"filterIds": {"value": missing[k:k + 100]}, "limit": 100}}
            lookup.append(fetcher([("view", "kona_player_info"), ("scoringPeriodId", str(period))], cookies,
                                  {"X-Fantasy-Filter": json.dumps(flt)}))
        except Exception as exc:
            problems.append(f"player lookup: {type(exc).__name__}")
    return {"league": league, "pool": pool, "last_week": last, "transactions": tx_pages,
            "player_lookup": lookup, "fetch_problems": problems}


def _known_ids(*payloads) -> set:
    ids = set()
    for pl in _iter_players(*payloads):
        ids.add(pl.get("id"))
    return ids


def _iter_players(*payloads):
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for t in payload.get("teams") or []:
            for e in ((t.get("roster") or {}).get("entries") or []):
                pl = (e.get("playerPoolEntry") or {}).get("player")
                if pl:
                    yield pl
        for item in payload.get("players") or []:
            pl = item.get("player") if isinstance(item, dict) else None
            if pl:
                yield pl


# ------------------------------------------------------------ normalization

def _points(player: dict, period: int, source: int) -> float | None:
    """ESPN league-scored points (appliedTotal) for one scoring period; source 0=actual, 1=projected."""
    for st in player.get("stats") or []:
        if (st.get("scoringPeriodId") == period and st.get("statSourceId") == source
                and st.get("statSplitTypeId", 1) == 1 and st.get("appliedTotal") is not None):
            return round(float(st["appliedTotal"]), 2)
    return None


def _player(p: dict, period: int) -> dict:
    pos = POSITIONS.get(p.get("defaultPositionId"), str(p.get("defaultPositionId")))
    nfl = team_abbr(PRO_TEAMS.get(p.get("proTeamId"), str(p.get("proTeamId"))))
    name = p.get("fullName") or f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
    own = p.get("ownership") or {}
    return {
        "name": name, "position": pos, "nfl_team": nfl, "espn_id": str(p.get("id")) if p.get("id") else None,
        "injury_status": p.get("injuryStatus") or ("ACTIVE" if p.get("injured") is False else None),
        "proj": _points(p, period, 1), "pct_owned": round(own["percentOwned"], 1) if own.get("percentOwned") is not None else None,
        "key": name_key(name, nfl, pos),
    }


def _team_name(t: dict) -> str:
    name = (t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}").strip()
    return " ".join(name.split()) or t.get("abbrev") or str(t.get("id"))


def _roster(team: dict, period: int, actual: bool = False) -> list[dict]:
    rows = []
    for e in ((team.get("roster") or {}).get("entries") or []):
        pl = ((e.get("playerPoolEntry") or {}).get("player")) or {}
        if not pl:
            continue
        row = _player(pl, period)
        row["slot"] = SLOTS.get(e.get("lineupSlotId"), str(e.get("lineupSlotId")))
        row["injury_status"] = e.get("injuryStatus") or row["injury_status"]
        if actual:
            row["actual"] = _points(pl, period, 0)
        rows.append(row)
    return rows


def normalize(raw: dict, observed_at: str) -> dict:
    league = raw["league"]
    period = int(league.get("scoringPeriodId") or 1)
    settings = league.get("settings") or {}
    budget = (settings.get("acquisitionSettings") or {}).get("acquisitionBudget")
    teams, owned, me = [], {}, None
    for t in league.get("teams") or []:
        spent = (t.get("transactionCounter") or {}).get("acquisitionBudgetSpent")
        rec = ((t.get("record") or {}).get("overall")) or {}
        roster = _roster(t, period)
        entry = {"team_id": t.get("id"), "name": _team_name(t), "abbrev": t.get("abbrev"),
                 "record": f"{rec.get('wins', 0)}-{rec.get('losses', 0)}-{rec.get('ties', 0)}" if rec else None,
                 "points_for": round(rec["pointsFor"], 2) if rec.get("pointsFor") is not None else None,
                 "faab_remaining": (budget - spent) if budget is not None and spent is not None else None,
                 "faab_spent": spent,
                 "roster": [{k: r[k] for k in ("name", "position", "nfl_team", "slot", "proj", "injury_status")}
                            for r in roster]}
        teams.append(entry)
        for r in roster:
            if r["key"]:
                owned[r["key"]] = t.get("id")
        if t.get("id") == MY_TEAM_ID:
            me = {**{k: v for k, v in entry.items() if k != "roster"}, "roster": roster}
    if me is None:
        raise EspnError(f"teamId {MY_TEAM_ID} not in ESPN response (wrong league or no access)")
    available = []
    for item in (raw.get("pool") or {}).get("players") or []:
        status = item.get("status")
        if status not in ("FREEAGENT", "WAIVERS"):
            continue
        row = _player(item.get("player") or {}, period)
        if not row["key"] or row["key"] in owned:
            continue        # roster data wins over a stale pool row
        row["status"] = status
        available.append(row)
    last_week = None
    if raw.get("last_week"):
        for t in raw["last_week"].get("teams") or []:
            if t.get("id") == MY_TEAM_ID:
                rows = _roster(t, period - 1, actual=True)
                starters = [r for r in rows if r["slot"] not in ("BN", "IR")]
                last_week = {"week": period - 1, "players": [{k: v for k, v in r.items() if k != "key"} for r in rows],
                             "starter_points": round(sum(r["actual"] or 0 for r in starters), 2)}
    matchup = _matchup(league, teams)
    for r in me["roster"]:
        r.pop("key", None)
    for r in available:
        r.pop("key", None)
    return {
        "league": "mongo", "espn_league_id": LEAGUE_ID, "season": league.get("seasonId", SEASON),
        "observed_at": observed_at, "scoring_period": period,
        "authority": ("ESPN current ownership evidence as of observed_at (read-only API). Does not by itself "
                      "write transactions; availability must be re-checked before a claim."),
        "faab_budget": budget, "waiver_settings": {k: (settings.get("acquisitionSettings") or {}).get(k)
                                                   for k in ("waiverProcessDays", "waiverProcessHour", "minimumBid", "isUsingAcquisitionBudget")},
        "my_team": me, "teams": teams, "owned_keys": owned,
        "available": available, "last_week": last_week, "matchup": matchup,
        "fetch_problems": raw.get("fetch_problems") or [],
    }


def _starter_proj(roster: list[dict]) -> float:
    return round(sum(r.get("proj") or 0 for r in roster if r.get("slot") not in ("BN", "IR")), 2)


def _matchup(league: dict, teams: list[dict]) -> dict | None:
    """This week's opponent from the ESPN schedule (mMatchup view)."""
    status = league.get("status") or {}
    week = status.get("currentMatchupPeriod") or league.get("scoringPeriodId")
    by_id = {t["team_id"]: t for t in teams}
    for g in league.get("schedule") or []:
        if g.get("matchupPeriodId") != week:
            continue
        home, away = (g.get("home") or {}).get("teamId"), (g.get("away") or {}).get("teamId")
        if MY_TEAM_ID not in (home, away):
            continue
        opp_id = away if home == MY_TEAM_ID else home
        me, opp = by_id.get(MY_TEAM_ID), by_id.get(opp_id)
        if not opp:
            return {"week": week, "opponent_team_id": opp_id, "bye": opp_id is None}
        return {"week": week, "opponent_team_id": opp_id, "opponent": opp["name"], "opponent_abbrev": opp["abbrev"],
                "opponent_record": opp["record"], "opponent_points_for": opp.get("points_for"),
                "my_proj": _starter_proj(me["roster"]), "opponent_proj": _starter_proj(opp["roster"]),
                "opponent_starters": [{k: r[k] for k in ("slot", "name", "nfl_team", "proj", "injury_status")}
                                      for r in opp["roster"] if r["slot"] not in ("BN", "IR")]}
    return None


SKIP_TX_TYPES = {"ROSTER", "DRAFT", "FUTURE_ROSTER", "RETRO_ROSTER"}


def _ms_to_iso(ms) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_transactions(raw: dict, snapshot: dict) -> dict:
    """Season transactions (waivers incl. failed bids, free-agent moves, trades) with player names."""
    names: dict = {}
    for pl in _iter_players(raw.get("league"), raw.get("pool"), *(raw.get("player_lookup") or [])):
        names[pl.get("id")] = _player(pl, snapshot["scoring_period"])
    team_names = {t["team_id"]: t["name"] for t in snapshot["teams"]}
    seen, rows, types = set(), [], {}
    for page in raw.get("transactions") or []:
        for t in (page or {}).get("transactions") or []:
            tid = t.get("id")
            if tid in seen:
                continue
            seen.add(tid)
            ttype = t.get("type") or "?"
            types[ttype] = types.get(ttype, 0) + 1
            if ttype in SKIP_TX_TYPES:
                continue
            items = []
            for it in t.get("items") or []:
                kind = it.get("type")
                if kind not in ("ADD", "DROP"):
                    continue
                pl = names.get(it.get("playerId")) or {}
                items.append({"type": kind, "espn_id": str(it.get("playerId")), "name": pl.get("name"),
                              "position": pl.get("position"), "nfl_team": pl.get("nfl_team"),
                              "from_team_id": it.get("fromTeamId"), "to_team_id": it.get("toTeamId")})
            if not items:
                continue
            rows.append({
                "id": tid, "type": ttype, "status": t.get("status"), "team_id": t.get("teamId"),
                "team": team_names.get(t.get("teamId")), "bid": t.get("bidAmount"),
                "scoring_period": t.get("scoringPeriodId"),
                "processed_at": _ms_to_iso(t.get("processDate")) or _ms_to_iso(t.get("proposedDate")),
                "adds": [i for i in items if i["type"] == "ADD"], "drops": [i for i in items if i["type"] == "DROP"],
            })
    rows.sort(key=lambda r: (r["processed_at"] or "", str(r["id"])))
    return {"league": "mongo", "observed_at": snapshot["observed_at"], "season": snapshot["season"],
            "authority": "ESPN transaction log (read-only). Completed (EXECUTED) rows are ownership evidence; "
                         "ingest into data/imports is a separate reviewed step.",
            "raw_type_counts": dict(sorted(types.items())), "transactions": rows}


def write(snapshot: dict, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(snapshot, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    stamp = snapshot["observed_at"][:16].replace(":", "")
    dated = out_dir / f"{stamp}Z.json"
    dated.write_text(text)
    (out_dir / "latest.json").write_text(text)
    if json.loads((out_dir / "latest.json").read_text()) != snapshot:
        raise EspnError("read-back of latest.json does not match")
    return dated


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-raw", type=Path, help="directory with league.json, pool.json[, last_week.json]")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if args.from_raw:
        raw = {k: (json.loads((args.from_raw / f"{k}.json").read_text()) if (args.from_raw / f"{k}.json").exists() else None)
               for k in ("league", "pool", "last_week", "transactions", "player_lookup")}
    else:
        cookies = {"espn_s2": clean_cookie(os.environ.get("ESPN_S2"), "espn_s2"),
                   "SWID": clean_cookie(os.environ.get("ESPN_SWID"), "SWID")}
        if cookies["SWID"] and not re.fullmatch(r"\{[0-9A-Fa-f-]{36}\}", cookies["SWID"]):
            print("::warning title=ESPN sync::ESPN_SWID does not look like {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}; re-copy it")
        secrets = [os.environ.get("ESPN_S2", ""), os.environ.get("ESPN_SWID", ""), *cookies.values()]
        try:
            raw = fetch_all(cookies if cookies["espn_s2"] else None)
        except EspnError as exc:
            print(f"::error title=ESPN sync::{exc}")
            return 1
        except Exception as exc:  # network/TLS/etc.: report the type, never the cookies
            print(f"::error title=ESPN sync::{type(exc).__name__}: {redact(str(exc), secrets)[:200]}")
            return 1
    try:
        snap = normalize(raw, now)
    except EspnError as exc:
        print(f"::error title=ESPN sync::{exc}")
        return 1
    except Exception as exc:
        keys = sorted(raw["league"])[:25] if isinstance(raw.get("league"), dict) else type(raw.get("league")).__name__
        print(f"::error title=ESPN sync::could not read ESPN response ({type(exc).__name__}: {str(exc)[:200]}); league keys={keys}")
        return 1
    path = write(snap, args.out)
    try:
        tx = normalize_transactions(raw, snap)
        (args.out / "transactions.json").write_text(json.dumps(tx, indent=1, ensure_ascii=False) + "\n")
        print(f"ESPN TRANSACTIONS rows={len(tx['transactions'])} raw_types={tx['raw_type_counts']}")
    except Exception as exc:
        print(f"::warning title=ESPN transactions::could not normalize ({type(exc).__name__}: {str(exc)[:150]})")
    for prob in snap.get("fetch_problems") or []:
        print(f"::warning title=ESPN sync::{prob}")
    me = snap["my_team"]
    print(f"ESPN MONGO week={snap['scoring_period']} team={me['name']} record={me['record']} "
          f"faab=${me['faab_remaining']} roster={len(me['roster'])} available={len(snap['available'])} -> {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
