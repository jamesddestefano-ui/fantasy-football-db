# Mongo reconciliation — NEEDS_INGEST

ESPN 2026-10-22T22:27:33Z vs repository (newest import 2026-10-21T15:17:00Z). Transactions checked: 241.

## Completed on ESPN, not in the repository

- 2026-10-22T22:13:59Z FREEAGENT +Browns D/ST, -Saints D/ST
- 2026-10-22T22:15:37Z FREEAGENT +Bam Knight, -Audric Estime
- 2026-10-22T22:26:17Z FREEAGENT +Dontayvion Wicks, -Jaleel McLaughlin
- 2026-10-22T22:26:31Z FREEAGENT +Juwan Johnson, -Jacob Cowing

## Roster differences

- On ESPN, not in repo: Bam Knight, Browns D/ST, Dontayvion Wicks, Juwan Johnson
- In repo, not on ESPN: Audric Estime, Jacob Cowing, Jaleel McLaughlin, Saints D/ST

FAAB: ESPN $66 · repository $66.0

Codex: ingest the drafts in intelligence/reconcile/pending/ (Mongo Live Check workflow).
