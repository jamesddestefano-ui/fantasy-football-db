# Data model

Global `nfl_players` are identity only. All ownership truth is keyed by `league_id`: immutable `ownership_events` feed rebuildable `current_ownership`; `transaction_groups` atomically collect transaction events; draft picks remain opening history; FAAB uses immutable entries plus authoritative balance observations; lineups remain distinct from rosters. Sources support every material assertion. News/status tables cannot participate in ownership replay. Waiver watch belongs to the decision layer. Reconciliation issues preserve missing or conflicting evidence.

