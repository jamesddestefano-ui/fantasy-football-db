from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (Authority, FaabBalanceObservation, FantasyTeam, League, LineupAssignment,
    Manager, NFLPlayer, OwnershipEvent, OwnershipState, ReconciliationIssue, Source,
    TransactionEvent, TransactionGroup)
from .names import normalize_name
from .services import rebuild_state

AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
MALIK_DAVIS_IR_CONFIRMED_AT = datetime(2026, 9, 11, 21, 5, 15, tzinfo=timezone.utc)
DEMERCADO_ADD_CONFIRMED_AT = datetime(2026, 9, 11, 21, 43, 0, tzinfo=timezone.utc)
ROSTER = [
    ("Jalen Hurts", "QB", "QB", "STARTER"), ("De'Von Achane", "RB", "RB", "STARTER"),
    ("Bijan Robinson", "RB", "RB", "STARTER"), ("Luther Burden III", "WR", "WR", "STARTER"),
    ("Tetairoa McMillan", "WR", "WR", "STARTER"), ("Mark Andrews", "TE", "TE", "STARTER"),
    ("Josh Downs", "WR", "FLEX", "STARTER"), ("CeeDee Lamb", "WR", "FLEX", "STARTER"),
    ("Eagles D/ST", "D/ST", "D/ST", "STARTER"), ("Kaelon Black", "RB", "BN", "BENCH"),
    ("Ray Davis", "RB", "BN", "BENCH"), ("Malik Davis", "RB", "IR", "IR"),
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
    malik = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Malik Davis")))
    ir_source = Source(
        league_id=lg.id,
        source_type="USER_CONFIRMATION",
        description="User confirmed Malik Davis moved from bench to IR",
        original_ref="data/imports/2026-09-11-malik-davis-ir.json",
        platform="ChatGPT/ESPN",
        observed_at=MALIK_DAVIS_IR_CONFIRMED_AT,
        authority=Authority.MANUAL_CORRECTION,
        notes="Exact ESPN transaction time was not supplied; timestamp is the user-confirmation time.",
    )
    session.add(ir_source); session.flush()
    ir_group = TransactionGroup(
        id="malik-ir-20260911-confirmed-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MALIK_DAVIS_IR_CONFIRMED_AT, source_id=ir_source.id,
        notes="Malik Davis moved from bench to IR; ownership unchanged.",
    )
    session.add(ir_group); session.flush()
    session.add(TransactionEvent(
        group_id=ir_group.id, sequence=1, event_type="IR_MOVE", player_id=malik.id,
        notes="Moved from BN/BENCH to IR/IR based on explicit user confirmation.",
    ))
    demercado = NFLPlayer(
        canonical_name="Emari Demercado", normalized_name=normalize_name("Emari Demercado"),
        position="RB", nfl_team="DAL",
    )
    session.add(demercado); session.flush()
    add_source = Source(
        league_id=lg.id,
        source_type="USER_CONFIRMATION",
        description="User confirmed Emari Demercado was added for $0; roster screenshot shows him on the bench",
        original_ref="data/imports/2026-09-11-emari-demercado-free-add.json",
        platform="ChatGPT/ESPN",
        observed_at=DEMERCADO_ADD_CONFIRMED_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Exact ESPN transaction time was not supplied; timestamp is the user-confirmation time.",
    )
    session.add(add_source); session.flush()
    add_group = TransactionGroup(
        id="demercado-add-20260911-free-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=DEMERCADO_ADD_CONFIRMED_AT, source_id=add_source.id,
        notes="Emari Demercado added for $0 after Malik Davis moved to IR; no player was dropped.",
    )
    session.add(add_group); session.flush()
    session.add_all([
        TransactionEvent(
            group_id=add_group.id, sequence=1, event_type="FREE_AGENT_ADD", player_id=demercado.id,
            faab_amount=Decimal("0"), notes="Free pickup; no drop.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=demercado.id, fantasy_team_id=tm.id,
            state=OwnershipState.OWNED, event_type="ADDED", effective_at=DEMERCADO_ADD_CONFIRMED_AT,
            source_id=add_source.id, authority=Authority.CONFIRMED_TRANSACTION,
            transaction_group_id=add_group.id, notes="User-confirmed completed free-agent add for $0.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=1, fantasy_team_id=tm.id, player_id=demercado.id,
            slot="BN", placement="BENCH", effective_at=DEMERCADO_ADD_CONFIRMED_AT, source_id=add_source.id,
        ),
    ])
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
