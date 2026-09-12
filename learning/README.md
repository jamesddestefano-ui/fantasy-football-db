# Prime Mongo measurable learning loop

This directory is exclusively for Prime Mongo Fantasy Watch decisions and outcomes. It must never contain Sparta, DFS or prop-betting decisions or metrics.

## Durable artifacts

- `decision_ledger.jsonl`: append-only event ledger. `DECISION` captures the recommendation exactly as known before the deadline; `REVIEW` appends outcomes and lessons later.
- `season_scorecard.json`: regenerable cumulative Mongo scorecard.
- `weekly_reviews/`: one review after each NFL week.
- `rules/learning_rules_vN.json`: immutable, versioned operating-rule changes.

## Operating loop

1. Read current Mongo repository and authenticated ESPN state.
2. Before the deadline, append each material recommendation with all required fields.
3. Preserve ownership/FAAB/lineup authority boundaries. Pulse and external sources are signals only.
4. After the result is known, append a separate review with outcome and process grades.
5. Rebuild the scorecard and signal metrics from the event ledger.
6. Propose rule changes during the weekly review; adopt changes only in a new versioned rules file.

## NFL Pulse lineage

NFL Pulse is an approved intelligence input, not a command or ownership authority. When it materially informs a decision, the immutable `DECISION` event records the Pulse ID, detection time, category, fact confidence, urgency, relevance, lead time and whether it changed, confirmed, created or conflicted with the Mongo thesis. Repeated reporting of the same underlying NFL fact counts as one signal.

After the outcome, the `REVIEW` event grades Pulse usefulness separately and records whether Pulse was early, improved the decision, prevented a mistake, arrived too late or was misleading. Pulse fact confidence and Mongo decision confidence must remain separate.

Do not backfill a recommendation that was not actually made. Historical enrichment may document context, but it is not a contemporaneous decision.
