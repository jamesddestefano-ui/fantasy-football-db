"""Name normalization for Mongo scripts (FantasyPros, ESPN, repository records).

Repository history spells defenses several ways ("Ravens D/ST", "Ravens",
"Dallas Cowboys DEF") and ESPN calls them "Ravens D/ST".
Everything is collapsed to a single comparison key.
"""
from __future__ import annotations

import re
import unicodedata

# abbr -> (city, nickname)
NFL_TEAMS = {
    "ARI": ("Arizona", "Cardinals"), "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"), "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"), "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"), "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"), "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"), "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"), "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"), "KC": ("Kansas City", "Chiefs"),
    "LV": ("Las Vegas", "Raiders"), "LAC": ("Los Angeles", "Chargers"),
    "LAR": ("Los Angeles", "Rams"), "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"), "NE": ("New England", "Patriots"),
    "NO": ("New Orleans", "Saints"), "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"), "PHI": ("Philadelphia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"), "SF": ("San Francisco", "49ers"),
    "SEA": ("Seattle", "Seahawks"), "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"), "WAS": ("Washington", "Commanders"),
}
TEAM_ALIASES = {"WSH": "WAS", "JAC": "JAX", "LA": "LAR", "OAK": "LV", "SD": "LAC", "GNB": "GB",
                "KAN": "KC", "NOR": "NO", "NWE": "NE", "SFO": "SF", "TAM": "TB", "LVR": "LV"}


def team_abbr(abbr: str | None) -> str | None:
    if not abbr:
        return None
    a = str(abbr).upper()
    return TEAM_ALIASES.get(a, a)


_NICK_TO_ABBR = {nick.lower(): abbr for abbr, (_, nick) in NFL_TEAMS.items()}
# Short/long first-name variants seen in fantasy records (e.g. "Kenny" vs "Kenneth Gainwell").
FIRST_NAME_ALIASES = {
    "kenny": "kenneth", "chig": "chigoziem", "cam": "cameron", "mike": "michael",
    "matt": "matthew", "chris": "christopher", "josh": "joshua", "nick": "nicholas",
    "rob": "robert", "bob": "robert", "tony": "anthony", "jon": "jonathan",
    "gabe": "gabriel", "zach": "zachary", "dj": "dj", "pat": "patrick",
}
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
_DEF_TAIL = re.compile(r"\b(d/st|dst|def|defense)\b", re.I)


def defense_abbr(name: str | None, nfl_team: str | None = None, position: str | None = None) -> str | None:
    """Return the NFL abbreviation if this name/position is a team defense."""
    if position and position.upper() in ("DEF", "D/ST", "DST") and nfl_team:
        return team_abbr(nfl_team)
    if not name:
        return None
    text = name.strip()
    has_tail = bool(_DEF_TAIL.search(text))
    words = _DEF_TAIL.sub("", text).strip().lower().split()
    if words and words[-1] in _NICK_TO_ABBR and (has_tail or len(words) <= 3):
        # "Ravens", "Ravens D/ST", "Dallas Cowboys DEF"
        if has_tail or len(words) == 1 or " ".join(words[:-1]) == NFL_TEAMS[_NICK_TO_ABBR[words[-1]]][0].lower():
            return _NICK_TO_ABBR[words[-1]]
    return None


def defense_display(abbr: str) -> str:
    return f"{NFL_TEAMS[abbr][1]} D/ST" if abbr in NFL_TEAMS else f"{abbr} D/ST"


def name_key(name: str | None, nfl_team: str | None = None, position: str | None = None) -> str | None:
    if not name:
        return None
    abbr = defense_abbr(name, nfl_team, position)
    if abbr:
        return f"def:{abbr}"
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[.'`’\-]", "", text)
    text = _SUFFIX.sub("", text)
    words = text.split()
    if len(words) >= 2 and words[0] in FIRST_NAME_ALIASES:
        words[0] = FIRST_NAME_ALIASES[words[0]]
    return " ".join(words)
