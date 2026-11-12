# Mongo reconciliation — NEEDS_INGEST

ESPN 2026-11-12T18:51:02Z vs repository (newest import 2026-10-28T08:11:00Z). Transactions checked: 333.

## Completed on ESPN, not in the repository

- 2026-10-28T12:31:48Z FREEAGENT +Mason Taylor, -J.J. McCarthy
- 2026-10-28T12:32:32Z FREEAGENT +Geno Smith
- 2026-11-01T04:03:57Z FREEAGENT +Malik Willis, -Bam Knight
- 2026-11-04T08:59:02Z WAIVER +Greg Dulcich, -Geno Smith ($3)
- 2026-11-04T08:59:02Z WAIVER +Saints D/ST, -Commanders D/ST ($3)
- 2026-11-11T08:51:38Z WAIVER +Darren Waller, -Keaton Mitchell ($1)
- 2026-11-11T08:51:38Z WAIVER +Packers D/ST, -Saints D/ST ($3)
- 2026-11-11T08:51:38Z WAIVER +Fernando Mendoza, -Mason Taylor ($10)
- 2026-11-11T08:51:38Z WAIVER +Aaron Rodgers ($2)
- 2026-11-11T08:51:38Z WAIVER +Pat Freiermuth, -Kendre Miller ($1)
- 2026-11-12T02:12:39Z FREEAGENT +Roschon Johnson, -Darren Waller

## Roster differences

- On ESPN, not in repo: Aaron Rodgers, Fernando Mendoza, Greg Dulcich, Packers D/ST, Pat Freiermuth, Roschon Johnson
- In repo, not on ESPN: Bam Knight, Commanders D/ST, J.J. McCarthy, Keaton Mitchell, Kendre Miller, Kyler Murray

FAAB: ESPN $31 · repository $54.0

Codex: ingest the drafts in intelligence/reconcile/pending/ (Mongo Live Check workflow).
