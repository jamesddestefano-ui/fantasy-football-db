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

## ESPN live activity correction (2026-09-12)

Authenticated ESPN activity (`/workspace/espn-live-transactions.json`) corrected Sep 3 history:

- Kaelon Black was **ADD + DROP Ja'Kobi Lane** (not a bare free add)
- Tre Tucker was **ADD + DROP Nicholas Singleton** (not a bare free add)
- Lane drop on Sep 3 then re-add on Sep 8 (Boutte drop) is coherent; end roster still 17
- Malik BN→IR remains a **user-confirmation** `IR_MOVE` — ESPN activity filter did not show a Moved/IR row; do not invent an ESPN IR transaction

## Semantic dedupe safety (Mongo only)

`ffdb.dedupe` classifies inbound ESPN/import events before append:

- Semantic key: `mongo` + team + normalized type family + added/dropped player keys + `calendar_day_ET`
- Type family mapping collapses `FREE_AGENT_ADD+DROP` / `ADD_DROP` / seed `DROP+FREE_AGENT_ADD` → `ADD_DROP`
- Player keys use `normalize_name` + `PlayerAlias` (Ja'Kobi↔Jakobi, Eagles D/ST↔Eagles, De'Von↔Devon)
- Match → `ALREADY_RECORDED` (no write); uncertain → `UNCERTAIN` / INGESTION HELD; else `NEW`

Dry check: `ffdb ingest-dry-run --league mongo` or `pytest tests/test_dedupe.py`. Routine auto-ingest stays disabled until the parent enables it.

