# Fantasy Football DB

An event-history-first, auditable source of truth for James's 2026 fantasy leagues. Mongo and Billy's Sparta league share a canonical NFL player universe while keeping all league-dependent state completely isolated.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
ffdb init
pytest
```

The production database defaults to `data/fantasy.db`; set `FFDB_DATABASE_URL` to migrate later to PostgreSQL. SQLite foreign keys are enabled on every connection.

## Everyday commands

```bash
ffdb roster show --league mongo
ffdb roster show --league sparta
ffdb player ownership "Dylan Sampson" --league sparta
ffdb player history "Ja'Kobi Lane" --league sparta
ffdb faab show --league sparta
ffdb transaction add-drop --league sparta --team mine --drop "Player A" --add "Player B" --faab 0
ffdb waiver-watch show --league sparta
ffdb reconcile --league sparta
ffdb validate --league sparta
ffdb rebuild-state --league sparta
ffdb backup
ffdb export --league sparta
```

A completed transaction statement is evidence of the resulting ownership; a proposed pickup is not. Before a recommendation, query ownership and distinguish `OWNED`, `FREE_AGENT_CONFIRMED`, `WAIVERS_CONFIRMED`, and `UNKNOWN`. See `AGENTS.md` for mandatory behavior.

## Current seeds

### Mongo

The September 10, 2026 user confirmation seeds the current Mongo roster, Week 1 lineup snapshot, and a $94 FAAB balance checkpoint. It does not fabricate missing historical acquisition records; reconciliation issues record gaps.

### Sparta

The Sparta seed currently stores the user-confirmed current roster through Sept. 9, 2026, a $100 real-money FAAB opening checkpoint, and known ownership corrections that block false free-agent recommendations. It explicitly records reconciliation issues for the still-missing complete Aug. 30, 2026 draft-board import and any missing transaction links between the draft and current roster.

The current Sparta seed intentionally does **not** treat absence from the database as free agency. The complete Aug. 30, 2026 board must be imported before broad availability can be trusted from draft evidence alone.

## League isolation

Every ownership, roster, transaction, lineup, FAAB, waiver-watch, and recommendation query must carry a league namespace. A player may be owned by James in Mongo, owned by another manager in Sparta, or have different availability states in each league without conflict.

## Backup and restore

`ffdb backup` creates a timestamped SQLite copy in `data/backups/` before risky imports. Restore while no writer is active by copying the selected backup over `data/fantasy.db`; validate immediately afterward. Backups and exports are ignored by Git.
