# Mongo reconciliation — NEEDS_INGEST

ESPN 2026-11-05T18:41:12Z vs repository (newest import 2026-10-28T08:11:00Z). Transactions checked: 300.

## Completed on ESPN, not in the repository

- 2026-10-28T12:31:48Z FREEAGENT +Mason Taylor, -J.J. McCarthy
- 2026-10-28T12:32:32Z FREEAGENT +Geno Smith
- 2026-11-01T04:03:57Z FREEAGENT +Malik Willis, -Bam Knight
- 2026-11-04T08:59:02Z WAIVER +Greg Dulcich, -Geno Smith ($3)
- 2026-11-04T08:59:02Z WAIVER +Saints D/ST, -Commanders D/ST ($3)

## Roster differences

- On ESPN, not in repo: Greg Dulcich, Malik Willis, Mason Taylor, Saints D/ST
- In repo, not on ESPN: Bam Knight, Commanders D/ST, J.J. McCarthy, Kyler Murray

FAAB: ESPN $48 · repository $54.0

Codex: ingest the drafts in intelligence/reconcile/pending/ (Mongo Live Check workflow).
