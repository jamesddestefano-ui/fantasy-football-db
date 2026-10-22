"""Mongo FAAB market: what this league actually pays on waivers.

Input: data/espn_api/transactions.json (scripts/espn_sync.py) and data/espn_api/latest.json.
Output: intelligence/faab_market.json and intelligence/faab_market.md

For each completed waiver claim: player, position, winning team, winning bid, and the
losing bids ESPN recorded for the same player in the same run (failed claims carry their
bidAmount). Summaries by position and by week, plus every team's remaining budget.
Intelligence for bid sizing (learning rule mongo-learning-009); never ownership.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


OUTBID = "FAILED_INVALIDPLAYERSOURCE"


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    v = sorted(values)
    i = (len(v) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo), 1)


def build(root: Path = ROOT) -> dict:
    tx = json.loads((root / "data" / "espn_api" / "transactions.json").read_text())
    snap = json.loads((root / "data" / "espn_api" / "latest.json").read_text())
    waivers = [t for t in tx["transactions"] if t["type"] == "WAIVER" and t["adds"]]
    # group by (waiver run, player) so losing bids sit next to the winner. Only FAILED_INVALIDPLAYERSOURCE
    # (player already awarded = outbid) counts as a losing bid; PENDING/CANCELED and other failures
    # (e.g. the bidder's drop was gone) are not evidence of the market price.
    groups = defaultdict(list)
    for t in waivers:
        if t["status"] in ("PENDING", "CANCELED") or not t["processed_at"]:
            continue
        a = t["adds"][0]
        groups[(t["processed_at"][:13], a["espn_id"])].append(t)
    claims = []
    for (_, _), rows in groups.items():
        win = next((r for r in rows if r["status"] == "EXECUTED"), None)
        if not win:
            continue
        a = win["adds"][0]
        losers = sorted((r["bid"] for r in rows if r is not win and r["bid"] is not None
                         and r["status"] == OUTBID), reverse=True)
        claims.append({"processed_at": win["processed_at"], "week": win["scoring_period"], "player": a["name"],
                       "position": a["position"], "nfl_team": a["nfl_team"], "team": win["team"],
                       "team_id": win["team_id"], "winning_bid": win["bid"], "losing_bids": losers,
                       "runner_up_bid": losers[0] if losers else None,
                       "overpay_vs_runner_up": (win["bid"] - losers[0]) if losers and win["bid"] is not None else None})
    claims.sort(key=lambda c: c["processed_at"] or "")
    by_pos = {}
    for pos in sorted({c["position"] for c in claims if c["position"]}):
        bids = [c["winning_bid"] for c in claims if c["position"] == pos and c["winning_bid"] is not None]
        paid = [b for b in bids if b > 0]
        by_pos[pos] = {"claims": len(bids), "paid_claims": len(paid), "median": _pct(paid, 0.5),
                       "p75": _pct(paid, 0.75), "max": max(paid) if paid else None}
    by_week = {}
    for w in sorted({c["week"] for c in claims if c["week"]}):
        bids = [c["winning_bid"] for c in claims if c["week"] == w and c["winning_bid"]]
        by_week[str(w)] = {"claims": len([c for c in claims if c["week"] == w]), "spent": sum(bids),
                           "max": max(bids) if bids else None}
    top = sorted([c for c in claims if c["winning_bid"]], key=lambda c: -c["winning_bid"])[:15]
    mine = [c for c in claims if c["team_id"] == 2]
    mine_lost = [t for t in waivers if t["team_id"] == 2 and str(t["status"]).startswith("FAILED")]
    over = [c["overpay_vs_runner_up"] for c in claims if c["overpay_vs_runner_up"] is not None]
    return {
        "league": "mongo", "observed_at": tx["observed_at"],
        "kind": "INTELLIGENCE_FAAB_MARKET",
        "budgets": sorted([{"team": t["name"], "abbrev": t["abbrev"], "remaining": t["faab_remaining"],
                            "spent": t.get("faab_spent")} for t in snap["teams"]],
                          key=lambda b: -(b["remaining"] or 0)),
        "by_position": by_pos, "by_week": by_week, "top_claims": top,
        "median_overpay_vs_runner_up": _pct(over, 0.5) if over else None,
        "james": {"won": len(mine), "spent": sum(c["winning_bid"] or 0 for c in mine),
                  "lost_claims": [{"player": (t["adds"][0]["name"]), "bid": t["bid"], "status": t["status"],
                                   "week": t["scoring_period"]} for t in mine_lost]},
        "claims": claims,
    }


def to_markdown(m: dict) -> str:
    L = [f"# Mongo FAAB market (as of {m['observed_at']})", "",
         "_What Mongo managers actually pay. Use for bid sizing; never availability._", "",
         "## Budgets left", "", "| Team | Left | Spent |", "|---|---|---|"]
    for b in m["budgets"]:
        L.append(f"| {b['team']} ({b['abbrev']}) | ${b['remaining']} | ${b['spent']} |")
    L += ["", "## Winning bids by position (paid claims)", "", "| Pos | Claims | Paid | Median | 75th % | Max |", "|---|---|---|---|---|---|"]
    for pos, s in m["by_position"].items():
        L.append(f"| {pos} | {s['claims']} | {s['paid_claims']} | {'$%g' % s['median'] if s['median'] is not None else '—'} | "
                 f"{'$%g' % s['p75'] if s['p75'] is not None else '—'} | {'$%g' % s['max'] if s['max'] is not None else '—'} |")
    if m["median_overpay_vs_runner_up"] is not None:
        L += ["", f"Winners typically beat the runner-up bid by **${m['median_overpay_vs_runner_up']}** (median)."]
    L += ["", "## Biggest claims", "", "| Wk | Player | Pos | Team | Bid | Runner-up |", "|---|---|---|---|---|---|"]
    for c in m["top_claims"]:
        L.append(f"| {c['week']} | {c['player']} ({c['nfl_team']}) | {c['position']} | {c['team']} | ${c['winning_bid']} | "
                 f"{'$%s' % c['runner_up_bid'] if c['runner_up_bid'] is not None else '—'} |")
    j = m["james"]
    L += ["", f"James: won {j['won']} claim(s) for ${j['spent']}; lost {len(j['lost_claims'])}."]
    for lc in j["lost_claims"]:
        L.append(f"- Week {lc['week']}: {lc['player']} at ${lc['bid']} ({lc['status']})")
    return "\n".join(L) + "\n"


def main() -> int:
    m = build()
    (ROOT / "intelligence" / "faab_market.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    md = to_markdown(m)
    (ROOT / "intelligence" / "faab_market.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
