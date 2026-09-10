from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Authority, FantasyTeam, League, Manager, NFLPlayer, OwnershipEvent, OwnershipState, Source
from .names import normalize_name
from .services import rebuild_state

AS_OF = datetime(2026, 9, 10, 18, 30, tzinfo=timezone.utc)

# Current JD roster confirmed through Sept. 9, 2026 transactions.
CURRENT_ROSTER = [
    ("Jalen Hurts", "QB"),
    ("Quinshon Judkins", "RB"),
    ("Rhamondre Stevenson", "RB"),
    ("J.K. Dobbins", "RB"),
    ("Malik Davis", "RB"),
    ("Ja'Marr Chase", "WR"),
    ("Jaxon Smith-Njigba", "WR"),
    ("Tetairoa McMillan", "WR"),
    ("Xavier Worthy", "WR"),
    ("Dontayvion Wicks", "WR"),
    ("Ja'Kobi Lane", "WR"),
    ("Devaughn Vele", "WR"),
    ("Caleb Douglas", "WR"),
    ("Malachi Fields", "WR"),
    ("Michael Mayer", "TE"),
    ("Evan McPherson", "K"),
    ("Jets D/ST", "D/ST"),
]

# Ownership corrections that must block false free-agent recommendations.
KNOWN_OWNED_ELSEWHERE = {
    "Jacob Saylors": "SR",
    "Emmett Johnson": "ANT",
    "Najee Harris": "VV",
    "Juwan Johnson": "MN",
    "George Holani": "JU",
    "Dylan Sampson": "VV",
    "Keaton Mitchell": "MN",
    "Kaelon Black": "TM",
    "Kaleb Johnson": "VV",
    "Terrance Ferguson": "JU",
    "Brenton Strange": "JP",
    "Greg Dulcich": "MN",
    "Kayshon Boutte": "ANT",
    "MarShawn Lloyd": "SR",
    "Mike Washington Jr.": "BE",
    "Ka'imi Fairbairn": "JP",
    "Cyrus Allen": "VV",
    "Chris Bell": "MC",
    "Tre Tucker": "JU",
    "Jonah Coleman": "SR",
    "Samaje Perine": "SR",
    "Hunter Henry": "SR",
    "T.J. Hockenson": "SR",
    "Denzel Boston": "ME",
    "Adonai Mitchell": "JP",
    "Keenan Allen": "ME",
}

TEAM_CODES = sorted(set(KNOWN_OWNED_ELSEWHERE.values()) | {"JD"})


def _player(session: Session, name: str, position: str | None = None) -> NFLPlayer:
    normalized = normalize_name(name)
    p = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalized))
    if p is None:
        p = NFLPlayer(canonical_name=name, normalized_name=normalized, position=position)
        session.add(p)
        session.flush()
    elif position and not p.position:
        p.position = position
    return p


def seed_sparta(session: Session) -> None:
    """Seed authoritative current Sparta state without contaminating Mongo state."""
    if session.scalar(select(League).where(League.slug == "sparta")):
        return

    league = League(
        slug="sparta",
        name="Billy's 2026 Sparta League",
        platform="Yahoo",
        season=2026,
        settings={
            "teams": 12,
            "scoring": "Full PPR",
            "auction_budget": 200,
            "faab_budget": 100,
            "faab_is_real_money": True,
            "free_pickups_through_week": 1,
            "draft_date": "2026-08-30",
        },
    )
    manager = Manager(name="James DeStefano", aliases=["James", "JD"])
    session.add_all([league, manager])
    session.flush()

    teams: dict[str, FantasyTeam] = {}
    for code in TEAM_CODES:
        team = FantasyTeam(
            league_id=league.id,
            manager_id=manager.id if code == "JD" else None,
            slug=code.lower(),
            name=code,
            aliases=[code],
            is_mine=(code == "JD"),
        )
        session.add(team)
        teams[code] = team
    session.flush()

    roster_source = Source(
        league_id=league.id,
        source_type="USER_CONFIRMATION",
        description="Authoritative current Sparta roster confirmed by user through Sept. 9, 2026",
        platform="ChatGPT/Yahoo screenshots",
        observed_at=AS_OF,
        authority=Authority.MANUAL_CORRECTION,
    )
    ownership_source = Source(
        league_id=league.id,
        source_type="DRAFT_BOARD_AND_USER_CORRECTIONS",
        description="Known Sparta ownership from Aug. 30 draft board plus subsequent user corrections",
        platform="Sparta draft board",
        observed_at=AS_OF,
        authority=Authority.MANUAL_CORRECTION,
    )
    session.add_all([roster_source, ownership_source])
    session.flush()

    for name, position in CURRENT_ROSTER:
        p = _player(session, name, position)
        session.add(OwnershipEvent(
            league_id=league.id,
            player_id=p.id,
            fantasy_team_id=teams["JD"].id,
            state=OwnershipState.OWNED,
            event_type="CURRENT_ROSTER_SNAPSHOT",
            effective_at=AS_OF,
            source_id=roster_source.id,
            authority=Authority.MANUAL_CORRECTION,
        ))

    for name, team_code in KNOWN_OWNED_ELSEWHERE.items():
        p = _player(session, name)
        session.add(OwnershipEvent(
            league_id=league.id,
            player_id=p.id,
            fantasy_team_id=teams[team_code].id,
            state=OwnershipState.OWNED,
            event_type="OWNERSHIP_CORRECTION",
            effective_at=AS_OF,
            source_id=ownership_source.id,
            authority=Authority.MANUAL_CORRECTION,
            explicit_override=True,
        ))

    session.flush()
    rebuild_state(session, "sparta")
