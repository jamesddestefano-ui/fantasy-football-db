# JDD (Tom Brady of Ass) Week 10 read — Fantasy Points data through Week 9 (+ TNF)

_Mongo Brain read 2026-11-13 ~8:45 PM ET. Roster and slots from ESPN snapshot `data/espn_api/2026-11-13T1829Z.json`
(1:29 PM ET; week 10 vs Joe's Finest Team 7-2, proj 118.97 vs 116.34). Rank 1 = defense that allows the most._

| Player | Pos | Opp | FP/G last 4 | XFP/G last 4 | Opp FP/G allowed to pos, season (rank) | Same, last 4 (rank) |
|---|---|---|---|---|---|---|
| Bijan Robinson | RB | KC | 14.7 | 14.6 | 19.5 (28) | 19.4 (23) |
| CeeDee Lamb | WR | SF | 21.9 | 22.8 | 27.4 (28) | 27.3 (23) |
| Tetairoa McMillan | WR | NO | 12.5 | 13.7 | 31.5 (23) | 33.6 (9) |
| Luther Burden III | WR | bye | — | — | — | — |
| Josh Downs | WR | MIA | 7.5 | 10.5 | 25.7 (30) | 29.2 (17) |
| Dylan Sampson | RB | HST | 10.5 | 9.2 | 22.0 (20) | 27.1 (4) |
| Kaelon Black | RB | DAL | 6.3 | 7.4 | 26.1 (2) | 26.9 (5) |
| Ryan Flournoy | WR | SF | 12.1 | 10.1 | 27.4 (28) | 27.3 (23) |
| Chig Okonkwo | TE | NYG | 9.1 | 9.8 | 13.0 (17) | 11.5 (22) |
| Sam Darnold (out W10) | QB | LV | 14.2 | 15.8 | 21.4 (1) | 20.4 (4) |
| Greg Dulcich | TE | IND | 8.8 | 9.0 | 14.4 (12) | 12.4 (19) |
| Fernando Mendoza | QB | SEA | 2.2 | 3.6 | 11.4 (31) | 8.1 (31) |
| Aaron Rodgers | QB | CIN | 14.5 | 14.2 | 18.5 (18) | 19.9 (8) |
| Pat Freiermuth | TE | CIN | 10.1 | 8.7 | 16.0 (13) | 13.9 (16) |
| Roschon Johnson | RB | bye | 7.4 | 7.9 | — | — |
| Drew Lock (free agent) | QB | LV | 15.6 | 12.2 | 21.4 (1) | 20.4 (4) |

## What this changes or confirms

1. **QB: add Drew Lock and start him over Rodgers** (ledger mongo-2026-w10-fa-lock-001). The Tuesday Lock claim
   did not win; Rodgers (the backup claim) did. Lock is now an ESPN free agent. LV allows the most QB points
   (21.4 FP/G, rank 1); CIN is 18th (8th over the last 4). Lock 15.6 FP/G over 3 games vs Rodgers 14.5; Rodgers has
   the higher XFP (14.2 vs 12.2), so the edge is the matchup. Drop Mendoza (first start vs SEA, fewest QB points
   allowed). Darnold returns Week 12; keep him.
2. **RB2: the ESPN lineup starts Kaelon Black with Sampson on the bench.** The recorded lineup decision
   (mongo-2026-w10-lineup-001) is Sampson. Sampson's usage is higher (9.2 XFP/G vs 7.4) and HOU has allowed the 4th-most
   RB points over the last 4. Black's DAL matchup is good too (rank 2), so this is not lopsided, but the data supports
   the recorded plan.
3. TE: Okonkwo's Thursday game is done; Freiermuth (CIN, rank 13) is the TE. No change.
