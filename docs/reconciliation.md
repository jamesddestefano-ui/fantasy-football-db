# Reconciliation

Reconciliation never invents history. Reports surface confirmed ownership/availability, unknowns, conflicting evidence, missing transactions, ambiguous identities, FAAB and roster discrepancies, lineup conflicts, and staleness. Each conflict retains competing source IDs, dates, the winning rule, and whether confirmation is required.

## Mongo baseline (2026)

Resolved from authenticated ESPN evidence (leagueId `1470431049`, teamId `2`):

- FAAB opening budget `$100` and the `$6` Jacob Saylors waiver claim that explain remaining `$94`
- Historical adds/drops: Saylors waiver; Kaelon Black and Tre Tucker free adds (Sep 3 ET); Ja'Kobi Lane add / Kayshon Boutte drop; Malik Davis add / Jacob Saylors drop (Sep 8 ET)
- Scoring INT `-2`, no kicker, roster slots `1QB 2RB 2WR 1TE 2FLEX 1D/ST 7BN 1IR`
- ESPN league/team IDs stored in `leagues.settings` (`espn_league_id`, `espn_team_id`)

Still open / held:

- `MISSING_DRAFT_DATA` — complete auction results and prices were not in ESPN evidence
- `MISSING_PLAYER_ESPN_IDS` — `nfl_players.espn_id` held; do not invent numeric IDs
- Boutte original acquisition date/method remains unknown (only the Sep 8 drop is evidenced)
