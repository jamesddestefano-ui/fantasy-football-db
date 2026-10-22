"""Mongo 2026 auction results + value review (read-only ESPN), for the 2027 redraft auction.

Pulls the auction (mDraftDetail: every pick's player, team, price, nominator) and each drafted
player's season-to-date ESPN league-scored points, then writes:

  data/espn_api/draft_2026.json             auction results as ESPN recorded them (authoritative)
  intelligence/draft/2026_auction_review.json and .md
      - points per $ by player and position, best and worst buys
      - every manager's spending profile (positional split, top-heavy vs balanced, $1 fills)
      - how James's auction compares

Mongo is a redraft $200 auction league: nothing carries over except lessons. The review is
intelligence for the 2027 draft; the auction prices are draft evidence (AGENTS.md rule 4).

  ESPN_S2=... ESPN_SWID=... python scripts/espn_draft.py
  python scripts/espn_draft.py --review-only        # rebuild the review from saved files
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import espn_sync  # noqa: E402

SEASON = espn_sync.SEASON
DRAFT_FILE = ROOT / "data" / "espn_api" / f"draft_{SEASON}.json"
OUT_DIR = ROOT / "intelligence" / "draft"
POS_ORDER = ["QB", "RB", "WR", "TE", "D/ST", "K"]


def _season_points(player: dict) -> tuple[float | None, float | None]:
    """(actual season-to-date, projected full season) ESPN league-scored points."""
    actual = proj = None
    for st in player.get("stats") or []:
        if st.get("seasonId", SEASON) != SEASON or st.get("scoringPeriodId") not in (0, None):
            continue
        if st.get("statSplitTypeId") != 0 or st.get("appliedTotal") is None:
            continue
        if st.get("statSourceId") == 0:
            actual = round(float(st["appliedTotal"]), 2)
        elif st.get("statSourceId") == 1:
            proj = round(float(st["appliedTotal"]), 2)
    return actual, proj


def fetch_draft(cookies: dict | None, fetcher=espn_sync.fetch) -> dict:
    try:
        league = fetcher([("view", "mDraftDetail"), ("view", "mTeam"), ("view", "mSettings"), ("view", "mStatus")], cookies)
    except espn_sync.EspnError as exc:
        raise espn_sync.EspnError(f"draft results request: {exc}") from None
    period = str(league.get("scoringPeriodId") or 1)
    picks = ((league.get("draftDetail") or {}).get("picks")) or []
    ids = sorted({p["playerId"] for p in picks if p.get("playerId")})
    players, problems = [], []
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        variants = [  # most detailed first; fall back if ESPN rejects a filter
            {"players": {"filterIds": {"value": chunk}, "limit": len(chunk),
                         "filterStatsForTopScoringPeriodIds": {"value": 2, "additionalValue": [f"00{SEASON}", f"10{SEASON}"]}}},
            {"players": {"filterIds": {"value": chunk}, "limit": len(chunk)}},
        ]
        for i, flt in enumerate(variants):
            try:
                page = fetcher([("view", "kona_player_info"), ("scoringPeriodId", period)], cookies,
                               {"X-Fantasy-Filter": json.dumps(flt)})
                players.extend(page.get("players") or [])
                if i:
                    problems.append("season points unavailable for some players (stats filter rejected)")
                break
            except espn_sync.EspnError as exc:
                if i == len(variants) - 1:
                    problems.append(f"player lookup: {exc}")
    return {"league": league, "players": players, "problems": sorted(set(problems))}


def normalize_draft(raw: dict, observed_at: str) -> dict:
    league = raw["league"]
    detail = league.get("draftDetail") or {}
    teams = {t.get("id"): espn_sync._team_name(t) for t in league.get("teams") or []}
    abbrevs = {t.get("id"): t.get("abbrev") for t in league.get("teams") or []}
    info = {}
    for item in raw.get("players") or []:
        pl = item.get("player") if isinstance(item, dict) and "player" in item else item
        if not pl:
            continue
        base = espn_sync._player(pl, 0)
        actual, proj = _season_points(pl)
        info[pl.get("id")] = {**{k: base[k] for k in ("name", "position", "nfl_team")}, "season_points": actual,
                              "season_proj": proj}
    picks = []
    for p in sorted(detail.get("picks") or [], key=lambda x: x.get("overallPickNumber") or 0):
        pid = p.get("playerId")
        meta = info.get(pid, {})
        picks.append({"pick": p.get("overallPickNumber"), "espn_id": str(pid), "name": meta.get("name"),
                      "position": meta.get("position"), "nfl_team": meta.get("nfl_team"),
                      "team_id": p.get("teamId"), "team": teams.get(p.get("teamId")), "abbrev": abbrevs.get(p.get("teamId")),
                      "price": p.get("bidAmount"), "nominated_by": teams.get(p.get("nominatingTeamId")),
                      "keeper": bool(p.get("keeper")),
                      "season_points": meta.get("season_points"), "season_proj": meta.get("season_proj")})
    budget = ((league.get("settings") or {}).get("draftSettings") or {}).get("auctionBudget")
    return {"league": "mongo", "season": SEASON, "observed_at": observed_at,
            "authority": "ESPN draft results (read-only API): authoritative auction prices and buyers.",
            "drafted": detail.get("drafted"), "auction_budget": budget, "picks": picks,
            "points_note": "season_points = ESPN league-scored total to date; refreshed by later runs."}


def _median(v):
    return round(statistics.median(v), 1) if v else None


def build_review(draft: dict, my_team_id: int = espn_sync.MY_TEAM_ID) -> dict:
    picks = [p for p in draft["picks"] if p.get("price") is not None]
    for p in picks:
        pts = p.get("season_points")
        p["pts_per_dollar"] = round(pts / p["price"], 2) if pts is not None and p["price"] else None
    by_pos = {}
    for pos in [x for x in POS_ORDER if any(p["position"] == x for p in picks)]:
        rows = [p for p in picks if p["position"] == pos]
        prices = [p["price"] for p in rows]
        pts = [p["season_points"] for p in rows if p["season_points"] is not None]
        tiers = {"$30+": [p for p in rows if p["price"] >= 30], "$10-29": [p for p in rows if 10 <= p["price"] < 30],
                 "$2-9": [p for p in rows if 2 <= p["price"] < 10], "$1": [p for p in rows if p["price"] <= 1]}
        by_pos[pos] = {"drafted": len(rows), "total_spent": sum(prices), "median_price": _median(prices),
                       "max_price": max(prices) if prices else None, "median_points": _median(pts),
                       "tiers": {k: {"count": len(v), "median_points": _median([x["season_points"] for x in v
                                                                                 if x["season_points"] is not None])}
                                 for k, v in tiers.items()}}
    scored = [p for p in picks if p["season_points"] is not None]
    # Value = where a player ranked at his position by price vs by points ("paid like WR24, scored like WR5").
    for pos in by_pos:
        rows = [p for p in scored if p["position"] == pos]
        for i, p in enumerate(sorted(rows, key=lambda x: -x["price"]), start=1):
            p["price_rank"] = i
        for i, p in enumerate(sorted(rows, key=lambda x: -x["season_points"]), start=1):
            p["points_rank"] = i
        for p in rows:
            p["rank_gain"] = p["price_rank"] - p["points_rank"]
            p["value_label"] = f"paid like {pos}{p['price_rank']}, scored like {pos}{p['points_rank']}"
    best = sorted(scored, key=lambda p: (-p["rank_gain"], -p["season_points"]))[:12]
    worst = sorted([p for p in scored if p["price"] >= 10], key=lambda p: (p["rank_gain"], -p["price"]))[:12]
    managers = []
    for tid in sorted({p["team_id"] for p in picks}):
        rows = [p for p in picks if p["team_id"] == tid]
        spent = sum(p["price"] for p in rows)
        split = {pos: sum(p["price"] for p in rows if p["position"] == pos) for pos in by_pos}
        top3 = sum(sorted((p["price"] for p in rows), reverse=True)[:3])
        managers.append({"team_id": tid, "team": rows[0]["team"], "abbrev": rows[0]["abbrev"], "spent": spent,
                         "position_split": split, "top3_share": round(top3 / spent, 2) if spent else None,
                         "one_dollar_players": sum(1 for p in rows if p["price"] <= 1),
                         "most_expensive": max(rows, key=lambda p: p["price"])["name"],
                         "most_expensive_price": max(p["price"] for p in rows),
                         "season_points_drafted": round(sum(p["season_points"] or 0 for p in rows), 1)})
    managers.sort(key=lambda m: -m["season_points_drafted"])
    me = next((m for m in managers if m["team_id"] == my_team_id), None)
    mine = sorted([p for p in picks if p["team_id"] == my_team_id], key=lambda p: -p["price"])
    return {"league": "mongo", "season": draft["season"], "observed_at": draft["observed_at"],
            "kind": "INTELLIGENCE_AUCTION_REVIEW_FOR_NEXT_DRAFT", "auction_budget": draft.get("auction_budget"),
            "by_position": by_pos, "best_buys": best, "worst_buys": worst,
            "managers": managers, "james": {"profile": me, "picks": mine}}


def to_markdown(r: dict) -> str:
    L = [f"# Mongo {r['season']} auction review (points through {r['observed_at'][:10]})", "",
         "_For the 2027 redraft auction. Points are ESPN league scoring, season to date._", "",
         "## Price vs production by position", "",
         "| Pos | Drafted | $ spent | Median $ | Max $ | Median pts | $30+ pts | $10-29 pts | $2-9 pts | $1 pts |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for pos, s in r["by_position"].items():
        t = s["tiers"]
        cell = lambda k: f"{t[k]['median_points']} ({t[k]['count']})" if t[k]["count"] else "—"  # noqa: E731
        L.append(f"| {pos} | {s['drafted']} | ${s['total_spent']} | ${s['median_price']} | ${s['max_price']} | "
                 f"{s['median_points']} | {cell('$30+')} | {cell('$10-29')} | {cell('$2-9')} | {cell('$1')} |")
    L += ["", "Tier cells: median points (players).", "", "## Best buys", "", "| Player | Team | $ | Pts | Value |", "|---|---|---|---|---|"]
    for p in r["best_buys"]:
        L.append(f"| {p['name']} ({p['position']}) | {p['abbrev']} | ${p['price']} | {p['season_points']} | {p['value_label']} |")
    L += ["", "## Worst buys ($10+)", "", "| Player | Team | $ | Pts | Value |", "|---|---|---|---|---|"]
    for p in r["worst_buys"]:
        L.append(f"| {p['name']} ({p['position']}) | {p['abbrev']} | ${p['price']} | {p['season_points']} | {p['value_label']} |")
    pos_cols = list(r["by_position"])
    L += ["", "## How each manager spent", "",
          "| Team | Pts drafted | Top-3 share | $1 players | Priciest | " + " | ".join(f"{p} $" for p in pos_cols) + " |",
          "|---|---|---|---|---|" + "---|" * len(pos_cols)]
    for m in r["managers"]:
        L.append(f"| {m['team']} ({m['abbrev']}) | {m['season_points_drafted']} | {int((m['top3_share'] or 0) * 100)}% | "
                 f"{m['one_dollar_players']} | {m['most_expensive']} ${m['most_expensive_price']} | "
                 + " | ".join(str(m["position_split"].get(p, 0)) for p in pos_cols) + " |")
    j = r["james"]
    if j["profile"]:
        L += ["", "## James's auction", "", " · ".join(f"{p['name']} ${p['price']} → {p['season_points']}"
                                                      for p in j["picks"][:16])]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--review-only", action="store_true")
    args = ap.parse_args(argv)
    if not args.review_only:
        cookies = {"espn_s2": espn_sync.clean_cookie(os.environ.get("ESPN_S2"), "espn_s2"),
                   "SWID": espn_sync.clean_cookie(os.environ.get("ESPN_SWID"), "SWID")}
        secrets = [os.environ.get("ESPN_S2", ""), os.environ.get("ESPN_SWID", ""), *cookies.values()]
        try:
            raw = fetch_draft(cookies if cookies["espn_s2"] else None)
        except Exception as exc:
            print(f"::error title=ESPN draft::{type(exc).__name__}: {espn_sync.redact(str(exc), secrets)[:200]}")
            return 1
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        draft = normalize_draft(raw, now)
        for prob in raw.get("problems") or []:
            print(f"::warning title=ESPN draft::{prob}")
        if not draft["picks"]:
            print(f"::error title=ESPN draft::no picks returned (draftDetail keys: {sorted(raw['league'].get('draftDetail') or {})})")
            return 1
        DRAFT_FILE.parent.mkdir(parents=True, exist_ok=True)
        DRAFT_FILE.write_text(json.dumps(draft, indent=1, ensure_ascii=False) + "\n")
    draft = json.loads(DRAFT_FILE.read_text())
    review = build_review(draft)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{SEASON}_auction_review.json").write_text(json.dumps(review, indent=1, ensure_ascii=False) + "\n")
    md = to_markdown(review)
    (OUT_DIR / f"{SEASON}_auction_review.md").write_text(md)
    named = sum(1 for p in draft["picks"] if p["name"])
    scored = sum(1 for p in draft["picks"] if p["season_points"] is not None)
    print(f"ESPN DRAFT picks={len(draft['picks'])} named={named} with_points={scored} budget={draft.get('auction_budget')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
