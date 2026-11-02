# Mongo reconciliation — NEEDS_INGEST

ESPN 2026-11-02T20:43:55Z vs repository (newest import 2026-10-28T08:11:00Z). Transactions checked: 276.

## Completed on ESPN, not in the repository

- 2026-10-28T12:31:48Z FREEAGENT +Mason Taylor, -J.J. McCarthy
- 2026-10-28T12:32:32Z FREEAGENT +Geno Smith
- 2026-11-01T04:03:57Z FREEAGENT +Malik Willis, -Bam Knight

## Roster differences

- On ESPN, not in repo: Geno Smith, Malik Willis, Mason Taylor
- In repo, not on ESPN: Bam Knight, J.J. McCarthy, Kyler Murray

FAAB: ESPN $54 · repository $54.0

Codex: ingest the drafts in intelligence/reconcile/pending/ (Mongo Live Check workflow).
