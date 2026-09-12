from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from ffdb.models import (Authority, CurrentOwnership, FaabEntry, FantasyTeam, League, LineupAssignment, NFLPlayer, NewsItem,
    OwnershipEvent, OwnershipState, ReconciliationIssue, Source, TransactionEvent, TransactionGroup)
from ffdb.names import normalize_name
from ffdb.seed import ROSTER
from ffdb.services import DomainError, add_drop, faab_balance, ownership, rebuild_state, roster, validate

def test_seed_roster_is_exact(session):
    actual = {p.canonical_name for p, _ in roster(session, "mongo")}
    assert actual == {r[0] for r in ROSTER} | {"Emari Demercado"}
    assert len(actual) == 17
    assert faab_balance(session, "mongo") == Decimal("94.00")
    assert validate(session, "mongo") == []

def test_league_settings_include_espn_ids_scoring_and_faab_budget(session):
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    assert lg.settings["espn_league_id"] == "1470431049"
    assert lg.settings["espn_team_id"] == 2
    assert lg.settings["passing_int"] == -2
    assert lg.settings["passing_td"] == 6
    assert lg.settings["passing_yards_per_point"] == 25
    assert lg.settings["kicker"] is False
    assert lg.settings["faab_budget"] == 100
    assert lg.settings["roster_slots"] == {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 2, "D/ST": 1, "BN": 7, "IR": 1,
    }

def test_faab_history_explains_100_to_94_via_saylors_claim(session):
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    tm = session.scalar(select(FantasyTeam).where(FantasyTeam.league_id == lg.id, FantasyTeam.is_mine.is_(True)))
    opening = session.scalar(select(FaabEntry).where(
        FaabEntry.league_id == lg.id, FaabEntry.fantasy_team_id == tm.id, FaabEntry.kind == "OPENING_BUDGET",
    ))
    assert opening.amount == Decimal("100.00")
    saylors = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Jacob Saylors")))
    claim = session.scalar(select(TransactionEvent).where(
        TransactionEvent.player_id == saylors.id, TransactionEvent.event_type == "WAIVER_ADD",
    ))
    assert claim.faab_amount == Decimal("6.00")
    debit = session.scalar(select(FaabEntry).where(
        FaabEntry.league_id == lg.id, FaabEntry.kind == "WAIVER_EXPENDITURE",
        FaabEntry.transaction_group_id == claim.group_id,
    ))
    assert debit.amount == Decimal("-6.00")
    assert faab_balance(session, "mongo") == Decimal("94.00")

def test_historical_transactions_are_seeded_without_changing_current_roster(session):
    actual = {p.canonical_name for p, _ in roster(session, "mongo")}
    assert "Kaelon Black" in actual and "Tre Tucker" in actual
    assert "Ja'Kobi Lane" in actual and "Malik Davis" in actual
    assert "Jacob Saylors" not in actual and "Kayshon Boutte" not in actual
    assert "Nicholas Singleton" not in actual
    assert session.scalar(select(TransactionGroup).where(TransactionGroup.id == "black-add-lane-drop-20260903-001"))
    assert session.scalar(select(TransactionGroup).where(TransactionGroup.id == "tucker-add-singleton-drop-20260903-001"))
    assert session.scalar(select(TransactionGroup).where(TransactionGroup.id == "lane-add-boutte-drop-20260908-001"))
    assert session.scalar(select(TransactionGroup).where(TransactionGroup.id == "malik-add-saylors-drop-20260908-001"))
    assert session.scalar(select(TransactionGroup).where(TransactionGroup.id == "saylors-waiver-20260903-faab6-001"))
    # ESPN live: Sep 3 Black/Tucker were ADD_DROP, not bare free adds.
    black_events = {e.event_type for e in session.scalars(select(TransactionEvent).where(TransactionEvent.group_id == "black-add-lane-drop-20260903-001"))}
    tucker_events = {e.event_type for e in session.scalars(select(TransactionEvent).where(TransactionEvent.group_id == "tucker-add-singleton-drop-20260903-001"))}
    assert black_events == {"DROP", "FREE_AGENT_ADD"}
    assert tucker_events == {"DROP", "FREE_AGENT_ADD"}

def test_open_reconciliation_issues_are_draft_and_player_espn_ids(session):
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    open_issues = session.scalars(select(ReconciliationIssue).where(
        ReconciliationIssue.league_id == lg.id, ReconciliationIssue.status == "OPEN",
    )).all()
    cats = {i.category for i in open_issues}
    assert cats == {"MISSING_DRAFT_DATA", "MISSING_PLAYER_ESPN_IDS"}
    assert not any(i.category == "MISSING_TRANSACTION_HISTORY" for i in open_issues)

def test_malik_davis_is_owned_and_in_ir(session):
    current = ownership(session, "mongo", "Malik Davis")
    assert current.state == OwnershipState.OWNED
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    malik = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Malik Davis")))
    assignment = session.scalar(select(LineupAssignment).where(
        LineupAssignment.league_id == lg.id,
        LineupAssignment.player_id == malik.id,
        LineupAssignment.season == 2026,
        LineupAssignment.week == 1,
    ))
    assert assignment.slot == "IR"
    assert assignment.placement == "IR"
    move = session.scalar(select(TransactionEvent).where(
        TransactionEvent.player_id == malik.id,
        TransactionEvent.event_type == "IR_MOVE",
    ))
    assert move is not None

def test_demercado_free_add_is_owned_on_bench_without_faab_debit(session):
    current = ownership(session, "mongo", "Emari Demercado")
    assert current.state == OwnershipState.OWNED
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    demercado = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Emari Demercado")))
    assignment = session.scalar(select(LineupAssignment).where(
        LineupAssignment.league_id == lg.id,
        LineupAssignment.player_id == demercado.id,
        LineupAssignment.season == 2026,
        LineupAssignment.week == 1,
    ))
    assert assignment.slot == "BN"
    assert assignment.placement == "BENCH"
    add = session.scalar(select(TransactionEvent).where(
        TransactionEvent.player_id == demercado.id,
        TransactionEvent.event_type == "FREE_AGENT_ADD",
    ))
    assert add.faab_amount == Decimal("0.00")
    assert faab_balance(session, "mongo") == Decimal("94.00")

def test_not_mine_is_unknown_not_free_agent(session):
    for name in ["Browns D/ST", "Nicholas Singleton", "Kayshon Boutte", "Jacob Saylors"]:
        assert ownership(session, "mongo", name).state == OwnershipState.UNKNOWN

def test_rebuild_reproduces_roster(session):
    before = {p.canonical_name for p, _ in roster(session, "mongo")}
    session.query(CurrentOwnership).delete(); session.flush()
    rebuild_state(session, "mongo")
    assert {p.canonical_name for p, _ in roster(session, "mongo")} == before

def test_atomic_add_drop_preserves_drop_as_unknown_and_debits_faab(session):
    lg = session.scalar(select(League).where(League.slug == "mongo"))
    p = NFLPlayer(canonical_name="Player X", normalized_name="player x", position="RB"); session.add(p); session.flush()
    src = Source(league_id=lg.id, source_type="USER_CONFIRMATION", description="test completed transaction",
        observed_at=datetime.now(timezone.utc), authority=Authority.CONFIRMED_TRANSACTION); session.add(src); session.flush()
    add_drop(session, "mongo", "mine", "Kendre Miller", "Player X", Decimal("4"), src.id)
    assert ownership(session, "mongo", "Kendre Miller").state == OwnershipState.UNKNOWN
    assert ownership(session, "mongo", "Player X").state == OwnershipState.OWNED
    assert faab_balance(session, "mongo") == Decimal("90.00")
    assert validate(session, "mongo") == []

def test_add_owned_elsewhere_is_rejected_atomically(session):
    lg = session.scalar(select(League).where(League.slug == "mongo")); tm = FantasyTeam(league_id=lg.id, slug="other", name="Other")
    p = NFLPlayer(canonical_name="Owned Elsewhere", normalized_name="owned elsewhere", position="RB"); session.add_all([tm, p]); session.flush()
    src = Source(league_id=lg.id, source_type="ESPN_EXPORT", description="test", observed_at=datetime.now(timezone.utc), authority=Authority.ESPN_CURRENT); session.add(src); session.flush()
    session.add(OwnershipEvent(league_id=lg.id, player_id=p.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED,
        event_type="OWNERSHIP_SNAPSHOT", effective_at=datetime.now(timezone.utc), source_id=src.id, authority=Authority.ESPN_CURRENT)); session.flush(); rebuild_state(session, "mongo")
    with pytest.raises(DomainError): add_drop(session, "mongo", "mine", "Kendre Miller", "Owned Elsewhere", Decimal("0"), src.id)

def test_league_namespace_isolation(session):
    mongo = session.scalar(select(League).where(League.slug == "mongo")); p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Kendre Miller")))
    other_league = League(slug="isolation-test", name="Synthetic isolation test", season=2026, settings={}); session.add(other_league); session.flush()
    other = FantasyTeam(league_id=other_league.id, slug="other", name="Synthetic Other"); session.add(other); session.flush()
    src = Source(league_id=other_league.id, source_type="OTHER", description="synthetic test only", observed_at=datetime.now(timezone.utc), authority=Authority.OTHER_SNAPSHOT); session.add(src); session.flush()
    session.add(OwnershipEvent(league_id=other_league.id, player_id=p.id, fantasy_team_id=other.id, state=OwnershipState.OWNED,
        event_type="OWNERSHIP_SNAPSHOT", effective_at=datetime.now(timezone.utc), source_id=src.id, authority=Authority.OTHER_SNAPSHOT)); session.flush(); rebuild_state(session, "isolation-test")
    assert ownership(session, "mongo", "Kendre Miller").fantasy_team_id != ownership(session, "isolation-test", "Kendre Miller").fantasy_team_id

def test_news_never_changes_ownership(session):
    before = ownership(session, "mongo", "Browns D/ST").winning_event_id
    lg = session.scalar(select(League).where(League.slug == "mongo")); p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Browns D/ST")))
    src = Source(league_id=lg.id, source_type="FANTASY_ANALYSIS", description="waiver article", authority=Authority.NON_OWNERSHIP); session.add(src); session.flush()
    session.add(NewsItem(player_id=p.id, league_id=lg.id, category="WAIVER_ANALYSIS", headline="Add them", source_id=src.id)); session.flush(); rebuild_state(session, "mongo")
    assert ownership(session, "mongo", "Browns D/ST").winning_event_id == before
