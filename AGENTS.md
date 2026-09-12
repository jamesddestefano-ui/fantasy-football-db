# Mandatory repository rules

This repository is the source of truth for Mongo only. Integrity outranks an immediate recommendation.

1. This repository contains only Mongo league data. Never add or import another fantasy league's roster, ownership, transactions, FAAB, lineup, waiver, draft, or recommendation state.
2. Every league-dependent query and mutation must explicitly use the `mongo` league.
3. Never infer `FREE_AGENT_CONFIRMED` from an article, ranking, projection, low roster percentage, undrafted status, absence of an ownership row, or "not on James's roster." Use `UNKNOWN`.
4. Only ownership-authoritative evidence may change ownership: draft results, completed transactions, ESPN ownership/roster evidence, current roster screenshots, waiver results, trades, or explicit user corrections.
5. News and player-status evidence may affect evaluation and waiver priority, never ownership.
6. Never recommend a currently rostered player as a pickup. Before actionable waiver advice, query Mongo-specific ownership.
7. Preserve immutable ownership and transaction history. Never erase a prior draft, drop, or other event to make current state fit.
8. Later authoritative observations normally supersede older ones. At equal or ambiguous times use: manual correction; confirmed transaction/waiver result; ESPN current ownership; current roster screenshot; other ownership snapshot; draft.
9. Explicit override is exceptional, auditable, and must retain the conflicting evidence.
10. Never fabricate dates, prices, ownership, teams, transactions, or FAAB. Known current state with missing history requires a reconciliation issue.
11. Every material current-state claim requires provenance and must be explainable by history.
12. Completed user transaction language is authoritative evidence of the resulting ownership. Proposed language such as "should I add" is not.
13. A dropped player is not still rostered unless a later authoritative event reacquires him. A drop also does not prove current free agency.
14. Run `ffdb validate --league mongo` after mutations and back up before risky imports or reconciliation.
15. Tests use temporary databases only; never point pytest at `data/fantasy.db`.

Natural-language completed add/drop workflow: query current Mongo state; validate the drop; treat the user's completed add as authoritative even if prior ownership was unknown; append one grouped transaction; add the FAAB debit when known; rebuild current state; validate; report roster, balance, and provenance. For proposed pickups, stop at `UNKNOWN` until availability is verified.

## Required repository update loop

For every substantive fantasy update in any chat:

1. Read the current Mongo repository state.
2. Analyze the proposed or completed update.
3. Validate league identity, ownership prerequisites, and data integrity.
4. Write only an authoritative completed change; never persist a contemplated move.
5. Commit the change to GitHub with a descriptive message.
6. Read the committed values back from GitHub and compare them with the intended write.
7. Report success only after exact read-back verification, including the commit SHA. If any write, commit, or read-back step fails, report the failure explicitly.

The repository overrides conflicting chat history or memory. Chat context may help locate evidence but cannot silently overwrite committed Mongo facts.


## Measurable decision learning loop

Prime Mongo Fantasy Watch uses the append-only learning layer under `learning/`.

1. Record every material Mongo recommendation before its deadline in `learning/decision_ledger.jsonl` with contemporaneous evidence, confidence (1–5), urgency, risks and alternatives.
2. A `DECISION` event is immutable. Never edit it after the result. Append a separate `REVIEW` event with outcome grade, process grade, errors, lesson and any proposed rule adjustment.
3. Do not fabricate or backfill a recommendation that was not actually made. News without a material recommendation is not a decision-ledger entry.
4. Ground Mongo ownership and availability in authenticated ESPN state. Grok Pulse, articles, projections, experts and news are intelligence signals only.
5. Keep Mongo decisions and metrics isolated. Never store Sparta, DFS or prop decisions in this repository.
6. Rebuild cumulative metrics from the ledger and produce one weekly review after each NFL week.
7. Adopt a learning-rule change only in a new versioned file under `learning/rules/`; preserve all earlier rule versions.
8. Do not change signal weights because of one ordinary result. Require repeated evidence unless a clear structural defect is exposed.
