from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (Authority, FaabBalanceObservation, FaabEntry, FantasyTeam, League, LineupAssignment,
    Manager, NFLPlayer, OwnershipEvent, OwnershipState, PlayerAlias, ReconciliationIssue, Source,
    TransactionEvent, TransactionGroup)
from .names import normalize_name
from .services import rebuild_state

AS_OF = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
# ESPN evidence supplied calendar day ET only; noon ET (EDT=UTC-4) used as effective_at.
SEP3_ET = datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc)
SEP8_ET = datetime(2026, 9, 8, 16, 0, tzinfo=timezone.utc)
FAAB_OPENING_AT = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
MALIK_DAVIS_IR_CONFIRMED_AT = datetime(2026, 9, 11, 21, 5, 15, tzinfo=timezone.utc)
DEMERCADO_ADD_CONFIRMED_AT = datetime(2026, 9, 11, 21, 43, 0, tzinfo=timezone.utc)
MALIK_DAVIS_DROP_AT = datetime(2026, 9, 15, 8, 46, 0, tzinfo=timezone.utc)  # Tue Sep 15, 4:46 am ET
SAMPSON_IR_OBSERVED_AT = datetime(2026, 9, 15, 12, 10, 0, tzinfo=timezone.utc)  # Live Check capture ET→UTC
BELL_SANDERS_WAIVER_AT = datetime(2026, 9, 16, 4, 23, 0, tzinfo=timezone.utc)  # Wed Sep 16, 12:23 am ET
BATEMAN_DEMERCADO_AT = datetime(2026, 9, 17, 15, 14, 0, tzinfo=timezone.utc)  # Thu Sep 17, 11:14 am ET
HOLANI_LANE_AT = datetime(2026, 9, 20, 0, 28, 0, tzinfo=timezone.utc)  # Sat Sep 19, 8:28 pm ET
GADSDEN_SANDERS_WAIVER_AT = datetime(2026, 9, 23, 7, 27, 0, tzinfo=timezone.utc)  # Wed Sep 23, 3:27 am ET
PACKERS_EAGLES_DST_AT = datetime(2026, 9, 30, 15, 58, 23, tzinfo=timezone.utc)  # Tue Sep 30, 11:58:23 am ET
MITCHELL_ACHANE_AT = datetime(2026, 9, 30, 15, 59, 9, tzinfo=timezone.utc)  # Tue Sep 30, 11:59:09 am ET
PENIX_BELL_WAIVER_AT = datetime(2026, 10, 7, 7, 34, 0, tzinfo=timezone.utc)  # Wed Oct 7, 3:34 am ET
RAIDERS_PACKERS_DST_AT = datetime(2026, 10, 8, 22, 13, 0, tzinfo=timezone.utc)  # Wed Oct 8, 6:13 pm ET
TESLAA_BATEMAN_AT = datetime(2026, 10, 9, 13, 28, 0, tzinfo=timezone.utc)  # Thu Oct 9, 9:28 am ET
FLOURNOY_TESLAA_AT = datetime(2026, 10, 14, 11, 30, 0, tzinfo=timezone.utc)  # Wed Oct 14, 7:30 am ET
SAINTS_RAIDERS_DST_AT = datetime(2026, 10, 14, 11, 30, 0, tzinfo=timezone.utc)  # Wed Oct 14, 7:30 am ET
HIGBEE_GADSDEN_AT = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)  # Wed Oct 14, 8:00 am ET
MCLAUGHLIN_HOLANI_AT = datetime(2026, 10, 14, 12, 18, 0, tzinfo=timezone.utc)  # Wed Oct 14, 8:18 am ET
ESTIME_PENIX_AT = datetime(2026, 10, 14, 12, 18, 0, tzinfo=timezone.utc)  # Wed Oct 14, 8:18 am ET
WINSTON_DAVIS_AT = datetime(2026, 10, 14, 12, 22, 0, tzinfo=timezone.utc)  # Wed Oct 14, 8:22 am ET
COWING_ESTIME_AT = datetime(2026, 10, 15, 23, 10, 0, tzinfo=timezone.utc)  # Thu Oct 15, 7:10 pm ET
MCKEE_HURTS_AT = datetime(2026, 10, 16, 0, 19, 0, tzinfo=timezone.utc)  # Thu Oct 15, 8:19 pm ET
ESTIME_MCKEE_AT = datetime(2026, 10, 18, 16, 18, 0, tzinfo=timezone.utc)  # Sun Oct 18, 12:18 pm ET
MURRAY_ANDREWS_WAIVER_AT = datetime(2026, 10, 21, 8, 8, 0, tzinfo=timezone.utc)  # Wed Oct 21, 4:08 am ET
MCCARTHY_WINSTON_AT = datetime(2026, 10, 21, 15, 17, 0, tzinfo=timezone.utc)  # Wed Oct 21, 11:17 am ET
BROWNS_SAINTS_DST_AT = datetime(2026, 10, 22, 22, 13, 59, tzinfo=timezone.utc)  # Thu Oct 22, 6:13:59 pm ET
KNIGHT_ESTIME_AT = datetime(2026, 10, 22, 22, 15, 37, tzinfo=timezone.utc)  # Thu Oct 22, 6:15:37 pm ET
WICKS_MCLAUGHLIN_AT = datetime(2026, 10, 22, 22, 26, 17, tzinfo=timezone.utc)  # Thu Oct 22, 6:26:17 pm ET
JOHNSON_COWING_AT = datetime(2026, 10, 22, 22, 26, 31, tzinfo=timezone.utc)  # Thu Oct 22, 6:26:31 pm ET
WICKS_DROP_AT = datetime(2026, 10, 25, 12, 50, 0, tzinfo=timezone.utc)  # Sun Oct 25, 8:50 am ET (ESPN activity, minute precision)
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

ET_DAY_NOTE = (
    "ESPN evidence supplied calendar day America/New_York only; "
    "effective_at is noon Eastern (16:00 UTC during EDT) for that day."
)


def _player(session: Session, name: str, position: str | None = None, nfl_team: str | None = None) -> NFLPlayer:
    existing = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name(name)))
    if existing:
        return existing
    p = NFLPlayer(canonical_name=name, normalized_name=normalize_name(name), position=position, nfl_team=nfl_team)
    session.add(p)
    session.flush()
    return p


def seed_mongo(session: Session):
    if session.scalar(select(League).where(League.slug == "mongo")):
        return
    lg = League(
        slug="mongo",
        name="Mongo's 2026 ESPN Mangarelli Auction League",
        platform="ESPN",
        season=2026,
        settings={
            "scoring": "H2H Points PPR",
            "auction_budget": 200,
            "faab_budget": 100,
            "roster_size": 16,
            "starters": 9,
            "bench": 7,
            "ir": 1,
            "kicker": False,
            "passing_td": 6,
            "passing_yards_per_point": 25,
            "passing_int": -2,
            "roster_slots": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2, "D/ST": 1, "BN": 7, "IR": 1},
            "espn_league_id": "1470431049",
            "espn_team_id": 2,
        },
    )
    mgr = Manager(name="James DeStefano", aliases=["James", "JDD"])
    session.add_all([lg, mgr])
    session.flush()
    tm = FantasyTeam(
        league_id=lg.id, manager_id=mgr.id, slug="jdd", name="Tom Brady of Ass",
        aliases=["JDD", "James DeStefano"], is_mine=True,
    )
    session.add(tm)
    session.flush()
    src = Source(
        league_id=lg.id, source_type="USER_CONFIRMATION",
        description="Authoritative current Mongo roster and FAAB supplied by user",
        original_ref="Pasted text(20260910-170839).txt", platform="ChatGPT",
        observed_at=AS_OF, authority=Authority.MANUAL_CORRECTION,
    )
    session.add(src)
    session.flush()
    espn_src = Source(
        league_id=lg.id, source_type="ESPN_EXPORT",
        description="Authenticated ESPN league/team settings and completed transaction history for Mongo 2026",
        original_ref="authenticated ESPN evidence 2026-09 (leagueId 1470431049, teamId 2)",
        platform="ESPN", observed_at=datetime(2026, 9, 11, 23, 0, tzinfo=timezone.utc),
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="League/team IDs, scoring INT -2, FAAB opening $100, and dated add/drop/waiver events from ESPN UI.",
    )
    session.add(espn_src)
    session.flush()

    for name, pos, slot, placement in ROSTER:
        p = _player(session, name, pos)
        session.add(OwnershipEvent(
            league_id=lg.id, player_id=p.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="OWNERSHIP_SNAPSHOT", effective_at=AS_OF, source_id=src.id,
            authority=Authority.MANUAL_CORRECTION,
        ))
        session.add(LineupAssignment(
            league_id=lg.id, season=2026, week=1, fantasy_team_id=tm.id, player_id=p.id,
            slot=slot, placement=placement, effective_at=AS_OF, source_id=src.id,
        ))

    for name, pos in NOT_MINE_UNKNOWN:
        _player(session, name, pos)

    # FAAB opening $100 (league acquisition budget) then -$6 Saylors waiver → $94 remaining.
    session.add(FaabEntry(
        league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("100"), kind="OPENING_BUDGET",
        effective_at=FAAB_OPENING_AT, source_id=espn_src.id,
    ))

    saylors = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jacob Saylors")))
    saylors_claim = TransactionGroup(
        id="saylors-waiver-20260903-faab6-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SEP3_ET, source_id=espn_src.id,
        notes="Jacob Saylors acquired on waivers for $6. " + ET_DAY_NOTE,
    )
    session.add(saylors_claim)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=saylors_claim.id, sequence=1, event_type="WAIVER_ADD", player_id=saylors.id,
            faab_amount=Decimal("6"), notes="Waiver claim $6.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=saylors.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SEP3_ET, source_id=espn_src.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=saylors_claim.id,
            notes="ESPN waiver claim. " + ET_DAY_NOTE,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-6"), kind="WAIVER_EXPENDITURE",
            effective_at=SEP3_ET, transaction_group_id=saylors_claim.id, source_id=espn_src.id,
        ),
    ])

    # Sep 3 ESPN live: Black add + Lane drop; Tucker add + Singleton drop (not bare free adds).
    # Lane is re-acquired Sep 8 (Boutte drop); Singleton remains not on roster.
    black = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Kaelon Black")))
    lane = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Ja'Kobi Lane")))
    black_lane = TransactionGroup(
        id="black-add-lane-drop-20260903-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SEP3_ET, source_id=espn_src.id,
        notes="Kaelon Black added for $0; Ja'Kobi Lane dropped. " + ET_DAY_NOTE,
    )
    session.add(black_lane)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=black_lane.id, sequence=1, event_type="DROP", player_id=lane.id,
            notes="Dropped when adding Kaelon Black.",
        ),
        TransactionEvent(
            group_id=black_lane.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=black.id,
            faab_amount=Decimal("0"), notes="Free add.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=lane.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=SEP3_ET, source_id=espn_src.id, authority=Authority.CONFIRMED_TRANSACTION,
            transaction_group_id=black_lane.id,
            notes="Drop proves departure from roster, not current free agency. Lane re-added Sep 8. " + ET_DAY_NOTE,
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=black.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SEP3_ET, source_id=espn_src.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=black_lane.id,
            notes="ESPN free add dropping Lane. Later confirmed still owned by Sep 10 roster snapshot. " + ET_DAY_NOTE,
        ),
    ])

    tucker = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Tre Tucker")))
    singleton = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Nicholas Singleton")))
    tucker_singleton = TransactionGroup(
        id="tucker-add-singleton-drop-20260903-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SEP3_ET, source_id=espn_src.id,
        notes="Tre Tucker added for $0; Nicholas Singleton dropped. " + ET_DAY_NOTE,
    )
    session.add(tucker_singleton)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=tucker_singleton.id, sequence=1, event_type="DROP", player_id=singleton.id,
            notes="Dropped when adding Tre Tucker.",
        ),
        TransactionEvent(
            group_id=tucker_singleton.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=tucker.id,
            faab_amount=Decimal("0"), notes="Free add.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=singleton.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=SEP3_ET, source_id=espn_src.id, authority=Authority.CONFIRMED_TRANSACTION,
            transaction_group_id=tucker_singleton.id,
            notes="Drop proves departure from roster, not current free agency. " + ET_DAY_NOTE,
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=tucker.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SEP3_ET, source_id=espn_src.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=tucker_singleton.id,
            notes="ESPN free add dropping Singleton. Later confirmed still owned by Sep 10 roster snapshot. " + ET_DAY_NOTE,
        ),
    ])

    lane = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Ja'Kobi Lane")))
    boutte = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Kayshon Boutte")))
    lane_boutte = TransactionGroup(
        id="lane-add-boutte-drop-20260908-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SEP8_ET, source_id=espn_src.id,
        notes="Ja'Kobi Lane added for $0; Kayshon Boutte dropped. " + ET_DAY_NOTE,
    )
    session.add(lane_boutte)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=lane_boutte.id, sequence=1, event_type="DROP", player_id=boutte.id,
            notes="Dropped when adding Ja'Kobi Lane.",
        ),
        TransactionEvent(
            group_id=lane_boutte.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=lane.id,
            faab_amount=Decimal("0"), notes="Free add.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=boutte.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=SEP8_ET, source_id=espn_src.id, authority=Authority.CONFIRMED_TRANSACTION,
            transaction_group_id=lane_boutte.id,
            notes="Drop proves departure from roster, not current free agency. Boutte original acquisition not in ESPN evidence.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=lane.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SEP8_ET, source_id=espn_src.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=lane_boutte.id,
            notes="ESPN free add dropping Boutte. " + ET_DAY_NOTE,
        ),
    ])

    malik = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Malik Davis")))
    malik_saylors = TransactionGroup(
        id="malik-add-saylors-drop-20260908-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SEP8_ET, source_id=espn_src.id,
        notes="Malik Davis added for $0; Jacob Saylors dropped. " + ET_DAY_NOTE,
    )
    session.add(malik_saylors)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=malik_saylors.id, sequence=1, event_type="DROP", player_id=saylors.id,
            notes="Dropped when adding Malik Davis.",
        ),
        TransactionEvent(
            group_id=malik_saylors.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=malik.id,
            faab_amount=Decimal("0"), notes="Free add.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=saylors.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=SEP8_ET, source_id=espn_src.id, authority=Authority.CONFIRMED_TRANSACTION,
            transaction_group_id=malik_saylors.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=malik.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SEP8_ET, source_id=espn_src.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=malik_saylors.id,
            notes="ESPN free add dropping Saylors. " + ET_DAY_NOTE,
        ),
    ])

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
    session.add(ir_source)
    session.flush()
    ir_group = TransactionGroup(
        id="malik-ir-20260911-confirmed-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MALIK_DAVIS_IR_CONFIRMED_AT, source_id=ir_source.id,
        notes="Malik Davis moved from bench to IR; ownership unchanged.",
    )
    session.add(ir_group)
    session.flush()
    session.add(TransactionEvent(
        group_id=ir_group.id, sequence=1, event_type="IR_MOVE", player_id=malik.id,
        notes="Moved from BN/BENCH to IR/IR based on explicit user confirmation.",
    ))

    demercado = _player(session, "Emari Demercado", "RB", "DAL")
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
    session.add(add_source)
    session.flush()
    add_group = TransactionGroup(
        id="demercado-add-20260911-free-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=DEMERCADO_ADD_CONFIRMED_AT, source_id=add_source.id,
        notes="Emari Demercado added for $0 after Malik Davis moved to IR; no player was dropped.",
    )
    session.add(add_group)
    session.flush()
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


    # --- 2026-09-15 ESPN Live Check: DROP Malik Davis; IR_MOVE Dylan Sampson ---
    malik = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Malik Davis")))
    davis_drop_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Dropped Malik Davis, DAL RB (Tue Sep 15, 4:46 am)",
        original_ref="data/imports/2026-09-15-malik-davis-drop.json",
        platform="ESPN",
        observed_at=MALIK_DAVIS_DROP_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-15; FAAB remained $94; no paired add.",
    )
    session.add(davis_drop_source)
    session.flush()
    davis_drop_group = TransactionGroup(
        id="malik-davis-drop-20260915-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MALIK_DAVIS_DROP_AT, source_id=davis_drop_source.id,
        notes="ESPN-authoritative DROP of Malik Davis; ownership ends (not FREE_AGENT_CONFIRMED).",
    )
    session.add(davis_drop_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=davis_drop_group.id, sequence=1, event_type="DROP", player_id=malik.id,
            notes="Dropped from roster per ESPN activity Tue Sep 15, 4:46 am ET.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=malik.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MALIK_DAVIS_DROP_AT, source_id=davis_drop_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=davis_drop_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
    ])

    sampson = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Dylan Sampson")))
    sampson_ir_source = Source(
        league_id=lg.id,
        source_type="CURRENT_ROSTER_SCREENSHOT",
        description="Authenticated ESPN roster: Dylan Sampson on IR with Out after Davis drop",
        original_ref="data/imports/2026-09-15-dylan-sampson-ir.json",
        platform="ESPN",
        observed_at=SAMPSON_IR_OBSERVED_AT,
        authority=Authority.ESPN_CURRENT,
        notes="Exact ESPN MOVE timestamp not on activity filter; observed_at is Live Check capture.",
    )
    session.add(sampson_ir_source)
    session.flush()
    sampson_ir_group = TransactionGroup(
        id="dylan-sampson-ir-20260915-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SAMPSON_IR_OBSERVED_AT, source_id=sampson_ir_source.id,
        notes="Dylan Sampson BN→IR; ownership unchanged.",
    )
    session.add(sampson_ir_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=sampson_ir_group.id, sequence=1, event_type="IR_MOVE", player_id=sampson.id,
            notes="Moved from BN/BENCH to IR/IR per authenticated ESPN roster (Out).",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=sampson.id,
            slot="IR", placement="IR", effective_at=SAMPSON_IR_OBSERVED_AT, source_id=sampson_ir_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("94"),
        observed_at=SAMPSON_IR_OBSERVED_AT, source_id=davis_drop_source.id,
    ))



    # --- 2026-09-16 ESPN Live Check: WAIVER Chris Bell ($2, drop Tucker) + Raheim Sanders ($2) ---
    tucker = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Tre Tucker")))
    bell = _player(session, "Chris Bell", "WR", "MIA")
    bell_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Dropped Tre Tucker; added Chris Bell from waivers for $2 (Wed Sep 16, 12:23 am)",
        original_ref="data/imports/2026-09-16-chris-bell-waiver-tucker-drop.json",
        platform="ESPN",
        observed_at=BELL_SANDERS_WAIVER_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-16; paired with Raheim Sanders $2 claim; FAAB $94→$90.",
    )
    session.add(bell_source)
    session.flush()
    bell_group = TransactionGroup(
        id="chris-bell-waiver-tucker-drop-20260916-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=BELL_SANDERS_WAIVER_AT, source_id=bell_source.id,
        notes="ESPN-authoritative ADD_DROP: Chris Bell $2 waiver; Tre Tucker dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(bell_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=bell_group.id, sequence=1, event_type="DROP", player_id=tucker.id,
            notes="Dropped when claiming Chris Bell on waivers.",
        ),
        TransactionEvent(
            group_id=bell_group.id, sequence=2, event_type="WAIVER_ADD", player_id=bell.id,
            faab_amount=Decimal("2"), notes="Waiver claim $2.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=tucker.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=BELL_SANDERS_WAIVER_AT, source_id=bell_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=bell_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=bell.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=BELL_SANDERS_WAIVER_AT, source_id=bell_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=bell_group.id,
            notes="ESPN waiver claim $2 dropping Tucker.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=bell.id,
            slot="BN", placement="BENCH", effective_at=BELL_SANDERS_WAIVER_AT, source_id=bell_source.id,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-2"), kind="WAIVER_EXPENDITURE",
            effective_at=BELL_SANDERS_WAIVER_AT, transaction_group_id=bell_group.id, source_id=bell_source.id,
        ),
    ])

    sanders = _player(session, "Raheim Sanders", "RB", "CLE")
    sanders_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Raheim Sanders from waivers for $2 (Wed Sep 16, 12:23 am)",
        original_ref="data/imports/2026-09-16-raheim-sanders-waiver-add.json",
        platform="ESPN",
        observed_at=BELL_SANDERS_WAIVER_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-16; filled previously empty BN after Davis drop.",
    )
    session.add(sanders_source)
    session.flush()
    sanders_group = TransactionGroup(
        id="raheim-sanders-waiver-20260916-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=BELL_SANDERS_WAIVER_AT, source_id=sanders_source.id,
        notes="ESPN-authoritative WAIVER_ADD Raheim Sanders $2; no drop.",
    )
    session.add(sanders_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=sanders_group.id, sequence=1, event_type="WAIVER_ADD", player_id=sanders.id,
            faab_amount=Decimal("2"), notes="Waiver claim $2.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=sanders.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=BELL_SANDERS_WAIVER_AT, source_id=sanders_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=sanders_group.id,
            notes="ESPN waiver claim $2 into empty BN.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=sanders.id,
            slot="BN", placement="BENCH", effective_at=BELL_SANDERS_WAIVER_AT, source_id=sanders_source.id,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-2"), kind="WAIVER_EXPENDITURE",
            effective_at=BELL_SANDERS_WAIVER_AT, transaction_group_id=sanders_group.id, source_id=sanders_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("90"),
        observed_at=BELL_SANDERS_WAIVER_AT, source_id=bell_source.id,
    ))


    # --- 2026-09-17 ESPN: FREE_AGENT ADD Rashod Bateman $0 / DROP Emari Demercado ---
    demercado_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Emari Demercado")))
    bateman = _player(session, "Rashod Bateman", "WR", "BAL")
    bateman_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Rashod Bateman for $0; dropped Emari Demercado (Thu Sep 17, 11:14 am)",
        original_ref="data/imports/2026-09-17-rashod-bateman-add-demercado-drop.json",
        platform="ESPN",
        observed_at=BATEMAN_DEMERCADO_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-18; FAAB remained $90.",
    )
    session.add(bateman_source)
    session.flush()
    bateman_group = TransactionGroup(
        id="rashod-bateman-add-demercado-drop-20260917-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=BATEMAN_DEMERCADO_AT, source_id=bateman_source.id,
        notes="ESPN-authoritative ADD_DROP: Rashod Bateman $0 free add; Emari Demercado dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(bateman_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=bateman_group.id, sequence=1, event_type="DROP", player_id=demercado_drop.id,
            notes="Dropped when adding Rashod Bateman.",
        ),
        TransactionEvent(
            group_id=bateman_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=bateman.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=demercado_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=BATEMAN_DEMERCADO_AT, source_id=bateman_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=bateman_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=bateman.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=BATEMAN_DEMERCADO_AT, source_id=bateman_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=bateman_group.id,
            notes="ESPN free add $0 dropping Demercado.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=bateman.id,
            slot="BN", placement="BENCH", effective_at=BATEMAN_DEMERCADO_AT, source_id=bateman_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("90"),
        observed_at=BATEMAN_DEMERCADO_AT, source_id=bateman_source.id,
    ))



    # --- 2026-09-19 ESPN: FREE_AGENT ADD George Holani $0 / DROP Ja'Kobi Lane ---
    lane_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Ja'Kobi Lane")))
    holani = _player(session, "George Holani", "RB", "SEA")
    holani_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added George Holani for $0; dropped Ja'Kobi Lane (Sat Sep 19, 8:28 pm)",
        original_ref="data/imports/2026-09-19-george-holani-add-lane-drop.json",
        platform="ESPN",
        observed_at=HOLANI_LANE_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-20; FAAB remained $90.",
    )
    session.add(holani_source)
    session.flush()
    holani_group = TransactionGroup(
        id="george-holani-add-lane-drop-20260919-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=HOLANI_LANE_AT, source_id=holani_source.id,
        notes="ESPN-authoritative ADD_DROP: George Holani $0 free add; Ja'Kobi Lane dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(holani_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=holani_group.id, sequence=1, event_type="DROP", player_id=lane_drop.id,
            notes="Dropped when adding George Holani.",
        ),
        TransactionEvent(
            group_id=holani_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=holani.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=lane_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=HOLANI_LANE_AT, source_id=holani_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=holani_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=holani.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=HOLANI_LANE_AT, source_id=holani_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=holani_group.id,
            notes="ESPN free add $0 dropping Lane.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=holani.id,
            slot="BN", placement="BENCH", effective_at=HOLANI_LANE_AT, source_id=holani_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("90"),
        observed_at=HOLANI_LANE_AT, source_id=holani_source.id,
    ))


    # --- 2026-09-23 ESPN: WAIVER ADD Oronde Gadsden $8 / DROP Raheim Sanders ---
    sanders_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Raheim Sanders")))
    gadsden = _player(session, "Oronde Gadsden", "TE", "LAC")
    gadsden_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Oronde Gadsden from waivers for $8; dropped Raheim Sanders (Wed Sep 23, 3:27 am)",
        original_ref="data/imports/2026-09-23-oronde-gadsden-waiver-sanders-drop.json",
        platform="ESPN",
        observed_at=GADSDEN_SANDERS_WAIVER_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-09-23; FAAB $90→$82.",
    )
    session.add(gadsden_source)
    session.flush()
    gadsden_group = TransactionGroup(
        id="oronde-gadsden-waiver-sanders-drop-20260923-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=GADSDEN_SANDERS_WAIVER_AT, source_id=gadsden_source.id,
        notes="ESPN-authoritative WAIVER_ADD_DROP: Oronde Gadsden $8 waiver; Raheim Sanders dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(gadsden_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=gadsden_group.id, sequence=1, event_type="DROP", player_id=sanders_drop.id,
            notes="Dropped when claiming Oronde Gadsden on waivers.",
        ),
        TransactionEvent(
            group_id=gadsden_group.id, sequence=2, event_type="WAIVER_ADD", player_id=gadsden.id,
            faab_amount=Decimal("8"), notes="Waiver claim $8.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=sanders_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=GADSDEN_SANDERS_WAIVER_AT, source_id=gadsden_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=gadsden_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=gadsden.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=GADSDEN_SANDERS_WAIVER_AT, source_id=gadsden_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=gadsden_group.id,
            notes="ESPN waiver claim $8 dropping Sanders.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=gadsden.id,
            slot="BN", placement="BENCH", effective_at=GADSDEN_SANDERS_WAIVER_AT, source_id=gadsden_source.id,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-8"), kind="WAIVER_EXPENDITURE",
            effective_at=GADSDEN_SANDERS_WAIVER_AT, transaction_group_id=gadsden_group.id, source_id=gadsden_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("82"),
        observed_at=GADSDEN_SANDERS_WAIVER_AT, source_id=gadsden_source.id,
    ))





    # --- 2026-09-30 ESPN: FREE_AGENT ADD Packers D/ST $0 / DROP Eagles D/ST ---
    eagles_dst = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Eagles D/ST")))
    packers_dst = _player(session, "Packers D/ST", "D/ST", "GB")
    packers_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Packers D/ST for $0; dropped Eagles D/ST (Tue Sep 30, 11:58 am ET)",
        original_ref="data/imports/2026-09-30-packers-dst-add-eagles-dst-drop.json",
        platform="ESPN",
        observed_at=PACKERS_EAGLES_DST_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-01; FAAB remained $82.",
    )
    session.add(packers_source)
    session.flush()
    packers_group = TransactionGroup(
        id="packers-dst-add-eagles-dst-drop-20260930-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=PACKERS_EAGLES_DST_AT, source_id=packers_source.id,
        notes="ESPN-authoritative ADD_DROP: Packers D/ST $0 free add; Eagles D/ST dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(packers_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=packers_group.id, sequence=1, event_type="DROP", player_id=eagles_dst.id,
            notes="Dropped when adding Packers D/ST.",
        ),
        TransactionEvent(
            group_id=packers_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=packers_dst.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=eagles_dst.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=PACKERS_EAGLES_DST_AT, source_id=packers_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=packers_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=packers_dst.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=PACKERS_EAGLES_DST_AT, source_id=packers_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=packers_group.id,
            notes="ESPN free add $0 dropping Eagles D/ST.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=packers_dst.id,
            slot="D/ST", placement="STARTER", effective_at=PACKERS_EAGLES_DST_AT, source_id=packers_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("82"),
        observed_at=PACKERS_EAGLES_DST_AT, source_id=packers_source.id,
    ))

    # --- 2026-09-30 ESPN: FREE_AGENT ADD Keaton Mitchell $0 / DROP De'Von Achane ---
    achane_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("De'Von Achane")))
    mitchell = _player(session, "Keaton Mitchell", "RB", "LAC")
    mitchell_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Keaton Mitchell for $0; dropped De'Von Achane (Tue Sep 30, 11:59 am ET)",
        original_ref="data/imports/2026-09-30-keaton-mitchell-add-achane-drop.json",
        platform="ESPN",
        observed_at=MITCHELL_ACHANE_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-01; FAAB remained $82; Achane on ESPN WAIVERS (ACL IR context).",
    )
    session.add(mitchell_source)
    session.flush()
    mitchell_group = TransactionGroup(
        id="keaton-mitchell-add-achane-drop-20260930-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MITCHELL_ACHANE_AT, source_id=mitchell_source.id,
        notes="ESPN-authoritative ADD_DROP: Keaton Mitchell $0 free add; De'Von Achane dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(mitchell_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=mitchell_group.id, sequence=1, event_type="DROP", player_id=achane_drop.id,
            notes="Dropped when adding Keaton Mitchell.",
        ),
        TransactionEvent(
            group_id=mitchell_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=mitchell.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=achane_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MITCHELL_ACHANE_AT, source_id=mitchell_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mitchell_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows WAIVERS.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=mitchell.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=MITCHELL_ACHANE_AT, source_id=mitchell_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mitchell_group.id,
            notes="ESPN free add $0 dropping Achane.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=mitchell.id,
            slot="BN", placement="BENCH", effective_at=MITCHELL_ACHANE_AT, source_id=mitchell_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("82"),
        observed_at=MITCHELL_ACHANE_AT, source_id=mitchell_source.id,
    ))

    # --- 2026-10-07 ESPN: WAIVER ADD Michael Penix Jr. $8 / DROP Chris Bell ---
    bell_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Chris Bell")))
    penix = _player(session, "Michael Penix Jr.", "QB", "ATL")
    penix_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Michael Penix Jr. from waivers for $8; dropped Chris Bell (Wed Oct 7, 3:34 am)",
        original_ref="data/imports/2026-10-07-michael-penix-waiver-bell-drop.json",
        platform="ESPN",
        observed_at=PENIX_BELL_WAIVER_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-07; FAAB $82→$74.",
    )
    session.add(penix_source)
    session.flush()
    penix_group = TransactionGroup(
        id="michael-penix-waiver-bell-drop-20261007-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=PENIX_BELL_WAIVER_AT, source_id=penix_source.id,
        notes="ESPN-authoritative WAIVER_ADD_DROP: Michael Penix Jr. $8 waiver; Chris Bell dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(penix_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=penix_group.id, sequence=1, event_type="DROP", player_id=bell_drop.id,
            notes="Dropped when claiming Michael Penix Jr. on waivers.",
        ),
        TransactionEvent(
            group_id=penix_group.id, sequence=2, event_type="WAIVER_ADD", player_id=penix.id,
            faab_amount=Decimal("8"), notes="Waiver claim $8.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=bell_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=PENIX_BELL_WAIVER_AT, source_id=penix_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=penix_group.id,
            notes="Drop proves departure from roster, not current free agency; dropped to Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=penix.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=PENIX_BELL_WAIVER_AT, source_id=penix_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=penix_group.id,
            notes="ESPN waiver claim $8 dropping Bell.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=penix.id,
            slot="BN", placement="BENCH", effective_at=PENIX_BELL_WAIVER_AT, source_id=penix_source.id,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-8"), kind="WAIVER_EXPENDITURE",
            effective_at=PENIX_BELL_WAIVER_AT, transaction_group_id=penix_group.id, source_id=penix_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=PENIX_BELL_WAIVER_AT, source_id=penix_source.id,
    ))

    # --- 2026-10-08 ESPN: FREE_AGENT ADD Raiders D/ST $0 / DROP Packers D/ST ---
    packers_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Packers D/ST")))
    raiders_dst = _player(session, "Raiders D/ST", "D/ST", "LV")
    raiders_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Raiders D/ST for $0; dropped Packers D/ST (Wed Oct 8, 6:13 pm ET)",
        original_ref="data/imports/2026-10-08-raiders-dst-add-packers-dst-drop.json",
        platform="ESPN",
        observed_at=RAIDERS_PACKERS_DST_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-09; FAAB remained $74; no espn_id observed for Raiders D/ST.",
    )
    session.add(raiders_source)
    session.flush()
    raiders_group = TransactionGroup(
        id="raiders-dst-add-packers-dst-drop-20261008-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=RAIDERS_PACKERS_DST_AT, source_id=raiders_source.id,
        notes="ESPN-authoritative ADD_DROP: Raiders D/ST $0 free add; Packers D/ST dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(raiders_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=raiders_group.id, sequence=1, event_type="DROP", player_id=packers_drop.id,
            notes="Dropped when adding Raiders D/ST.",
        ),
        TransactionEvent(
            group_id=raiders_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=raiders_dst.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=packers_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=RAIDERS_PACKERS_DST_AT, source_id=raiders_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=raiders_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=raiders_dst.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=RAIDERS_PACKERS_DST_AT, source_id=raiders_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=raiders_group.id,
            notes="ESPN free add $0 dropping Packers D/ST.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=raiders_dst.id,
            slot="D/ST", placement="STARTER", effective_at=RAIDERS_PACKERS_DST_AT, source_id=raiders_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=RAIDERS_PACKERS_DST_AT, source_id=raiders_source.id,
    ))

    # --- 2026-10-09 ESPN: FREE_AGENT ADD Isaac TeSlaa $0 / DROP Rashod Bateman ---
    bateman_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Rashod Bateman")))
    teslaa = _player(session, "Isaac TeSlaa", "WR", "DET")
    teslaa_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Isaac TeSlaa for $0; dropped Rashod Bateman (Thu Oct 9, 9:28 am ET)",
        original_ref="data/imports/2026-10-09-isaac-teslaa-add-bateman-drop.json",
        platform="ESPN",
        observed_at=TESLAA_BATEMAN_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-10; FAAB remained $74; no espn_id observed for Isaac TeSlaa.",
    )
    session.add(teslaa_source)
    session.flush()
    teslaa_group = TransactionGroup(
        id="isaac-teslaa-add-bateman-drop-20261009-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=TESLAA_BATEMAN_AT, source_id=teslaa_source.id,
        notes="ESPN-authoritative ADD_DROP: Isaac TeSlaa $0 free add; Rashod Bateman dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(teslaa_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=teslaa_group.id, sequence=1, event_type="DROP", player_id=bateman_drop.id,
            notes="Dropped when adding Isaac TeSlaa.",
        ),
        TransactionEvent(
            group_id=teslaa_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=teslaa.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=bateman_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=TESLAA_BATEMAN_AT, source_id=teslaa_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=teslaa_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=teslaa.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=TESLAA_BATEMAN_AT, source_id=teslaa_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=teslaa_group.id,
            notes="ESPN free add $0 dropping Rashod Bateman.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=teslaa.id,
            slot="BN", placement="BENCH", effective_at=TESLAA_BATEMAN_AT, source_id=teslaa_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=TESLAA_BATEMAN_AT, source_id=teslaa_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Ryan Flournoy $0 / DROP Isaac TeSlaa ---
    ryan_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Isaac TeSlaa")))
    ryan_add = _player(session, "Ryan Flournoy", "WR", "DAL")
    ryan_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Ryan Flournoy for $0; dropped Isaac TeSlaa (Wed Oct 14, 7:30 am ET)",
        original_ref="data/imports/2026-10-14-ryan-flournoy-add-teslaa-drop.json",
        platform="ESPN",
        observed_at=FLOURNOY_TESLAA_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-14 08:15 ET; FAAB remained $74; no espn_id observed for Ryan Flournoy.",
    )
    session.add(ryan_source)
    session.flush()
    ryan_group = TransactionGroup(
        id="ryan-flournoy-add-teslaa-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=FLOURNOY_TESLAA_AT, source_id=ryan_source.id,
        notes="ESPN-authoritative ADD_DROP: Ryan Flournoy $0 free add; Isaac TeSlaa dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(ryan_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=ryan_group.id, sequence=1, event_type="DROP", player_id=ryan_drop.id,
            notes="Dropped when adding Ryan Flournoy.",
        ),
        TransactionEvent(
            group_id=ryan_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=ryan_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=ryan_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=FLOURNOY_TESLAA_AT, source_id=ryan_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=ryan_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=ryan_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=FLOURNOY_TESLAA_AT, source_id=ryan_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=ryan_group.id,
            notes="ESPN free add $0 dropping Isaac TeSlaa.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=ryan_add.id,
            slot="BN", placement="BENCH", effective_at=FLOURNOY_TESLAA_AT, source_id=ryan_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=FLOURNOY_TESLAA_AT, source_id=ryan_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Saints D/ST $0 / DROP Raiders D/ST ---
    saints_dst_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Raiders D/ST")))
    saints_dst_add = _player(session, "Saints D/ST", "D/ST", "NO")
    saints_dst_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Saints D/ST for $0; dropped Raiders D/ST (Wed Oct 14, 7:30 am ET)",
        original_ref="data/imports/2026-10-14-saints-dst-add-raiders-dst-drop.json",
        platform="ESPN",
        observed_at=SAINTS_RAIDERS_DST_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-14 08:15 ET; FAAB remained $74; no espn_id observed for Saints D/ST.",
    )
    session.add(saints_dst_source)
    session.flush()
    saints_dst_group = TransactionGroup(
        id="saints-dst-add-raiders-dst-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=SAINTS_RAIDERS_DST_AT, source_id=saints_dst_source.id,
        notes="ESPN-authoritative ADD_DROP: Saints D/ST $0 free add; Raiders D/ST dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(saints_dst_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=saints_dst_group.id, sequence=1, event_type="DROP", player_id=saints_dst_drop.id,
            notes="Dropped when adding Saints D/ST.",
        ),
        TransactionEvent(
            group_id=saints_dst_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=saints_dst_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=saints_dst_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=SAINTS_RAIDERS_DST_AT, source_id=saints_dst_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=saints_dst_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=saints_dst_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=SAINTS_RAIDERS_DST_AT, source_id=saints_dst_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=saints_dst_group.id,
            notes="ESPN free add $0 dropping Raiders D/ST.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=saints_dst_add.id,
            slot="D/ST", placement="STARTER", effective_at=SAINTS_RAIDERS_DST_AT, source_id=saints_dst_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=SAINTS_RAIDERS_DST_AT, source_id=saints_dst_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Tyler Higbee $0 / DROP Oronde Gadsden ---
    tyler_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Oronde Gadsden")))
    tyler_add = _player(session, "Tyler Higbee", "TE", "LAR")
    tyler_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Tyler Higbee for $0; dropped Oronde Gadsden (Wed Oct 14, 8:00 am ET)",
        original_ref="data/imports/2026-10-14-tyler-higbee-add-gadsden-drop.json",
        platform="ESPN",
        observed_at=HIGBEE_GADSDEN_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-14 08:15 ET; FAAB remained $74; no espn_id observed for Tyler Higbee.",
    )
    session.add(tyler_source)
    session.flush()
    tyler_group = TransactionGroup(
        id="tyler-higbee-add-gadsden-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=HIGBEE_GADSDEN_AT, source_id=tyler_source.id,
        notes="ESPN-authoritative ADD_DROP: Tyler Higbee $0 free add; Oronde Gadsden dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(tyler_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=tyler_group.id, sequence=1, event_type="DROP", player_id=tyler_drop.id,
            notes="Dropped when adding Tyler Higbee.",
        ),
        TransactionEvent(
            group_id=tyler_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=tyler_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=tyler_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=HIGBEE_GADSDEN_AT, source_id=tyler_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=tyler_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=tyler_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=HIGBEE_GADSDEN_AT, source_id=tyler_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=tyler_group.id,
            notes="ESPN free add $0 dropping Oronde Gadsden.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=tyler_add.id,
            slot="BN", placement="BENCH", effective_at=HIGBEE_GADSDEN_AT, source_id=tyler_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=HIGBEE_GADSDEN_AT, source_id=tyler_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Jaleel McLaughlin $0 / DROP George Holani ---
    jaleel_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("George Holani")))
    jaleel_add = _player(session, "Jaleel McLaughlin", "RB", "CLE")
    jaleel_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Jaleel McLaughlin for $0; dropped George Holani (Wed Oct 14, 8:18 am ET)",
        original_ref="data/imports/2026-10-14-jaleel-mclaughlin-add-holani-drop.json",
        platform="ESPN",
        observed_at=MCLAUGHLIN_HOLANI_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-14 08:15 ET; FAAB remained $74; no espn_id observed for Jaleel McLaughlin.",
    )
    session.add(jaleel_source)
    session.flush()
    jaleel_group = TransactionGroup(
        id="jaleel-mclaughlin-add-holani-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MCLAUGHLIN_HOLANI_AT, source_id=jaleel_source.id,
        notes="ESPN-authoritative ADD_DROP: Jaleel McLaughlin $0 free add; George Holani dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(jaleel_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=jaleel_group.id, sequence=1, event_type="DROP", player_id=jaleel_drop.id,
            notes="Dropped when adding Jaleel McLaughlin.",
        ),
        TransactionEvent(
            group_id=jaleel_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=jaleel_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=jaleel_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MCLAUGHLIN_HOLANI_AT, source_id=jaleel_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=jaleel_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=jaleel_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=MCLAUGHLIN_HOLANI_AT, source_id=jaleel_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=jaleel_group.id,
            notes="ESPN free add $0 dropping George Holani.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=jaleel_add.id,
            slot="BN", placement="BENCH", effective_at=MCLAUGHLIN_HOLANI_AT, source_id=jaleel_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=MCLAUGHLIN_HOLANI_AT, source_id=jaleel_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Audric Estime $0 / DROP Michael Penix Jr. ---
    audric_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Michael Penix Jr.")))
    audric_add = _player(session, "Audric Estime", "RB", "CLE")
    audric_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Audric Estime for $0; dropped Michael Penix Jr. (Wed Oct 14, 8:18 am ET)",
        original_ref="data/imports/2026-10-14-audric-estime-add-penix-drop.json",
        platform="ESPN",
        observed_at=ESTIME_PENIX_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-14 08:15 ET; FAAB remained $74; no espn_id observed for Audric Estime.",
    )
    session.add(audric_source)
    session.flush()
    audric_group = TransactionGroup(
        id="audric-estime-add-penix-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=ESTIME_PENIX_AT, source_id=audric_source.id,
        notes="ESPN-authoritative ADD_DROP: Audric Estime $0 free add; Michael Penix Jr. dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(audric_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=audric_group.id, sequence=1, event_type="DROP", player_id=audric_drop.id,
            notes="Dropped when adding Audric Estime.",
        ),
        TransactionEvent(
            group_id=audric_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=audric_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=audric_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=ESTIME_PENIX_AT, source_id=audric_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=audric_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=audric_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=ESTIME_PENIX_AT, source_id=audric_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=audric_group.id,
            notes="ESPN free add $0 dropping Michael Penix Jr..",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=audric_add.id,
            slot="BN", placement="BENCH", effective_at=ESTIME_PENIX_AT, source_id=audric_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=ESTIME_PENIX_AT, source_id=audric_source.id,
    ))

    # --- 2026-10-14 ESPN: FREE_AGENT ADD Jameis Winston $0 / DROP Ray Davis ---
    jameis_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Ray Davis")))
    jameis_add = _player(session, "Jameis Winston", "QB", "NYG")
    jameis_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Jameis Winston for $0; dropped Ray Davis (Wed Oct 14, 8:22 am ET)",
        original_ref="data/imports/2026-10-14-jameis-winston-add-ray-davis-drop.json",
        platform="ESPN",
        observed_at=WINSTON_DAVIS_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-15 08:17 ET; FAAB remained $74; no espn_id observed for Jameis Winston.",
    )
    session.add(jameis_source)
    session.flush()
    jameis_group = TransactionGroup(
        id="jameis-winston-add-ray-davis-drop-20261014-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=WINSTON_DAVIS_AT, source_id=jameis_source.id,
        notes="ESPN-authoritative ADD_DROP: Jameis Winston $0 free add; Ray Davis dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(jameis_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=jameis_group.id, sequence=1, event_type="DROP", player_id=jameis_drop.id,
            notes="Dropped when adding Jameis Winston.",
        ),
        TransactionEvent(
            group_id=jameis_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=jameis_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=jameis_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=WINSTON_DAVIS_AT, source_id=jameis_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=jameis_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=jameis_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=WINSTON_DAVIS_AT, source_id=jameis_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=jameis_group.id,
            notes="ESPN free add $0 dropping Ray Davis.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=jameis_add.id,
            slot="QB", placement="STARTER", effective_at=WINSTON_DAVIS_AT, source_id=jameis_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=WINSTON_DAVIS_AT, source_id=jameis_source.id,
    ))

    # --- 2026-10-15 ESPN: FREE_AGENT ADD Jacob Cowing $0 / DROP Audric Estime ---
    cowing_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Audric Estime")))
    cowing_add = _player(session, "Jacob Cowing", "WR", "SF")
    cowing_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Jacob Cowing for $0; dropped Audric Estime (Thu Oct 15, 7:10 pm ET)",
        original_ref="data/imports/2026-10-15-jacob-cowing-add-estime-drop.json",
        platform="ESPN",
        observed_at=COWING_ESTIME_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-20 08:09 ET; FAAB remained $74; no espn_id observed for Jacob Cowing.",
    )
    session.add(cowing_source)
    session.flush()
    cowing_group = TransactionGroup(
        id="jacob-cowing-add-estime-drop-20261015-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=COWING_ESTIME_AT, source_id=cowing_source.id,
        notes="ESPN-authoritative ADD_DROP: Jacob Cowing $0 free add; Audric Estime dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(cowing_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=cowing_group.id, sequence=1, event_type="DROP", player_id=cowing_drop.id,
            notes="Dropped when adding Jacob Cowing.",
        ),
        TransactionEvent(
            group_id=cowing_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=cowing_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=cowing_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=COWING_ESTIME_AT, source_id=cowing_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=cowing_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=cowing_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=COWING_ESTIME_AT, source_id=cowing_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=cowing_group.id,
            notes="ESPN free add $0 dropping Audric Estime.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=cowing_add.id,
            slot="BN", placement="BENCH", effective_at=COWING_ESTIME_AT, source_id=cowing_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=COWING_ESTIME_AT, source_id=cowing_source.id,
    ))

    # --- 2026-10-15 ESPN: FREE_AGENT ADD Tanner McKee $0 / DROP Jalen Hurts ---
    mckee_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jalen Hurts")))
    mckee_add = _player(session, "Tanner McKee", "QB", "PHI")
    mckee_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Tanner McKee for $0; dropped Jalen Hurts (Thu Oct 15, 8:19 pm ET)",
        original_ref="data/imports/2026-10-15-tanner-mckee-add-hurts-drop.json",
        platform="ESPN",
        observed_at=MCKEE_HURTS_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-20 08:09 ET; FAAB remained $74; no espn_id observed for Tanner McKee.",
    )
    session.add(mckee_source)
    session.flush()
    mckee_group = TransactionGroup(
        id="tanner-mckee-add-hurts-drop-20261015-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MCKEE_HURTS_AT, source_id=mckee_source.id,
        notes="ESPN-authoritative ADD_DROP: Tanner McKee $0 free add; Jalen Hurts dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(mckee_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=mckee_group.id, sequence=1, event_type="DROP", player_id=mckee_drop.id,
            notes="Dropped when adding Tanner McKee.",
        ),
        TransactionEvent(
            group_id=mckee_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=mckee_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=mckee_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MCKEE_HURTS_AT, source_id=mckee_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mckee_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=mckee_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=MCKEE_HURTS_AT, source_id=mckee_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mckee_group.id,
            notes="ESPN free add $0 dropping Jalen Hurts. Lineup slot not observed; no assignment recorded.",
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=MCKEE_HURTS_AT, source_id=mckee_source.id,
    ))

    # --- 2026-10-18 ESPN: FREE_AGENT ADD Audric Estime $0 (re-acquired) / DROP Tanner McKee ---
    estime2_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Tanner McKee")))
    estime2_add = _player(session, "Audric Estime", "RB", "CLE")
    estime2_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Audric Estime for $0; dropped Tanner McKee (Sun Oct 18, 12:18 pm ET)",
        original_ref="data/imports/2026-10-18-audric-estime-add-mckee-drop.json",
        platform="ESPN",
        observed_at=ESTIME_MCKEE_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-20 08:09 ET; FAAB remained $74; no espn_id observed for Audric Estime.",
    )
    session.add(estime2_source)
    session.flush()
    estime2_group = TransactionGroup(
        id="audric-estime-add-mckee-drop-20261018-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=ESTIME_MCKEE_AT, source_id=estime2_source.id,
        notes="ESPN-authoritative ADD_DROP: Audric Estime $0 free add (re-acquired after Oct 15 drop); Tanner McKee dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(estime2_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=estime2_group.id, sequence=1, event_type="DROP", player_id=estime2_drop.id,
            notes="Dropped when adding Audric Estime.",
        ),
        TransactionEvent(
            group_id=estime2_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=estime2_add.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=estime2_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=ESTIME_MCKEE_AT, source_id=estime2_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=estime2_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=estime2_add.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=ESTIME_MCKEE_AT, source_id=estime2_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=estime2_group.id,
            notes="ESPN free add $0 re-acquiring Audric Estime, dropping Tanner McKee. Existing week=2 BN assignment retained (ESPN shows BN).",
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("74"),
        observed_at=ESTIME_MCKEE_AT, source_id=estime2_source.id,
    ))

    # --- 2026-10-21 ESPN: WAIVER ADD Kyler Murray $8 / DROP Mark Andrews ---
    andrews_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Mark Andrews")))
    murray = _player(session, "Kyler Murray", "QB", "MIN")
    murray_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added Kyler Murray (MIN QB) from waivers for $8; dropped Mark Andrews (BAL TE) (Wed Oct 21, 4:08 am ET)",
        original_ref="data/imports/2026-10-21-kyler-murray-waiver-andrews-drop.json",
        platform="ESPN",
        observed_at=MURRAY_ANDREWS_WAIVER_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-21 08:17 ET; FAAB $74→$66; no espn_id observed for Kyler Murray.",
    )
    session.add(murray_source)
    session.flush()
    murray_group = TransactionGroup(
        id="kyler-murray-waiver-andrews-drop-20261021-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MURRAY_ANDREWS_WAIVER_AT, source_id=murray_source.id,
        notes="ESPN-authoritative WAIVER_ADD_DROP: Kyler Murray $8 waiver; Mark Andrews dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(murray_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=murray_group.id, sequence=1, event_type="DROP", player_id=andrews_drop.id,
            notes="Dropped when claiming Kyler Murray on waivers.",
        ),
        TransactionEvent(
            group_id=murray_group.id, sequence=2, event_type="WAIVER_ADD", player_id=murray.id,
            faab_amount=Decimal("8"), notes="Waiver claim $8.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=andrews_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MURRAY_ANDREWS_WAIVER_AT, source_id=murray_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=murray_group.id,
            notes="Drop proves departure from roster, not current free agency; drop destination not captured.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=murray.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=MURRAY_ANDREWS_WAIVER_AT, source_id=murray_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=murray_group.id,
            notes="ESPN waiver claim $8 dropping Mark Andrews.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=murray.id,
            slot="BN", placement="BENCH", effective_at=MURRAY_ANDREWS_WAIVER_AT, source_id=murray_source.id,
        ),
        FaabEntry(
            league_id=lg.id, fantasy_team_id=tm.id, amount=Decimal("-8"), kind="WAIVER_EXPENDITURE",
            effective_at=MURRAY_ANDREWS_WAIVER_AT, transaction_group_id=murray_group.id, source_id=murray_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=MURRAY_ANDREWS_WAIVER_AT, source_id=murray_source.id,
    ))

    # --- 2026-10-21 ESPN: FREE_AGENT ADD J.J. McCarthy $0 / DROP Jameis Winston ---
    mccarthy_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jameis Winston")))
    mccarthy = _player(session, "J.J. McCarthy", "QB", "NYG")
    mccarthy_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Added J.J. McCarthy (NYG QB) from free agency for $0; dropped Jameis Winston (NYG QB) to waivers (Wed Oct 21, 11:17 am ET)",
        original_ref="data/imports/2026-10-21-jj-mccarthy-add-winston-drop.json",
        platform="ESPN",
        observed_at=MCCARTHY_WINSTON_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="Mongo Live Check 2026-10-22 08:16 ET; FAAB remained $66; no espn_id observed for J.J. McCarthy.",
    )
    session.add(mccarthy_source)
    session.flush()
    mccarthy_group = TransactionGroup(
        id="jj-mccarthy-add-winston-drop-20261021-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=MCCARTHY_WINSTON_AT, source_id=mccarthy_source.id,
        notes="ESPN-authoritative ADD_DROP: J.J. McCarthy $0 free add; Jameis Winston dropped to waivers (not FREE_AGENT_CONFIRMED).",
    )
    session.add(mccarthy_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=mccarthy_group.id, sequence=1, event_type="DROP", player_id=mccarthy_drop.id,
            notes="Dropped to waivers when adding J.J. McCarthy.",
        ),
        TransactionEvent(
            group_id=mccarthy_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=mccarthy.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=mccarthy_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=MCCARTHY_WINSTON_AT, source_id=mccarthy_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mccarthy_group.id,
            notes="Drop proves departure from roster, not current free agency; ESPN shows Waivers.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=mccarthy.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=MCCARTHY_WINSTON_AT, source_id=mccarthy_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=mccarthy_group.id,
            notes="ESPN free add $0 dropping Jameis Winston.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=mccarthy.id,
            slot="BN", placement="BENCH", effective_at=MCCARTHY_WINSTON_AT, source_id=mccarthy_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=MCCARTHY_WINSTON_AT, source_id=mccarthy_source.id,
    ))

    # --- 2026-10-22 ESPN: FREE_AGENT ADD Browns D/ST $0 / DROP Saints D/ST ---
    browns_dst_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Saints D/ST")))
    browns_dst = _player(session, "Browns D/ST", "D/ST", "CLE")
    if browns_dst.espn_id is None:
        browns_dst.espn_id = "-16005"  # from ESPN API transaction log / roster snapshot 2026-10-22T22:27Z
    browns_dst_source = Source(
        league_id=lg.id,
        source_type="ESPN_API_TRANSACTION",
        description="ESPN transaction log (read-only API) eee2ff45-80ec-494a-b443-c5e9d5b32e6f FREEAGENT EXECUTED: added Browns D/ST (CLE D/ST) for $0; dropped Saints D/ST (NO D/ST) (Thu Oct 22, 6:13:59 pm ET)",
        original_ref="data/imports/2026-10-22-browns-dst-add-saints-dst-drop.json",
        platform="ESPN",
        observed_at=BROWNS_SAINTS_DST_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="ESPN API snapshot data/espn_api/2026-10-22T2227Z.json (observed 2026-10-22T22:27:33Z); FAAB remained $66; espn_id -16005 from ESPN data.",
    )
    session.add(browns_dst_source)
    session.flush()
    browns_dst_group = TransactionGroup(
        id="browns-dst-add-saints-dst-drop-20261022-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=BROWNS_SAINTS_DST_AT, source_id=browns_dst_source.id,
        notes="ESPN-authoritative ADD_DROP: Browns D/ST $0 free add; Saints D/ST dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(browns_dst_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=browns_dst_group.id, sequence=1, event_type="DROP", player_id=browns_dst_drop.id,
            notes="Dropped when adding Browns D/ST.",
        ),
        TransactionEvent(
            group_id=browns_dst_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=browns_dst.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=browns_dst_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=BROWNS_SAINTS_DST_AT, source_id=browns_dst_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=browns_dst_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=browns_dst.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=BROWNS_SAINTS_DST_AT, source_id=browns_dst_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=browns_dst_group.id,
            notes="ESPN free add $0 dropping Saints D/ST.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=browns_dst.id,
            slot="D/ST", placement="STARTER", effective_at=BROWNS_SAINTS_DST_AT, source_id=browns_dst_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=BROWNS_SAINTS_DST_AT, source_id=browns_dst_source.id,
    ))

    # --- 2026-10-22 ESPN: FREE_AGENT ADD Bam Knight $0 / DROP Audric Estime ---
    knight_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Audric Estime")))
    knight = _player(session, "Bam Knight", "RB", "ARI")
    if knight.espn_id is None:
        knight.espn_id = "4427728"  # from ESPN API transaction log / roster snapshot 2026-10-22T22:27Z
    knight_source = Source(
        league_id=lg.id,
        source_type="ESPN_API_TRANSACTION",
        description="ESPN transaction log (read-only API) daefc437-6173-4c20-93ec-9b7e2542d159 FREEAGENT EXECUTED: added Bam Knight (ARI RB) for $0; dropped Audric Estime (CLE RB) (Thu Oct 22, 6:15:37 pm ET)",
        original_ref="data/imports/2026-10-22-bam-knight-add-estime-drop.json",
        platform="ESPN",
        observed_at=KNIGHT_ESTIME_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="ESPN API snapshot data/espn_api/2026-10-22T2227Z.json (observed 2026-10-22T22:27:33Z); FAAB remained $66; espn_id 4427728 from ESPN data.",
    )
    session.add(knight_source)
    session.flush()
    knight_group = TransactionGroup(
        id="bam-knight-add-estime-drop-20261022-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=KNIGHT_ESTIME_AT, source_id=knight_source.id,
        notes="ESPN-authoritative ADD_DROP: Bam Knight $0 free add; Audric Estime dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(knight_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=knight_group.id, sequence=1, event_type="DROP", player_id=knight_drop.id,
            notes="Dropped when adding Bam Knight.",
        ),
        TransactionEvent(
            group_id=knight_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=knight.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=knight_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=KNIGHT_ESTIME_AT, source_id=knight_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=knight_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=knight.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=KNIGHT_ESTIME_AT, source_id=knight_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=knight_group.id,
            notes="ESPN free add $0 dropping Audric Estime.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=knight.id,
            slot="BN", placement="BENCH", effective_at=KNIGHT_ESTIME_AT, source_id=knight_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=KNIGHT_ESTIME_AT, source_id=knight_source.id,
    ))

    # --- 2026-10-22 ESPN: FREE_AGENT ADD Dontayvion Wicks $0 / DROP Jaleel McLaughlin ---
    wicks_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jaleel McLaughlin")))
    wicks = _player(session, "Dontayvion Wicks", "WR", "PHI")
    if wicks.espn_id is None:
        wicks.espn_id = "4428850"  # from ESPN API transaction log / roster snapshot 2026-10-22T22:27Z
    wicks_source = Source(
        league_id=lg.id,
        source_type="ESPN_API_TRANSACTION",
        description="ESPN transaction log (read-only API) 3837d910-ec8e-46c5-8840-caf565b76586 FREEAGENT EXECUTED: added Dontayvion Wicks (PHI WR) for $0; dropped Jaleel McLaughlin (CLE RB) (Thu Oct 22, 6:26:17 pm ET)",
        original_ref="data/imports/2026-10-22-dontayvion-wicks-add-mclaughlin-drop.json",
        platform="ESPN",
        observed_at=WICKS_MCLAUGHLIN_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="ESPN API snapshot data/espn_api/2026-10-22T2227Z.json (observed 2026-10-22T22:27:33Z); FAAB remained $66; espn_id 4428850 from ESPN data.",
    )
    session.add(wicks_source)
    session.flush()
    wicks_group = TransactionGroup(
        id="dontayvion-wicks-add-mclaughlin-drop-20261022-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=WICKS_MCLAUGHLIN_AT, source_id=wicks_source.id,
        notes="ESPN-authoritative ADD_DROP: Dontayvion Wicks $0 free add; Jaleel McLaughlin dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(wicks_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=wicks_group.id, sequence=1, event_type="DROP", player_id=wicks_drop.id,
            notes="Dropped when adding Dontayvion Wicks.",
        ),
        TransactionEvent(
            group_id=wicks_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=wicks.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=wicks_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=WICKS_MCLAUGHLIN_AT, source_id=wicks_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=wicks_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=wicks.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=WICKS_MCLAUGHLIN_AT, source_id=wicks_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=wicks_group.id,
            notes="ESPN free add $0 dropping Jaleel McLaughlin.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=wicks.id,
            slot="BN", placement="BENCH", effective_at=WICKS_MCLAUGHLIN_AT, source_id=wicks_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=WICKS_MCLAUGHLIN_AT, source_id=wicks_source.id,
    ))

    # --- 2026-10-22 ESPN: FREE_AGENT ADD Juwan Johnson $0 / DROP Jacob Cowing ---
    juwan_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jacob Cowing")))
    juwan = _player(session, "Juwan Johnson", "TE", "NO")
    if juwan.espn_id is None:
        juwan.espn_id = "3929645"  # from ESPN API transaction log / roster snapshot 2026-10-22T22:27Z
    juwan_source = Source(
        league_id=lg.id,
        source_type="ESPN_API_TRANSACTION",
        description="ESPN transaction log (read-only API) 80e3ffe7-2097-4182-86c7-c8a4e0e4a38e FREEAGENT EXECUTED: added Juwan Johnson (NO TE) for $0; dropped Jacob Cowing (SF WR) (Thu Oct 22, 6:26:31 pm ET)",
        original_ref="data/imports/2026-10-22-juwan-johnson-add-cowing-drop.json",
        platform="ESPN",
        observed_at=JOHNSON_COWING_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="ESPN API snapshot data/espn_api/2026-10-22T2227Z.json (observed 2026-10-22T22:27:33Z); FAAB remained $66; espn_id 3929645 from ESPN data.",
    )
    session.add(juwan_source)
    session.flush()
    juwan_group = TransactionGroup(
        id="juwan-johnson-add-cowing-drop-20261022-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=JOHNSON_COWING_AT, source_id=juwan_source.id,
        notes="ESPN-authoritative ADD_DROP: Juwan Johnson $0 free add; Jacob Cowing dropped (not FREE_AGENT_CONFIRMED).",
    )
    session.add(juwan_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=juwan_group.id, sequence=1, event_type="DROP", player_id=juwan_drop.id,
            notes="Dropped when adding Juwan Johnson.",
        ),
        TransactionEvent(
            group_id=juwan_group.id, sequence=2, event_type="FREE_AGENT_ADD", player_id=juwan.id,
            faab_amount=Decimal("0"), notes="Free add $0.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=juwan_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=JOHNSON_COWING_AT, source_id=juwan_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=juwan_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=juwan.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
            event_type="ADDED", effective_at=JOHNSON_COWING_AT, source_id=juwan_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=juwan_group.id,
            notes="ESPN free add $0 dropping Jacob Cowing.",
        ),
        LineupAssignment(
            league_id=lg.id, season=2026, week=2, fantasy_team_id=tm.id, player_id=juwan.id,
            slot="BN", placement="BENCH", effective_at=JOHNSON_COWING_AT, source_id=juwan_source.id,
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=JOHNSON_COWING_AT, source_id=juwan_source.id,
    ))

    # --- 2026-10-25 ESPN: DROP Dontayvion Wicks (plain drop, no add) ---
    wicks_plain_drop = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Dontayvion Wicks")))
    wicks_drop_source = Source(
        league_id=lg.id,
        source_type="ESPN_ACTIVITY",
        description="Authenticated ESPN activity: Dropped Dontayvion Wicks, PHI WR (Sun Oct 25, 8:50 am)",
        original_ref="data/imports/2026-10-25-dontayvion-wicks-drop.json",
        platform="ESPN",
        observed_at=WICKS_DROP_AT,
        authority=Authority.CONFIRMED_TRANSACTION,
        notes="ESPN activity read ~12:56 pm ET 2026-10-25; corroborated by ESPN API snapshot data/espn_api/2026-10-25T1456Z.json "
              "(observed 2026-10-25T14:56:01Z, Wicks absent, 16 players). Plain drop is an ESPN ROSTER-type transaction not "
              "captured in transactions.json (no transaction id); minute precision. FAAB remained $66; no paired add.",
    )
    session.add(wicks_drop_source)
    session.flush()
    wicks_drop_group = TransactionGroup(
        id="dontayvion-wicks-drop-20261025-espn-001", league_id=lg.id, fantasy_team_id=tm.id,
        effective_at=WICKS_DROP_AT, source_id=wicks_drop_source.id,
        notes="ESPN-authoritative DROP of Dontayvion Wicks; ownership ends (not FREE_AGENT_CONFIRMED).",
    )
    session.add(wicks_drop_group)
    session.flush()
    session.add_all([
        TransactionEvent(
            group_id=wicks_drop_group.id, sequence=1, event_type="DROP", player_id=wicks_plain_drop.id,
            notes="Dropped from roster per ESPN activity Sun Oct 25, 8:50 am ET.",
        ),
        OwnershipEvent(
            league_id=lg.id, player_id=wicks_plain_drop.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=WICKS_DROP_AT, source_id=wicks_drop_source.id,
            authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=wicks_drop_group.id,
            notes="Drop proves departure from roster, not current free agency.",
        ),
    ])
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("66"),
        observed_at=WICKS_DROP_AT, source_id=wicks_drop_source.id,
    ))

    for name, pos in NOT_MINE_UNKNOWN:
        p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name(name)))
        session.add(OwnershipEvent(
            league_id=lg.id, player_id=p.id, state=OwnershipState.UNKNOWN,
            event_type="MANUAL_CORRECTION", effective_at=AS_OF, source_id=src.id,
            authority=Authority.MANUAL_CORRECTION,
            notes="Confirmed not on user's roster; league ownership not established.",
        ))

    session.add(ReconciliationIssue(
        league_id=lg.id, category="MISSING_DRAFT_DATA",
        details={"missing": "Complete 2026 Mongo auction results and all teams; ESPN evidence did not include auction prices"},
    ))
    session.add(ReconciliationIssue(
        league_id=lg.id, category="MISSING_PLAYER_ESPN_IDS",
        details={
            "status": "RECONCILIATION HELD",
            "reason": "Authenticated ESPN evidence did not include numeric player espn_id values; do not invent IDs",
            "field": "nfl_players.espn_id",
        },
    ))
    session.add(FaabBalanceObservation(
        league_id=lg.id, fantasy_team_id=tm.id, balance=Decimal("94"), observed_at=AS_OF, source_id=src.id,
    ))

    # Name aliases for ESPN/alternate spellings (no new ownership).
    for canonical, alias in [
        ("Ja'Kobi Lane", "Jakobi Lane"),
        ("Eagles D/ST", "Eagles"),
        ("Packers D/ST", "Packers"),
        ("Raiders D/ST", "Raiders"),
        ("Saints D/ST", "Saints"),
        ("De'Von Achane", "Devon Achane"),
    ]:
        p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name(canonical)))
        if not p:
            continue
        norm_alias = normalize_name(alias)
        existing_alias = session.scalar(select(PlayerAlias).where(PlayerAlias.normalized_alias == norm_alias))
        if existing_alias:
            continue
        # Skip if alias normalizes to the same key as the canonical player row.
        if norm_alias == p.normalized_name:
            continue
        session.add(PlayerAlias(player_id=p.id, alias=alias, normalized_alias=norm_alias))

    session.flush()
    rebuild_state(session, "mongo")