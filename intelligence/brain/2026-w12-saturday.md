# Mongo Brain — Week 12 Saturday injury update (2026-11-28 ~10:30 AM ET)

Tom Brady of Ass (JDD), 4-7, vs Bills Mafia (8-3). ESPN 123.89 vs 145.61 with current slots — underdog, prefer upside.
Roster and slots from `data/espn_api/latest.json` (2026-11-27T19:53Z). FAAB $27. Roster 16/16, IR empty. No byes.

**New DECISION:** `mongo-2026-w12-mcmillan-contingency-001` (McMillan foot, MNF).
The RB fix below restates `mongo-2026-w12-add-watson-fa-001` (not re-logged, rule 011).

## Changes for James (ESPN slots as of Fri snapshot)

1. **RB: Kaelon Black → Dylan Sampson** (CLE vs LV, SNF). ESPN 11.56 vs 6.41; Sampson not on the Browns report; Black 6 carries last week. Before 4:25 PM ET Sun (Black's kickoff).
2. **McMillan contingency (Mon):** start him. Only if Carolina rules him OUT/DOUBTFUL: $0 add **Tez Johnson** (TB WR, FREEAGENT, 6.43, plays MNF), drop Packers D/ST (already played), start Johnson. No bench WR is still unplayed.

## Starter check (Friday Nov 27 final reports)

| Slot | Player | Game | Status |
|---|---|---|---|
| QB | Deshaun Watson | CLE vs LV, SNF | Not on report |
| RB | Bijan Robinson | ATL at MIN 1 PM | Not on report |
| RB | Kaelon Black → **Dylan Sampson** | SF vs SEA 4:25 / CLE vs LV SNF | Neither on report |
| WR | CeeDee Lamb | played Thu | — |
| WR | Tetairoa McMillan | CAR at TB, Mon | Foot: est. DNP Thu, limited Fri, Canales optimistic; designation pending |
| TE | Chig Okonkwo | WAS at ARI | Not on report |
| FLEX | Luther Burden III | played Thu | — |
| FLEX | Ryan Flournoy | played Thu | — |
| D/ST | Jets | at MIA | Jets DL Onyemata, Phillips, Sweat Q |

RB rank (unplayed, ESPN): Bijan 18.86, Sampson 11.56, Ekeler 9.24, Black 6.41.
QB: Watson 24.12 > Mendoza 19.73 > Darnold 15.76 (Darnold confirmed starting at SF; Purdy OUT).

## Sunday watch

- Browns RB: Raheim Sanders (hip) Q, returning — could trim Sampson/Judkins work.
- Jets D/ST: three DL questionable; no change unless two are out (Patriots D/ST 8.24 is FREEAGENT).
- McMillan: Carolina designations Saturday; inactives ~6:45 PM ET Monday.
- Opponent: Denzel Boston (CLE, Bills Mafia FLEX) Q, DNP all week; McCaffrey no designation; Purdy OUT doesn't touch their lineup.

## Freshness

- ESPN snapshot 2026-11-27 19:53Z (~19.5h). Today's 7:07 AM daily pull and the Saturday 9:23 AM board have not landed on main; board is Tuesday's (2026-11-24).
- Repository roster: newest import 2026-10-28 (31 days); reconcile NEEDS_INGEST (16 moves). Advice uses ESPN state.
- Grok Pulse 2026-11-28 09:19Z (McMillan foot).

Sources: NFL.com Week 12 injury report 2026; CBS Sports Week 12 injury report (2026-11-27); ClevelandBrowns.com final report (2026-11-27); Seahawks.com Week 12 report (2026-11-27); Commanders.com game status (2026-11-27); SI Commanders-Cardinals final report (2026-11-27); FantasyPros Week 12 pickups (2026-11-28); iHeart Kaelon Black preview (2026-11-28); Grok Pulse.
