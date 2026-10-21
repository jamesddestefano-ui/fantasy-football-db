"""Weekly FantasyPros pull for the Mongo board (read-only, one key, ~11 requests).

Fetches weekly PPR consensus rankings (QB, FLX, DST), rest-of-season FLX
rankings, weekly projections (QB, RB, WR, TE, DST) and the injury report.
Mongo has no kicker.
Raw responses are saved unchanged under intelligence/fantasypros/weekly/<season>-wNN/
(the repository is private), then normalized leniently into players.json.

FantasyPros' live responses did not match the supplied OpenAPI contract in the
Sparta pilot (Oct 18), so normalization looks for several known field names instead of
rejecting the batch. Unrecognized shapes are reported, never silently dropped.
FantasyPros is NFL intelligence only: it never establishes Mongo ownership or
availability (AGENTS.md rules 3-5).

Usage:
  FANTASYPROS_API_KEY=... python scripts/fp_weekly.py [--week N]
  python scripts/fp_weekly.py --normalize-only --week N   # re-normalize saved raw files
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mongo_names import name_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.fantasypros.com/public/v2/json"
SEASON = 2026
WEEK1_TUESDAY = date(2026, 9, 8)   # NFL week N runs Tuesday..Monday

# Order = priority: if FantasyPros rate-limits us, the most useful data is already saved.
# NOTE: type=WW is FantasyPros' *Waiver Wire* list (with expert notes), not weekly ranks.
#       Weekly start/sit ranks come from consensus-rankings with a week and no type.
REQUESTS = (
    [("weekly", pos, f"/nfl/{SEASON}/consensus-rankings",
      {"position": pos, "scoring": "PPR", "week": "{week}"}) for pos in ("FLX", "QB", "DST")]
    + [("waiver", "FLX", f"/nfl/{SEASON}/consensus-rankings",
        {"position": "FLX", "scoring": "PPR", "type": "WW", "week": "{week}"})]
    + [("projections", pos, f"/nfl/{SEASON}/projections", {"position": pos, "week": "{week}"})
       for pos in ("RB", "WR", "QB", "TE", "DST")]
    + [("ros", "FLX", f"/nfl/{SEASON}/consensus-rankings", {"position": "FLX", "scoring": "PPR", "type": "ROS"})]
    + [("injuries", "ALL", "/nfl/injuries", {"year": str(SEASON), "week": "{week}"})]
)
# Actual fantasy points for the previous week (for the Brain's report card); fetched once per week.
RESULT_REQUESTS = [("points", pos, f"/nfl/{SEASON}/player-points",
                    {"start": "{prev}", "end": "{prev}", "position": pos, "scoring": "PPR"})
                   for pos in ("QB", "RB", "WR", "TE", "DST")]
SPACING_S = 2.5
SCORING_NOTE = ("FantasyPros standard PPR. Mongo is ESPN PPR with 6-pt pass TD and -2 INT, so QB and "
                "D/ST points differ from Mongo's. Prefer ESPN league-scored points "
                "(data/espn_api/latest.json last_week) for grading; use this file as a fallback.")
RETRY_WAITS_S = (15, 30, 60)


def current_week(today: date | None = None) -> int:
    today = today or datetime.now(timezone.utc).date()
    return max(1, min(18, (today - WEEK1_TUESDAY).days // 7 + 1))


def week_dir(week: int, root: Path = ROOT) -> Path:
    return root / "intelligence" / "fantasypros" / "weekly" / f"{SEASON}-w{week:02d}"


class RateLimited(RuntimeError):
    pass


def fetch(path: str, params: dict, api_key: str, timeout: int = 20, sleep=time.sleep) -> dict:
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"x-api-key": api_key, "Accept": "application/json",
                                               "User-Agent": "fantasy-football-db/1.0"})
    for attempt, wait in enumerate((*RETRY_WAITS_S, None)):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and wait is not None:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    wait = max(wait, min(120, int(retry_after)))
                except (TypeError, ValueError):
                    pass
                sleep(wait)
                continue
            if exc.code == 429:
                raise RateLimited(f"{path} HTTP 429 after {attempt} retries") from None
            raise RuntimeError(f"{path} HTTP {exc.code}") from None
    raise RateLimited(f"{path} HTTP 429")


# ------------------------------------------------------------ normalization

def _first(d: dict, *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def player_rows(payload) -> list[dict]:
    """Find the list of player-like dicts in a response, whatever it is called."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("players", "injuries", "data", "rankings", "items"):
        v = payload.get(key)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    for v in payload.values():
        if isinstance(v, list) and v and isinstance(v[0], dict) and any(
                k in v[0] for k in ("player_name", "name", "player_id", "fpid")):
            return v
    return []


def ppr_points(row: dict):
    stats = row.get("stats")
    if isinstance(stats, list):
        stats = stats[0] if stats and isinstance(stats[0], dict) else {}
    if isinstance(stats, dict):
        for k in ("points_ppr", "fpts_ppr", "ppr"):
            if stats.get(k) is not None:
                return _num(stats[k])
        # DST/K projections have a single points value
        if stats.get("points") is not None and stats.get("points_ppr") is None:
            return _num(stats["points"])
    return _num(_first(row, "points_ppr", "fpts_ppr", "proj_ppr", "fpts", "points"))


def base_player(row: dict) -> dict:
    name = _first(row, "player_name", "name", "player")
    pos = _first(row, "player_position_id", "position_id", "position", "pos")
    team = _first(row, "player_team_id", "team_id", "team", "player_team")
    return {
        "name": name,
        "position": (str(pos).upper().replace("DST", "DEF") if pos else None),
        "nfl_team": team,
        "fp_id": str(_first(row, "player_id", "fpid", "id", default="")) or None,
        "yahoo_id": str(_first(row, "player_yahoo_id", "yahoo_id", default="")) or None,
        "key": name_key(name, team, "DEF" if str(pos).upper() in ("DST", "DEF") else pos) if name else None,
    }


def normalize(raw: dict[str, dict]) -> dict:
    players: dict[str, dict] = {}
    report: dict[str, dict] = {}

    def merge(row: dict) -> dict | None:
        b = base_player(row)
        if not b["key"]:
            return None
        cur = players.setdefault(b["key"], {k: v for k, v in b.items() if k != "key"})
        for k, v in b.items():
            if k != "key" and v and not cur.get(k):
                cur[k] = v
        return cur

    for label, payload in raw.items():
        kind = label.split("_")[0]
        rows = player_rows(payload)
        used = 0
        for row in rows:
            p = merge(row)
            if p is None:
                continue
            used += 1
            owned = _num(_first(row, "player_owned_yahoo"))
            if owned is not None:
                p["yahoo_rostered_pct"] = owned
            owned_espn = _num(_first(row, "player_owned_espn"))
            if owned_espn is not None:
                p["espn_rostered_pct"] = owned_espn
            if kind in ("weekly", "consensus"):
                ptype = str(payload.get("ranking_type_name", "")).lower() if isinstance(payload, dict) else ""
                if ptype == "waiver":   # FantasyPros returned its waiver list; treat it as such
                    p["waiver_rank"] = _num(_first(row, "rank_ecr", "rank"))
                    p["waiver_list"] = payload.get("position_id")
                    p["waiver_note"] = _first(row, "note")
                    continue
                p["ecr_rank"] = _num(_first(row, "rank_ecr", "ecr", "rank"))
                p["ecr_pos_rank"] = _first(row, "pos_rank", "position_rank")
                p["ecr_min"], p["ecr_max"] = _num(row.get("rank_min")), _num(row.get("rank_max"))
                p["ecr_std"] = _num(row.get("rank_std"))
                p["opponent"] = _first(row, "player_opponent", "opponent")
                p["bye_week"] = _first(row, "player_bye_week", "bye_week")
                p["game_status"] = _first(row, "player_game_status")
            elif kind == "waiver":
                p["waiver_rank"] = _num(_first(row, "rank_ecr", "rank"))
                p["waiver_list"] = payload.get("position_id") if isinstance(payload, dict) else None
                p["waiver_note"] = _first(row, "note")
                p["opponent"] = p.get("opponent") or _first(row, "player_opponent")
                p["bye_week"] = p.get("bye_week") or _first(row, "player_bye_week")
            elif kind == "ros":
                p["ros_rank"] = _num(_first(row, "rank_ecr", "ecr", "rank"))
            elif kind == "projections":
                p["proj_ppr"] = ppr_points(row)
            elif kind == "injuries":
                p["injury_status"] = _first(row, "injury_status", "status", "game_status")
                p["injury_detail"] = _first(row, "injury", "injury_type", "description")
                p["practice"] = _first(row, "practice_status", "practice")
        report[label] = {"rows_found": len(rows), "rows_used": used,
                         "ranking_type": payload.get("ranking_type_name") if isinstance(payload, dict) else None,
                         "top_level_keys": sorted(payload)[:20] if isinstance(payload, dict) else type(payload).__name__,
                         "sample_row_keys": sorted(rows[0])[:30] if rows else []}
    return {"players": sorted(players.values(), key=lambda p: (p.get("ecr_rank") or 9999, p["name"])),
            "sources": report}


def write_results(week: int, out_root: Path = ROOT) -> dict:
    """Normalize saved player-points files into results.json: {name_key: {name, position, points}}."""
    res_dir = week_dir(week, out_root) / "results"
    out = {}
    for f in sorted(res_dir.glob("points_*.json")):
        for row in player_rows(json.loads(f.read_text())):
            b = base_player(row)
            if not b["key"]:
                continue
            pts = None
            weeks = row.get("weeks") or row.get("points")
            if isinstance(row.get("points"), (int, float)) and not isinstance(row.get("points"), bool):
                pts = _num(row["points"])           # exact single-week total; "weeks" is rounded to 0.1
            elif isinstance(weeks, dict):
                pts = _num(weeks.get(str(week)) if weeks.get(str(week)) is not None else next(iter(weeks.values()), None))
            if pts is None:
                pts = _num(_first(row, "points", "fpts", "points_ppr", "total"))
            out[b["key"]] = {"name": b["name"], "position": b["position"], "nfl_team": b["nfl_team"], "points": pts}
    if out:
        (week_dir(week, out_root) / "results.json").write_text(
            json.dumps({"season": SEASON, "week": week, "scoring": "PPR",
                        "scoring_note": SCORING_NOTE, "players": out}, indent=1,
                       ensure_ascii=False) + "\n")
    return out


def pull_results(week: int, api_key: str, out_root: Path = ROOT, fetcher=fetch) -> list:
    """Fetch actual PPR points for a completed week into results/ and write results.json.

    Files already saved are not re-requested, so re-running only fills gaps."""
    errors = []
    res_dir = week_dir(week, out_root) / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    for kind, pos, path, params in RESULT_REQUESTS:
        target = res_dir / f"{kind}_{pos}.json"
        if target.exists():
            continue
        p = {k: v.replace("{prev}", str(week)) for k, v in params.items()}
        try:
            payload = fetcher(path, p, api_key)
        except RateLimited as exc:
            errors.append(f"results w{week} {pos}: {exc}")
            break
        except Exception as exc:
            errors.append(f"results w{week} {pos}: {exc}")
            continue
        target.write_text(json.dumps(payload, indent=1, ensure_ascii=False))
        time.sleep(SPACING_S)
    write_results(week, out_root)
    return errors


# ------------------------------------------------------------------- main

def run(week: int, api_key: str | None, out_root: Path = ROOT, normalize_only: bool = False,
        fetcher=fetch) -> dict:
    wdir = week_dir(week, out_root)
    raw_dir = wdir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    if not normalize_only:
        if not api_key:
            raise SystemExit("FANTASYPROS_API_KEY is not set")
        for kind, pos, path, params in REQUESTS:
            p = {k: v.replace("{week}", str(week)) for k, v in params.items()}
            try:
                payload = fetcher(path, p, api_key)
            except RateLimited as exc:
                errors.append(f"{kind}_{pos}: {exc}; stopped to respect FantasyPros rate limit")
                break
            except Exception as exc:  # keep going; report per endpoint
                errors.append(f"{kind}_{pos}: {exc}")
                continue
            (raw_dir / f"{kind}_{pos}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))
            time.sleep(SPACING_S)
        if week - 1 >= 1:
            errors += pull_results(week - 1, api_key, out_root, fetcher)
    raw = {f.stem: json.loads(f.read_text()) for f in sorted(raw_dir.glob("*.json"))}
    norm = normalize(raw)
    norm.update({"season": SEASON, "week": week, "pulled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "errors": errors, "authority": "NFL intelligence only; never Mongo ownership/availability"})
    (wdir / "players.json").write_text(json.dumps(norm, indent=1, ensure_ascii=False) + "\n")
    return norm


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--normalize-only", action="store_true")
    ap.add_argument("--results-only", metavar="WEEKS",
                    help="only fetch actual points for completed weeks, e.g. 6 or 1-6 (no board pull)")
    args = ap.parse_args(argv)
    if args.results_only:
        key = os.environ.get("FANTASYPROS_API_KEY", "").strip()
        if not key:
            raise SystemExit("FANTASYPROS_API_KEY is not set")
        a, _, b = args.results_only.partition("-")
        weeks = range(int(a), int(b or a) + 1)
        errors, missing = [], []
        for w in weeks:
            errors += pull_results(w, key)
            res = week_dir(w) / "results.json"
            n = len(json.loads(res.read_text())["players"]) if res.exists() else 0
            print(f"RESULTS WEEK {w}: players={n}")
            if not n:
                missing.append(w)
        for e in errors:
            print(f"::warning title=FantasyPros results::{e}")
        return 1 if missing else 0
    week = args.week or current_week()
    out = run(week, os.environ.get("FANTASYPROS_API_KEY", "").strip() or None, normalize_only=args.normalize_only)
    print(f"FANTASYPROS WEEK {week}: players={len(out['players'])} errors={len(out['errors'])}")
    for label, r in out["sources"].items():
        print(f"  {label}: rows={r['rows_found']} used={r['rows_used']}")
    for e in out["errors"]:
        print(f"::warning title=FantasyPros::{e}")
    empty = [l for l, r in out["sources"].items() if r["rows_used"] == 0]
    if empty:
        print(f"::warning title=FantasyPros format::No players read from {empty}; raw files saved for review.")
    return 0 if out["players"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
