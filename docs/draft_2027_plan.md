# Mongo 2027 auction plan

Mongo is a **redraft** $200 auction league (James confirmed 2026-10-22): no keepers. Everything that
carries into 2027 is evidence and lessons. All of it is Mongo-only (AGENTS.md rule 1).

## Collected automatically during 2026

| What | Where | Refreshed |
|---|---|---|
| 2026 auction: every player, price, buyer, nominator | `data/espn_api/draft_2026.json` | daily (prices fixed; points update) |
| Price vs production, best/worst buys, each manager's spending profile | `intelligence/draft/2026_auction_review.md` | daily |
| In-season FAAB behaviour by manager | `intelligence/faab_market.md` | daily |
| Graded decisions and lessons | `learning/` | weekly |

## Checkpoints

1. **After Week 17 (early Jan 2027):** season review — final points per $ by position and price tier,
   which manager styles won, James's best/worst buys, waiver vs draft contribution to his points.
   Write the lessons to `learning/rules/` as `2027-auction-strategy-notes.md` (versioned, never edited later).
2. **Summer 2027 (July):** season rollover (scripts' `SEASON`, new `data/espn_api/` season files,
   2027 league settings), then a 2027 draft board: projections converted to Mongo dollars using
   2026 spending patterns, target prices, avoid list, manager tendencies.
3. **Draft day:** live tracker — each team's money left and max bid, open roster slots, nominations,
   suggested max bid for James on every nominated player.
