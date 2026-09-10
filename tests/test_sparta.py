from decimal import Decimal
from sqlalchemy import func, select
from ffdb.models import Draft, DraftPick, FantasyTeam, OwnershipState
from ffdb.sparta_draft import SPARTA_2026_DRAFT
from ffdb.sparta_seed import CURRENT_ROSTER, KNOWN_OWNED_ELSEWHERE
from ffdb.services import faab_balance, ownership, roster, validate


def test_sparta_seed_roster_is_exact(session):
    actual={p.canonical_name for p,_ in roster(session,"sparta")}; expected={name for name,_ in CURRENT_ROSTER}
    assert actual==expected; assert len(actual)==17; assert faab_balance(session,"sparta")==Decimal("100.00"); assert validate(session,"sparta")==[]


def test_full_aug30_board_imported(session):
    draft=session.scalar(select(Draft).where(Draft.name.like("Billy's 2026 Sparta Auction%")))
    assert draft is not None
    assert session.scalar(select(func.count()).select_from(DraftPick).where(DraftPick.draft_id==draft.id))==204
    for code, expected in SPARTA_2026_DRAFT.items():
        tm=session.scalar(select(FantasyTeam).where(FantasyTeam.league_id==draft.league_id, FantasyTeam.slug==code.lower()))
        assert session.scalar(select(func.count()).select_from(DraftPick).where(DraftPick.draft_id==draft.id,DraftPick.fantasy_team_id==tm.id))==17
        assert session.scalar(select(func.sum(DraftPick.auction_price)).where(DraftPick.draft_id==draft.id,DraftPick.fantasy_team_id==tm.id))==sum(Decimal(str(x[1])) for x in expected)


def test_sparta_latest_transactions_are_reflected(session):
    actual={p.canonical_name for p,_ in roster(session,"sparta")}
    for name in ["Michael Mayer","Caleb Douglas","Malachi Fields","Jets D/ST"]: assert name in actual
    for name in ["Dalton Schultz","Pat Bryant","Malik Willis","Devin Neal","Kendre Miller","Ravens D/ST"]: assert name not in actual
    assert ownership(session,"sparta","Ravens D/ST").state==OwnershipState.UNKNOWN


def test_sparta_known_owned_players_are_never_free_agents(session):
    for name,team_code in KNOWN_OWNED_ELSEWHERE.items():
        row=ownership(session,"sparta",name); assert row is not None; assert row.state==OwnershipState.OWNED; assert row.fantasy_team_id is not None


def test_sparta_specific_false_positive_guards(session):
    for name in ["Dylan Sampson","Ka'imi Fairbairn","Keenan Allen"]: assert ownership(session,"sparta",name).state==OwnershipState.OWNED


def test_shared_player_identity_does_not_share_league_ownership(session):
    mongo=ownership(session,"mongo","Jalen Hurts"); sparta=ownership(session,"sparta","Jalen Hurts")
    assert mongo.state==OwnershipState.OWNED; assert sparta.state==OwnershipState.OWNED; assert mongo.fantasy_team_id!=sparta.fantasy_team_id


def test_sparta_unknown_candidate_is_not_implicitly_free_agent(session):
    assert ownership(session,"sparta","Browns D/ST") is None
