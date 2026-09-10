# Mandatory repository rules

This database is the source of truth. Integrity outranks an immediate recommendation.

1. Mongo and Sparta are separate league namespaces. Every league-dependent query and mutation must require a league.
2. Never infer `FREE_AGENT_CONFIRMED` from an article, ranking, projection, low roster percentage, undrafted status, absence of an ownership row, or "not on James's roster." Use `UNKNOWN`.
3. Only ownership-authoritative evidence may change ownership: draft results, completed transactions, platform ownership/roster evidence, current roster screenshots, waiver results, trades, or explicit user corrections.
4. News and player-status evidence may affect evaluation and waiver priority, never ownership.
5. Never recommend a currently rostered player as a pickup. Before actionable waiver advice, query league-specific ownership.
6. Preserve immutable ownership and transaction history. Never erase a prior draft, drop, or other event to make current state fit.
7. Later authoritative observations normally supersede older ones. At equal/ambiguous times use: manual correction; confirmed transaction/waiver result; platform current ownership; current roster screenshot; other ownership snapshot; draft.
8. Explicit override is exceptional, auditable, and must retain the conflicting evidence.
9. Never fabricate dates, prices, ownership, teams, transactions, or FAAB. Known current state with missing history requires a reconciliation issue.
10. Every material current-state claim requires provenance and must be explainable by history.
11. Completed user transaction language is authoritative evidence of the resulting ownership. Proposed language ("should I add") is not.
12. A dropped player is not still rostered unless a later authoritative event reacquires him. A drop also does not prove current free agency.
13. Run `ffdb validate --league <slug>` after mutations and back up before risky imports or reconciliation.
14. Tests use temporary databases only; never point pytest at `data/fantasy.db`.
15. Mongo and Sparta may both be seeded, but their ownership, roster, lineup, transaction, FAAB, waiver, and recommendation state must remain completely isolated. Shared NFL player identity is allowed; shared league state is not.
16. Sparta's Aug. 30, 2026 draft board is authoritative historical ownership evidence once imported. Until the complete 2026 board is present, unresolved candidates remain `UNKNOWN` unless later authoritative evidence confirms ownership or availability.
17. Never substitute older Sparta draft-history spreadsheets for the Aug. 30, 2026 board.

Natural-language completed add/drop workflow: query current state; validate the drop; treat the user's completed add as authoritative even if prior ownership was unknown; append one grouped transaction; add FAAB debit when known; rebuild current state; validate; report roster, balance, and provenance. For proposed pickups, stop at `UNKNOWN` until availability is verified.

## Required repository update loop

For every substantive fantasy update in any chat:

1. Read the current repository state for the specified league.
2. Analyze the proposed or completed update.
3. Validate league scope, ownership prerequisites, and data integrity.
4. Write only an authoritative completed change; never persist a contemplated move.
5. Commit the change to GitHub with a descriptive message.
6. Read the committed values back from GitHub and compare them with the intended write.
7. Report success only after exact read-back verification, including the commit SHA. If any write, commit, or read-back step fails, report the failure explicitly.

The repository overrides conflicting chat history or memory. Chat context may help locate evidence but cannot silently overwrite committed league facts.
