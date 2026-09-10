from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Authority, Draft, DraftPick, FaabBalanceObservation, FantasyTeam, League, Manager, NFLPlayer, OwnershipEvent, OwnershipState, ReconciliationIssue, Source
from .names import normalize_name
from .services import rebuild_state
from .sparta_draft import SPARTA_2026_DRAFT

DRAFT_AT = datetime(2026, 8, 30, 19, 16, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 10, 18, 30, tzinfo=timezone.utc)
CURRENT_ROSTER = [
("Jalen Hurts","QB"),("Quinshon Judkins","RB"),("Rhamondre Stevenson","RB"),("J.K. Dobbins","RB"),("Malik Davis","RB"),("Ja'Marr Chase","WR"),("Jaxon Smith-Njigba","WR"),("Tetairoa McMillan","WR"),("Xavier Worthy","WR"),("Dontayvion Wicks","WR"),("Ja'Kobi Lane","WR"),("Devaughn Vele","WR"),("Caleb Douglas","WR"),("Malachi Fields","WR"),("Michael Mayer","TE"),("Evan McPherson","K"),("Jets D/ST","D/ST")]
KNOWN_OWNED_ELSEWHERE = {"Jacob Saylors":"SR","Emmett Johnson":"ANT","Najee Harris":"VV","Juwan Johnson":"MN","George Holani":"JU","Dylan Sampson":"VV","Keaton Mitchell":"MN","Kaelon Black":"TM","Kaleb Johnson":"VV","Terrance Ferguson":"JU","Brenton Strange":"JP","Greg Dulcich":"MN","Kayshon Boutte":"ANT","MarShawn Lloyd":"SR","Mike Washington Jr.":"BE","Ka'imi Fairbairn":"JP","Cyrus Allen":"VV","Chris Bell":"MC","Tre Tucker":"JU","Jonah Coleman":"SR","Samaje Perine":"SR","Hunter Henry":"SR","T.J. Hockenson":"SR","Denzel Boston":"ME","Adonai Mitchell":"JP","Keenan Allen":"ME"}
TEAM_CODES = list(SPARTA_2026_DRAFT.keys())
TEAM_NAMES = {
    "BE": "The Showstoppers",
    "MN": "MattyBad",
    "TM": "Dynamic Duo of Lad and Strips",
    "VV": "Focus",
    "MC": "Clinton Portis",
    "ANT": "Amon A-Roll",
    "JU": "The U",
    "JD": "TB12 of Ass",
    "SR": "King Kong",
    "JP": "X-Factor",
    "ME": "Brown Rice and Craft",
    "MM": "Pablo Pledge-Scabars",
}

def _player(session: Session, name: str, position: str | None = None) -> NFLPlayer:
    normalized = normalize_name(name); p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalized))
    if p is None:
        p = NFLPlayer(canonical_name=name, normalized_name=normalized, position=position); session.add(p); session.flush()
    elif position and not p.position: p.position = position
    return p

def seed_sparta(session: Session) -> None:
    if session.scalar(select(League).where(League.slug == "sparta")): return
    league = League(slug="sparta", name="Billy's 2026 Sparta League", platform="Yahoo", season=2026, settings={"teams":12,"scoring":"Full PPR","auction_budget":200,"faab_budget":100,"faab_is_real_money":True,"free_pickups_through_week":1,"draft_date":"2026-08-30","roster_size":17})
    manager = Manager(name="James DeStefano", aliases=["James","JD"]); session.add_all([league,manager]); session.flush()
    teams = {}
    for code in TEAM_CODES:
        aliases = [code]
        if code == "JD": aliases += ["JD", "James", "me", "TB12 of Ass"]
        tm = FantasyTeam(league_id=league.id, manager_id=manager.id if code=="JD" else None, slug=code.lower(), name=TEAM_NAMES[code], aliases=aliases, is_mine=(code=="JD")); session.add(tm); teams[code]=tm
    session.flush()
    draft_source = Source(league_id=league.id, source_type="DRAFT_BOARD_SCREENSHOTS", description="Authoritative Aug. 30, 2026 Sparta full auction board supplied by user in two screenshots", platform="Sparta/Yahoo", observed_at=DRAFT_AT, authority=Authority.DRAFT, notes="All 12 board columns transcribed; 17 players per team. Displayed auction prices preserved exactly.")
    roster_source = Source(league_id=league.id, source_type="USER_CONFIRMATION", description="Authoritative current Sparta roster confirmed by user through Sept. 9, 2026", platform="ChatGPT/Yahoo screenshots", observed_at=AS_OF, authority=Authority.MANUAL_CORRECTION)
    ownership_source = Source(league_id=league.id, source_type="USER_OWNERSHIP_CORRECTIONS", description="Subsequent Sparta ownership corrections supplied by user after draft", platform="ChatGPT", observed_at=AS_OF, authority=Authority.MANUAL_CORRECTION)
    session.add_all([draft_source,roster_source,ownership_source]); session.flush()
    draft = Draft(league_id=league.id, name="Billy's 2026 Sparta Auction — Aug. 30, 2026", source_id=draft_source.id); session.add(draft); session.flush()
    for code, rows in SPARTA_2026_DRAFT.items():
        for name, price in rows:
            p=_player(session,name); session.add(DraftPick(draft_id=draft.id, player_id=p.id, fantasy_team_id=teams[code].id, nomination_order=None, auction_price=Decimal(str(price)), source_id=draft_source.id)); session.add(OwnershipEvent(league_id=league.id, player_id=p.id, fantasy_team_id=teams[code].id, state=OwnershipState.OWNED, event_type="DRAFTED", effective_at=DRAFT_AT, source_id=draft_source.id, authority=Authority.DRAFT))
    current_names={name for name,_ in CURRENT_ROSTER}
    for name, position in CURRENT_ROSTER:
        p=_player(session,name,position); session.add(OwnershipEvent(league_id=league.id, player_id=p.id, fantasy_team_id=teams["JD"].id, state=OwnershipState.OWNED, event_type="CURRENT_ROSTER_SNAPSHOT", effective_at=AS_OF, source_id=roster_source.id, authority=Authority.MANUAL_CORRECTION))
    for name,_ in SPARTA_2026_DRAFT["JD"]:
        if name not in current_names:
            p=_player(session,name); session.add(OwnershipEvent(league_id=league.id, player_id=p.id, state=OwnershipState.UNKNOWN, event_type="ABSENT_FROM_CURRENT_ROSTER", effective_at=AS_OF, source_id=roster_source.id, authority=Authority.CURRENT_ROSTER, notes="Not on confirmed current JD roster; present league ownership/free-agent status not inferred."))
    for name,team_code in KNOWN_OWNED_ELSEWHERE.items():
        p=_player(session,name); session.add(OwnershipEvent(league_id=league.id, player_id=p.id, fantasy_team_id=teams[team_code].id, state=OwnershipState.OWNED, event_type="OWNERSHIP_CORRECTION", effective_at=AS_OF, source_id=ownership_source.id, authority=Authority.MANUAL_CORRECTION, explicit_override=True))
    session.add(FaabBalanceObservation(league_id=league.id, fantasy_team_id=teams["JD"].id, balance=Decimal("100"), observed_at=AS_OF, source_id=roster_source.id))
    session.add(ReconciliationIssue(league_id=league.id, category="DRAFT_TO_CURRENT_TRANSACTION_HISTORY", details={"known":["Devin Neal -> Malik Davis","Kendre Miller -> Evan McPherson","Pat Bryant -> Caleb Douglas","Malik Willis -> Malachi Fields","Dalton Schultz -> Michael Mayer","Jets D/ST added"],"missing":"Exact event timestamps/intermediate moves and Ravens D/ST disposition. Draft and current snapshots are preserved; do not invent the missing chain."}))
    session.flush(); rebuild_state(session,"sparta")
