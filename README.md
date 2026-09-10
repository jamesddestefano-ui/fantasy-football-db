# Mongo Fantasy Football DB

An event-history-first, auditable source of truth for James's 2026 Mongo ESPN Mangarelli Auction League. This repository contains Mongo data only. Data from any other fantasy league belongs in a separate repository and must never be imported here.

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
ffdb player ownership "Kendre Miller" --league mongo
ffdb player history "Ja'Kobi Lane" --league mongo
ffdb lineup show --league mongo --week 1
ffdb faab show --league mongo
ffdb transaction add-drop --league mongo --team mine --drop "Kendre Miller" --add "Player X" --faab 4
ffdb waiver-watch show --league mongo
ffdb reconcile --league mongo
ffdb validate --league mongo
ffdb rebuild-state --league mongo
ffdb backup
ffdb export --league mongo
```

A completed transaction statement is evidence of the resulting ownership; a proposed pickup is not. Before a recommendation, query Mongo ownership and distinguish `OWNED`, `FREE_AGENT_CONFIRMED`, `WAIVERS_CONFIRMED`, and `UNKNOWN`. See `AGENTS.md` for mandatory behavior.

## Current seed

The September 10, 2026 user confirmation seeds the current Mongo roster, Week 1 lineup snapshot, and a $94 FAAB balance checkpoint. It does not fabricate missing historical acquisition records; reconciliation issues preserve those gaps.

## Backup and restore

`ffdb backup` creates a timestamped SQLite copy in `data/backups/` before risky imports. Restore while no writer is active by copying the selected backup over `data/fantasy.db`; validate immediately afterward. Backups and exports are ignored by Git.
