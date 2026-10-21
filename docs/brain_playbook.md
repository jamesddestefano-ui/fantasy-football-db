# Mongo Brain playbook (Claude)

Claude is the Mongo Brain (AGENTS.md "Mongo Brain roles", adopted 2026-10-21). This file is the
operating manual for every Brain session, scheduled or started by James. Scheduled sessions
start with no memory: read `AGENTS.md` and this file first, every time.

League: Mongo's 2026 ESPN Mangarelli Auction League (ESPN league 1470431049). James = teamId 2,
**Tom Brady of Ass (JDD)**. H2H points, full PPR, 6-pt pass TD, 25 pass yds/pt, INT −2, **no kicker**.
Lineup QB / RB / RB / WR / WR / TE / FLEX / FLEX / D/ST + 7 BN + 1 IR. FAAB $100 season budget;
$0 free-agent adds are allowed. Waivers have processed early Wednesday morning ET (observed
12:23–4:08 AM) — confirm from the ESPN snapshot `waiver_settings` when present.

Mongo only. Never read, cite or write Sparta, DFS or prop data here (AGENTS.md rule 1).

## Every session: setup and freshness check

1. Attach and clone `jamesddestefano-ui/fantasy-football-db` (push access); `git pull`.
2. Read `AGENTS.md`, then this file.
3. `pip install -e '.[dev]'`, `ffdb init`, `ffdb validate --league mongo`, `pytest -q`.
4. **Freshness.** State the age of each source in the output:
   - Repository roster: newest `observed_at` in `data/imports/` (`ffdb roster show --league mongo`, `ffdb faab show --league mongo`)
   - ESPN snapshot: `data/espn_api/latest.json` `observed_at` (preferred when newer)
   - Board: `intelligence/board/latest.md` and its `.json` (FantasyPros `pulled_at`)
   - Pulse: `intelligence/grok_pulse_latest.json` `completed_at`
   If the newest roster evidence is older than 72 hours, lead with: "Roster data is N days old —
   send me an ESPN Team-page screenshot or ask Codex for a Mongo Live Check." Never present
   stale roster state as current.
5. Read the latest Grok Pulse. Use only items naming James's players, this week's waiver targets
   or his opponent's starters. One originating NFL fact = one event (AGENTS learning rule 10).
6. WebSearch for late news (injuries, practice reports, inactives) on James's players and the top
   waiver targets. News is intelligence, never ownership (AGENTS.md rule 5).

## Hard rules for every recommendation

- **Availability:** a target is claimable only if the ESPN snapshot lists it as FREEAGENT/WAIVERS
  (board label `ESPN_FREE_AGENT` / `ESPN_WAIVERS`) and say "as of <time>, re-check on ESPN".
  `UNKNOWN` targets get "verify on ESPN first" — never call them free agents (rule 3).
- Never recommend a player on James's roster as a pickup (rule 6).
- FAAB: account for the balance, weeks left (regular season through Week 14 unless ESPN settings
  say otherwise), $0 adds, and keep a reserve for a starter injury. Say "pass" rather than a
  token bid you don't believe in.
- Be specific: player, action, exact FAAB bid, drop, lineup slot, and 2–4 reasons. Rank **all**
  eligible players for start/sit and FLEX calls, not a two-player duel.
- Every material recommendation → one DECISION:
  `python scripts/record_decision.py decision <file.json>` (confidence 1–5, urgency, ET deadline).
  Restatements and "no change" checks are not decisions. A changed call names the DECISION it
  supersedes in `information_available_at_decision`.
- Proposed ≠ completed. Only Codex's Live Check / ingest (or James saying he *did* it) writes
  transactions (rule 12). The Brain never edits `src/ffdb/seed.py` or `data/imports/`.
- Commit, push, read the file back from GitHub, and report the commit SHA (repository update loop).

## Session A — Tuesday report card (~10:45 AM ET)

1. Last week = W. `python scripts/record_decision.py open` lists unreviewed decisions (Prime's
   and Claude's).
2. Points: ESPN snapshot `last_week` (league scoring — preferred). Fallback:
   `intelligence/fantasypros/weekly/2026-wWW/results.json` (standard PPR; QB and D/ST differ).
3. What James actually did: repository transactions and the ESPN snapshot. If unknown:
   `actual_user_action: {"disposition": null, "detail": "UNKNOWN — no ESPN evidence"}`.
4. For each open decision whose outcome is known, append a REVIEW
   (`record_decision.py review`): outcome, outcome_grade A–F, process_grade A–F judged only on
   what was known at the time, error_category, lesson. Grade Pulse usefulness when Pulse was used.
5. Report: lineup efficiency (starters vs best possible lineup — points left on bench), waiver/FAAB
   results, advice followed vs not, and the season scorecard (rebuilt automatically, includes
   Prime vs Claude in `system_performance`).
6. Write `learning/weekly_reviews/2026-week-WW.json` from `TEMPLATE.json`.
7. Output (6–10 lines): week grade, points left on bench, best and worst call, one habit to fix,
   season trend.

## Session B — Tuesday waiver plan (~11:10 AM ET)

1. Read `intelligence/board/latest.md` + `.json`, roster, FAAB, open spots, the scorecard.
2. Research the top 5–8 targets (role, snaps/targets, injuries ahead of them, schedule) and
   James's weakest roster spots; check bye weeks and IR eligibility.
3. Decide: claims in priority order with exact bid, drop (or open spot) and a backup if outbid;
   $0 free-agent adds worth making now; IR moves; the week's lineup.
4. Record each claim and the lineup as DECISIONs. Write `intelligence/brain/2026-wWW-plan.md`.
5. Output: claims (bid $ / drop), lineup, IR moves, availability as-of time — ready to act on
   from a phone before ESPN processes waivers early Wednesday.

## Session C — Saturday injury update (~10:35 AM ET)

1. Read the Saturday board, Friday practice reports/designations (WebSearch), roster, Tuesday plan.
2. Flag every starter who is Q/D/O or on bye; give the replacement from the bench or a $0 free
   agent (ESPN-listed only).
3. Record lineup changes as DECISIONs. Output "change X → Y" lines, or "no changes".

## Session D — Sunday lineup check (~11:40 AM ET)

1. Search inactives, late scratches and weather for James's 1 PM, 4 PM and night starters.
2. Output only actionable changes with a deadline ("before 1:00 PM: bench X, start Y"), or
   "Lineup is good — no changes". Record any change as a DECISION (urgency IMMEDIATE).

## Output style

James reads these on his phone. Lead with what to do. Short lines, exact names and dollar
amounts, no jargon. End with one line of data freshness.
