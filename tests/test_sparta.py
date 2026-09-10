from decimal import Decimal

from ffdb.models import OwnershipState
from ffdb.sparta_seed import CURRENT_ROSTER, KNOWN_OWNED_ELSEWHERE
from ffdb.services import faab_balance, ownership, roster, validate


def test_sparta_seed_roster_is_exact(session):
    actual = {p.canonical_name for p, _ in roster(session, "sparta")}
    expected = {name for name, _ in CURRENT_ROSTER}
    assert actual == expected
    assert len(actual) == len(CURRENT_ROSTER)
    assert faab_balance(session, "sparta") == Decimal("100.00")
    assert validate(session, "sparta") == []


def test_sparta_latest_transactions_are_reflected(session):
    actual = {p.canonical_name for p, _ in roster(session, "sparta")}
    assert "Michael Mayer" in actual
    assert "Caleb Douglas" in actual
    assert "Malachi Fields" in actual
    assert "Jets D/ST" in actual
    assert "Dalton Schultz" not in actual
    assert "Pat Bryant" not in actual
    assert "Malik Willis" not in actual


def test_sparta_known_owned_players_are_never_free_agents(session):
    for name, team_code in KNOWN_OWNED_ELSEWHERE.items():
        row = ownership(session, "sparta", name)
        assert row is not None
        assert row.state == OwnershipState.OWNED
        assert row.fantasy_team_id is not None


def test_sparta_specific_false_positive_guards(session):
    for name in ["Dylan Sampson", "Ka'imi Fairbairn", "Keenan Allen"]:
        assert ownership(session, "sparta", name).state == OwnershipState.OWNED


def test_shared_player_identity_does_not_share_league_ownership(session):
    # Jalen Hurts exists once in the NFL player universe but ownership is resolved per league.
    mongo = ownership(session, "mongo", "Jalen Hurts")
    sparta = ownership(session, "sparta", "Jalen Hurts")
    assert mongo.state == OwnershipState.OWNED
    assert sparta.state == OwnershipState.OWNED
    assert mongo.fantasy_team_id != sparta.fantasy_team_id


def test_sparta_unknown_candidate_is_not_implicitly_free_agent(session):
    # A player with no Sparta ownership event must not be treated as confirmed available.
    row = ownership(session, "sparta", "Browns D/ST")
    assert row is None
