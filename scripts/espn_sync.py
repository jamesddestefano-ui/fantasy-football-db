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
    value = tokens[0] if tokens else ""
    return value.strip().strip('"').strip(";")


def redact(text: str, secrets: list[str]) -> str:
    for sec in secrets:
        if sec and len(sec) >= 6:
            text = text.replace(sec, "[redacted]")
    text = re.sub(r"(espn_s2|SWID)=\S+", r"\1=[redacted]", text)
    return re.sub(r"[A-Za-z0-9%+/=]{40,}", "[redacted]", text)


def fetch(params: list[tuple[str, str]], cookies: dict[str, str] | None, headers: dict | None = None,
          timeout: int = 30) -> dict:
    url = BASE.format(season=SEASON, league=LEAGUE_ID) + "?" + urllib.parse.urlencode(params)
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
        return json.loads(body)
    except json.JSONDecodeError:
        raise EspnError("ESPN returned non-JSON (often an expired/invalid espn_s2 cookie)") from None


def fetch_all(cookies: dict | None, fetcher=fetch) -> dict:
    league = fetcher([("view", v) for v in ("mTeam", "mRoster", "mSettings", "mStatus")], cookies)
    period = int(league.get("scoringPeriodId") or (league.get("status") or {}).get("currentMatchupPeriod") or 1)
    pool = fetcher([("view", "kona_player_info"), ("scoringPeriodId", str(period))], cookies,
                   {"X-Fantasy-Filter": json.dumps(FREE_AGENT_FILTER)})
    last = None
    if period > 1:
        last = fetcher([("view", "mRoster"), ("view", "mTeam"), ("scoringPeriodId", str(period - 1))], cookies)
    return {"league": league, "pool": pool, "last_week": last}


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
    return t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}".strip() or t.get("abbrev") or str(t.get("id"))


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
                 "faab_remaining": (budget - spent) if budget is not None and spent is not None else None,
                 "roster": [r["name"] for r in roster]}
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
        "available": available, "last_week": last_week,
    }


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
               for k in ("league", "pool", "last_week")}
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
    me = snap["my_team"]
    print(f"ESPN MONGO week={snap['scoring_period']} team={me['name']} record={me['record']} "
          f"faab=${me['faab_remaining']} roster={len(me['roster'])} available={len(snap['available'])} -> {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
