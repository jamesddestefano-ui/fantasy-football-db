from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from ffdb.models import (Authority, CurrentOwnership, FantasyTeam, League, NFLPlayer, NewsItem,
    OwnershipEvent, OwnershipState, Source)
from ffdb.names import normalize_name
from ffdb.seed import ROSTER
from ffdb.services import DomainError, add_drop, faab_balance, ownership, rebuild_state, roster, validate

def test_seed_roster_is_exact(session):
    actual = {p.canonical_name for p, _ in roster(session, "mongo")}
    assert actual == {r[0] for r in ROSTER}
    assert len(actual) == 16
    assert faab_balance(session, "mongo") == Decimal("94.00")
    assert validate(session, "mongo") == []

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
    sparta = League(slug="sparta-test", name="Synthetic isolation test", season=2026, settings={}); session.add(sparta); session.flush()
    other = FantasyTeam(league_id=sparta.id, slug="other", name="Synthetic Other"); session.add(other); session.flush()
    src = Source(league_id=sparta.id, source_type="OTHER", description="synthetic test only", observed_at=datetime.now(timezone.utc), authority=Authority.OTHER_SNAPSHOT); session.add(src); session.flush()
    session.add(OwnershipEvent(league_id=sparta.id, player_id=p.id, fantasy_team_id=other.id, state=OwnershipState.OWNED,
        event_type="OWNERSHIP_SNAPSHOT", effective_at=datetime.now(timezone.utc), source_id=src.id, authority=Authority.OTHER_SNAPSHOT)); session.flush(); rebuild_state(session, "sparta-test")
    assert ownership(session, "mongo", "Kendre Miller").fantasy_team_id != ownership(session, "sparta-test", "Kendre Miller").fantasy_team_id

def test_news_never_changes_ownership(session):
    before = ownership(session, "mongo", "Browns D/ST").winning_event_id
    lg = session.scalar(select(League).where(League.slug == "mongo")); p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name("Browns D/ST")))
    src = Source(league_id=lg.id, source_type="FANTASY_ANALYSIS", description="waiver article", authority=Authority.NON_OWNERSHIP); session.add(src); session.flush()
    session.add(NewsItem(player_id=p.id, league_id=lg.id, category="WAIVER_ANALYSIS", headline="Add them", source_id=src.id)); session.flush(); rebuild_state(session, "mongo")
    assert ownership(session, "mongo", "Browns D/ST").winning_event_id == before

