# Prime Mongo measurable learning loop

This directory is exclusively for Prime Mongo Fantasy Watch decisions and outcomes. It must never contain Sparta, DFS or prop-betting decisions or metrics.

## Durable artifacts

- `decision_ledger.jsonl`: append-only event ledger. `DECISION` captures the recommendation exactly as known before the deadline; `REVIEW` appends outcomes and lessons later.
- `season_scorecard.json`: regenerable cumulative Mongo scorecard.
- `weekly_reviews/`: one review after each NFL week.
- `rules/learning_rules_vN.json`: immutable, versioned operating-rule changes.

Pulse lineage is stored only when an NFL Pulse item was considered in a material Mongo decision. Store the Pulse ID and one canonical `pulse_information_event_id`; never copy the Pulse database into this directory. Repeated reports of the same NFL fact share the same information-event ID so they are not counted as independent evidence. Authenticated ESPN remains authoritative for ownership, availability, transactions, FAAB, IR and lineup state.

## Operating loop

1. Read current Mongo repository and authenticated ESPN state.
2. Before the deadline, append each material recommendation with all required fields.
3. Preserve ownership/FAAB/lineup authority boundaries. Pulse and external sources are signals only.
4. After the result is known, append a separate review with outcome and process grades.
5. Rebuild the scorecard and signal metrics from the event ledger.
6. Propose rule changes during the weekly review; adopt changes only in a new versioned rules file.

Do not backfill a recommendation that was not actually made. Historical enrichment may document context, but it is not a contemporaneous decision.
