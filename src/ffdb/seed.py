from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (Authority, FaabBalanceObservation, FantasyTeam, League, LineupAssignment,
    Manager, NFLPlayer, OwnershipEvent, OwnershipState, ReconciliationIssue, Source)
from .names import normalize_name
from .services import rebuild_state

AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ROSTER = [
    ("Jalen Hurts", "QB", "QB", "STARTER"), ("De'Von Achane", "RB", "RB", "STARTER"),
    ("Bijan Robinson", "RB", "RB", "STARTER"), ("Luther Burden III", "WR", "WR", "STARTER"),
    ("Tetairoa McMillan", "WR", "WR", "STARTER"), ("Mark Andrews", "TE", "TE", "STARTER"),
    ("Josh Downs", "WR", "FLEX", "STARTER"), ("CeeDee Lamb", "WR", "FLEX", "STARTER"),
    ("Eagles D/ST", "D/ST", "D/ST", "STARTER"), ("Kaelon Black", "RB", "BN", "BENCH"),
    ("Ray Davis", "RB", "BN", "BENCH"), ("Malik Davis", "RB", "BN", "BENCH"),
    ("Ja'Kobi Lane", "WR", "BN", "BENCH"), ("Kendre Miller", "RB", "BN", "BENCH"),
    ("Dylan Sampson", "RB", "BN", "BENCH"), ("Tre Tucker", "WR", "BN", "BENCH"),
]
NOT_MINE_UNKNOWN = [("Browns D/ST", "D/ST"), ("Nicholas Singleton", "RB"), ("Kayshon Boutte", "WR"), ("Jacob Saylors", "RB")]


def seed_mongo(session: Session):
    if session.scalar(select(League).where(League.slug == "mongo")): return
    lg = League(slug="mongo", name="Mongo's 2026 ESPN Mangarelli Auction League", platform="ESPN", season=2026,
        settings={"scoring": "H2H Points PPR", "auction_budget": 200, "roster_size": 16, "starters": 9, "bench": 7,
                  "ir": 1, "kicker": False, "passing_td": 6, "passing_yards_per_point": 25})
    mgr = Manager(name="James DeStefano", aliases=["James", "JDD"]); session.add_all([lg, mgr]); session.flush()
    tm = FantasyTeam(league_id=lg.id, manager_id=mgr.id, slug="jdd", name="Tom Brady of Ass", aliases=["JDD"], is_mine=True)
    session.add(tm); session.flush()
    src = Source(league_id=lg.id, source_type="USER_CONFIRMATION", description="Authoritative current Mongo roster and FAAB supplied by user",
        original_ref="Pasted text(20260910-170839).txt", platform="ChatGPT", observed_at=AS_OF, authority=Authority.MANUAL_CORRECTION)
    session.add(src); session.flush()
    for name, pos, slot, placement in ROSTER:
        p = NFLPlayer(canonical_name=name, normalized_name=normalize_name(name), position=pos); session.add(p); session.flush()
        session.add(OwnershipEvent(league_id=lg.id, player_id=p.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="OWNERSHIP_SNAPSHOT", effective_at=AS_OF, source_id=src.id, authority=Authority.MANUAL_CORRECTION))
        session.add(LineupAssignment(league_id=lg.id, season=2026, week=1, fantasy_team_id=tm.id, player_id=p.id,
            slot=slot, placement=placement, effective_at=AS_OF, source_id=src.id))
    for name, pos in NOT_MINE_UNKNOWN:
        p = NFLPlayer(canonical_name=name, normalized_name=normalize_name(name), position=pos); session.add(p); session.flush()
        session.add(OwnershipEvent(league_id=lg.id, player_id=p.id, state=OwnershipState.UNKNOWN,
            event_type="MANUAL_CORRECTION", effective_at=AS_OF, source_id=src.id, authority=Authority.MANUAL_CORRECTION,
            notes="Confirmed not on user's roster; league ownership not established."))
    lane = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Ja'Kobi Lane")))
    session.add(ReconciliationIssue(league_id=lg.id, player_id=lane.id, category="MISSING_TRANSACTION_HISTORY",
        details={"known": "Previously dropped and later reacquired; currently rostered", "missing": ["drop date", "reacquisition date", "method", "FAAB"]}))
    session.add(ReconciliationIssue(league_id=lg.id, category="MISSING_TRANSACTION_HISTORY",
        details={"known": "Current FAAB balance is 94", "missing": ["opening budget confirmation", "complete expenditure history"]}))
    session.add(ReconciliationIssue(league_id=lg.id, category="MISSING_DRAFT_DATA",
        details={"missing": "Complete 2026 Mongo auction results and all teams"}))
    session.add(FaabBalanceObservation(league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("94"), observed_at=AS_OF, source_id=src.id))
    session.flush(); rebuild_state(session, "mongo")

