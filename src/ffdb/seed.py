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