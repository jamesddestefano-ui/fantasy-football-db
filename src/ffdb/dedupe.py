"""Mongo ESPN→transaction semantic dedupe + type-normalization safety layer.

Semantic identity key (after name/type normalization):
  league + team/owner + transaction_type_family + added_player + dropped_player + calendar_day_ET

BEFORE append:
  ALREADY_RECORDED → no write
  UNCERTAIN → INGESTION HELD (no write)
  NEW → eligible to append (caller decides; this module does not auto-ingest)

Transaction type family mapping
--------------------------------
ESPN wording, import JSON, and seed event sequences collapse into canonical families:

  WAIVER_ADD / "waiver" / "waiver_add"
      → WAIVER_ADD

  FREE_AGENT_ADD alone / "add" / "free_agent_add"  (no drop player)
      → FREE_AGENT_ADD

  IR_MOVE / "ir" / "ir_move"
      → IR_MOVE

  ADD_DROP / "add/drop" / "add_drop"
  FREE_AGENT_ADD + DROP (paired) / DROP + FREE_AGENT_ADD (seed sequence)
  any inbound event that has both an added and a dropped player under a free-agent/add vocabulary
      → ADD_DROP

  WAIVER_ADD + DROP (paired) / "waiver" with a dropped player
      → WAIVER_ADD_DROP

  DROP alone
      → DROP

Identical source labels and exact timestamps are NOT required — only the semantic key.
Timestamps are reduced to America/New_York calendar days before compare.
Player names are compared via normalize_name + PlayerAlias lookup to a canonical key.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import FantasyTeam, League, NFLPlayer, PlayerAlias, TransactionEvent, TransactionGroup
from .names import normalize_name

ET = ZoneInfo("America/New_York")

# Raw label → intermediate token (before add/drop pairing rules).
_TYPE_TOKEN: dict[str, str] = {
    "waiver": "WAIVER_ADD",
    "waivers": "WAIVER_ADD",
    "waiver_add": "WAIVER_ADD",
    "waiver add": "WAIVER_ADD",
    "add": "FREE_AGENT_ADD",
    "free_agent_add": "FREE_AGENT_ADD",
    "free agent add": "FREE_AGENT_ADD",
    "free_agent": "FREE_AGENT_ADD",
    "fa_add": "FREE_AGENT_ADD",
    "ir": "IR_MOVE",
    "ir_move": "IR_MOVE",
    "ir move": "IR_MOVE",
    "add/drop": "ADD_DROP",
    "add_drop": "ADD_DROP",
    "add-drop": "ADD_DROP",
    "drop": "DROP",
    "dropped": "DROP",
}


class Classification(str, Enum):
    ALREADY_RECORDED = "ALREADY_RECORDED"
    NEW = "NEW"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class SemanticKey:
    league: str
    team: str
    transaction_type: str
    added_player: str | None
    dropped_player: str | None
    calendar_day_ET: str

    def as_tuple(self) -> tuple:
        return (
            self.league,
            self.team,
            self.transaction_type,
            self.added_player,
            self.dropped_player,
            self.calendar_day_ET,
        )


@dataclass
class DedupeResult:
    classification: Classification
    semantic_key: SemanticKey | None = None
    matched_group_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    would_append: bool = False
    would_append_faab: bool = False
    faab_amount: Decimal | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value
        if self.semantic_key is not None:
            d["semantic_key"] = asdict(self.semantic_key)
        if self.faab_amount is not None:
            d["faab_amount"] = str(self.faab_amount)
        return d


def calendar_day_et(value: datetime | date | str) -> str:
    """Normalize a timestamp or date to an America/New_York calendar day (YYYY-MM-DD)."""
    if isinstance(value, str):
        raw = value.strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            # Bare date or ISO datetime — if timezone-aware ISO, convert; if date-only, keep.
            if "T" in raw or " " in raw[10:]:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(ET).date().isoformat()
            return raw[:10]
        raise ValueError(f"Unrecognized date/time string: {value!r}")
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(ET).date().isoformat()
    return value.isoformat()


def _token(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip().lower().replace("-", "_")
    key = " ".join(key.replace("_", " ").split())
    spaced = key
    underscored = key.replace(" ", "_")
    if underscored in _TYPE_TOKEN:
        return _TYPE_TOKEN[underscored]
    if spaced in _TYPE_TOKEN:
        return _TYPE_TOKEN[spaced]
    # Already-canonical uppercase families
    upper = raw.strip().upper().replace("-", "_").replace(" ", "_")
    if upper in {
        "WAIVER_ADD", "FREE_AGENT_ADD", "ADD_DROP", "WAIVER_ADD_DROP",
        "IR_MOVE", "DROP",
    }:
        return upper
    if upper == "ADD":
        return "FREE_AGENT_ADD"
    return upper


def normalize_transaction_type(
    transaction_type: str | Iterable[str] | None = None,
    *,
    added_player: str | None = None,
    dropped_player: str | None = None,
    event_types: Iterable[str] | None = None,
) -> str:
    """Map ESPN / import / seed vocabularies onto a canonical type family for matching.

    See module docstring for the full mapping table.
    """
    types: list[str] = []
    if isinstance(transaction_type, str):
        tok = _token(transaction_type)
        if tok:
            types.append(tok)
    elif transaction_type is not None:
        for t in transaction_type:
            tok = _token(t)
            if tok:
                types.append(tok)
    if event_types is not None:
        for t in event_types:
            tok = _token(t)
            if tok:
                types.append(tok)

    has_add = bool(added_player and str(added_player).strip()) or any(
        t in {"FREE_AGENT_ADD", "WAIVER_ADD", "ADD_DROP", "WAIVER_ADD_DROP"} for t in types
    )
    has_drop = bool(dropped_player and str(dropped_player).strip()) or any(t == "DROP" for t in types)

    # Paired add+drop collapses regardless of source label order.
    if has_add and has_drop:
        if any(t in {"WAIVER_ADD", "WAIVER_ADD_DROP"} for t in types) and not any(
            t in {"FREE_AGENT_ADD", "ADD_DROP"} for t in types
        ):
            # Pure waiver vocabulary with a drop.
            if "FREE_AGENT_ADD" not in types and "ADD_DROP" not in types:
                return "WAIVER_ADD_DROP"
        return "ADD_DROP"

    if "ADD_DROP" in types:
        return "ADD_DROP"
    if "WAIVER_ADD_DROP" in types:
        return "WAIVER_ADD_DROP"
    if "WAIVER_ADD" in types:
        return "WAIVER_ADD"
    if "IR_MOVE" in types:
        return "IR_MOVE"
    if "FREE_AGENT_ADD" in types:
        return "FREE_AGENT_ADD"
    if "DROP" in types:
        return "DROP"
    if types:
        return types[0]
    raise ValueError("Cannot normalize transaction type without type or players")


def resolve_player_key(session: Session, name: str | None) -> str | None:
    """Return canonical normalized player key using NFLPlayer + PlayerAlias."""
    if name is None:
        return None
    text = str(name).strip()
    if not text:
        return None
    norm = normalize_name(text)
    player = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == norm))
    if player:
        return player.normalized_name
    alias = session.scalar(select(PlayerAlias).where(PlayerAlias.normalized_alias == norm))
    if alias:
        player = session.get(NFLPlayer, alias.player_id)
        if player:
            return player.normalized_name
    return norm


def resolve_team_slug(session: Session, league_slug: str, team_ref: str) -> str:
    lg = session.scalar(select(League).where(League.slug == league_slug))
    if not lg:
        raise ValueError(f"Unknown league: {league_slug}")
    ref = team_ref.strip()
    if ref in {"mine", "jdd"}:
        tm = session.scalar(
            select(FantasyTeam).where(FantasyTeam.league_id == lg.id, FantasyTeam.is_mine.is_(True))
        )
        if tm:
            return tm.slug
    teams = session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == lg.id)).all()
    norm_ref = normalize_name(ref)
    for tm in teams:
        if tm.slug == ref or tm.name == ref:
            return tm.slug
        aliases = tm.aliases or []
        if ref in aliases or any(normalize_name(a) == norm_ref for a in aliases):
            return tm.slug
        if normalize_name(tm.name) == norm_ref or normalize_name(tm.slug) == norm_ref:
            return tm.slug
    raise ValueError(f"Unknown team in {league_slug}: {team_ref}")


def semantic_key(
    session: Session,
    *,
    league_slug: str,
    team_slug: str,
    transaction_type: str | Iterable[str] | None = None,
    added_player: str | None = None,
    dropped_player: str | None = None,
    effective_at: datetime | date | str,
    event_types: Iterable[str] | None = None,
) -> SemanticKey:
    team = resolve_team_slug(session, league_slug, team_slug)
    family = normalize_transaction_type(
        transaction_type,
        added_player=added_player,
        dropped_player=dropped_player,
        event_types=event_types,
    )
    return SemanticKey(
        league=league_slug,
        team=team,
        transaction_type=family,
        added_player=resolve_player_key(session, added_player),
        dropped_player=resolve_player_key(session, dropped_player),
        calendar_day_ET=calendar_day_et(effective_at),
    )


def _group_semantic_key(session: Session, group: TransactionGroup, league_slug: str, team_slug: str) -> SemanticKey:
    events = session.scalars(
        select(TransactionEvent).where(TransactionEvent.group_id == group.id).order_by(TransactionEvent.sequence)
    ).all()
    event_types = [e.event_type for e in events]
    added_name = None
    dropped_name = None
    for e in events:
        p = session.get(NFLPlayer, e.player_id)
        if e.event_type in {"FREE_AGENT_ADD", "WAIVER_ADD", "IR_MOVE"}:
            added_name = p.canonical_name if p else None
        elif e.event_type == "DROP":
            dropped_name = p.canonical_name if p else None
        elif e.event_type in {"ADD_DROP", "WAIVER_ADD_DROP"}:
            # Single-row grouped type (import shape) — treat player as added; drop comes from notes/counterpart.
            added_name = p.canonical_name if p else added_name
    return semantic_key(
        session,
        league_slug=league_slug,
        team_slug=team_slug,
        event_types=event_types,
        added_player=added_name,
        dropped_player=dropped_name,
        effective_at=group.effective_at,
    )


def find_existing_transaction(
    session: Session,
    league_slug: str,
    team_slug: str,
    *,
    transaction_type: str | Iterable[str] | None = None,
    added_player: str | None = None,
    dropped_player: str | None = None,
    effective_at: datetime | date | str,
    event_types: Iterable[str] | None = None,
    faab_amount: Decimal | int | float | str | None = None,
) -> DedupeResult:
    """Classify an inbound ESPN/import event against existing Mongo transaction groups."""
    if league_slug != "mongo":
        return DedupeResult(
            classification=Classification.UNCERTAIN,
            reasons=[f"INGESTION HELD: only mongo league is supported (got {league_slug!r})"],
        )

    try:
        key = semantic_key(
            session,
            league_slug=league_slug,
            team_slug=team_slug,
            transaction_type=transaction_type,
            added_player=added_player,
            dropped_player=dropped_player,
            effective_at=effective_at,
            event_types=event_types,
        )
    except (ValueError, TypeError) as exc:
        return DedupeResult(
            classification=Classification.UNCERTAIN,
            reasons=[f"INGESTION HELD: cannot build semantic key ({exc})"],
        )

    lg = session.scalar(select(League).where(League.slug == league_slug))
    if not lg:
        return DedupeResult(
            classification=Classification.UNCERTAIN,
            semantic_key=key,
            reasons=["INGESTION HELD: mongo league missing"],
        )
    tm_slug = key.team
    tm = session.scalar(select(FantasyTeam).where(FantasyTeam.league_id == lg.id, FantasyTeam.slug == tm_slug))
    if not tm:
        return DedupeResult(
            classification=Classification.UNCERTAIN,
            semantic_key=key,
            reasons=[f"INGESTION HELD: team {tm_slug!r} missing"],
        )

    matches: list[str] = []
    for group in session.scalars(
        select(TransactionGroup).where(
            TransactionGroup.league_id == lg.id,
            TransactionGroup.fantasy_team_id == tm.id,
        )
    ).all():
        existing = _group_semantic_key(session, group, league_slug, tm.slug)
        if existing.as_tuple() == key.as_tuple():
            matches.append(group.id)

    faab = None
    if faab_amount is not None and str(faab_amount) != "":
        faab = Decimal(str(faab_amount))

    if len(matches) == 1:
        return DedupeResult(
            classification=Classification.ALREADY_RECORDED,
            semantic_key=key,
            matched_group_id=matches[0],
            would_append=False,
            would_append_faab=False,
            faab_amount=faab,
            reasons=["Exact semantic key match after type + name + calendar-day normalization"],
        )
    if len(matches) > 1:
        return DedupeResult(
            classification=Classification.UNCERTAIN,
            semantic_key=key,
            matched_group_id=None,
            would_append=False,
            would_append_faab=False,
            faab_amount=faab,
            reasons=[
                "INGESTION HELD: multiple existing groups share the same semantic key",
                *matches,
            ],
        )

    return DedupeResult(
        classification=Classification.NEW,
        semantic_key=key,
        matched_group_id=None,
        would_append=True,
        would_append_faab=bool(faab is not None and faab > 0),
        faab_amount=faab,
        reasons=["No existing TransactionGroup matches semantic key"],
    )


def _event_from_mapping(event: Mapping[str, Any]) -> dict[str, Any]:
    """Accept flexible ESPN / import / dry-run event shapes."""
    added = event.get("added_player")
    if added is None:
        added = event.get("added") or event.get("player")
        if isinstance(event.get("players_added"), list) and event["players_added"]:
            added = event["players_added"][0]
    dropped = event.get("dropped_player")
    if dropped is None:
        dropped = event.get("dropped")
        if isinstance(event.get("players_dropped"), list):
            dropped = event["players_dropped"][0] if event["players_dropped"] else None
    tx_type = event.get("transaction_type") or event.get("type") or event.get("event_type")
    when = (
        event.get("effective_at")
        or event.get("calendar_day_ET")
        or event.get("observed_at")
        or event.get("date_displayed")
    )
    faab = event.get("faab_amount")
    if faab is None:
        faab = event.get("faab_spent")
    return {
        "league": event.get("league", "mongo"),
        "team": event.get("team") or event.get("fantasy_team") or event.get("team_slug") or "jdd",
        "transaction_type": tx_type,
        "added_player": added,
        "dropped_player": dropped,
        "effective_at": when,
        "faab_amount": faab,
        "description": event.get("description") or event.get("detail"),
        "event_types": event.get("event_types"),
    }


def dry_run_classify(session: Session, events: Iterable[Mapping[str, Any]]) -> list[DedupeResult]:
    """Classify inbound events without writing. Returns one DedupeResult per event."""
    results: list[DedupeResult] = []
    for raw in events:
        parsed = _event_from_mapping(raw)
        if parsed["effective_at"] is None:
            results.append(
                DedupeResult(
                    classification=Classification.UNCERTAIN,
                    description=parsed.get("description"),
                    reasons=["INGESTION HELD: missing effective_at / calendar_day_ET"],
                )
            )
            continue
        # ESPN live activity sometimes uses display dates like "Thu Sep 3, 12:13 am"
        when = parsed["effective_at"]
        if isinstance(when, str) and when[0].isalpha():
            # Require caller to supply calendar_day_ET for display strings; try companion field.
            if raw.get("calendar_day_ET"):
                when = raw["calendar_day_ET"]
            else:
                results.append(
                    DedupeResult(
                        classification=Classification.UNCERTAIN,
                        description=parsed.get("description"),
                        reasons=[
                            "INGESTION HELD: display date string needs calendar_day_ET",
                            f"got {when!r}",
                        ],
                    )
                )
                continue
        result = find_existing_transaction(
            session,
            parsed["league"] if parsed["league"] != "Mangarelli Auction League" else "mongo",
            "jdd" if parsed["team"] in {"Tom Brady of Ass", "JDD", "James DeStefano"} else parsed["team"],
            transaction_type=parsed["transaction_type"],
            added_player=parsed["added_player"],
            dropped_player=parsed["dropped_player"],
            effective_at=when,
            event_types=parsed.get("event_types"),
            faab_amount=parsed.get("faab_amount"),
        )
        result.description = parsed.get("description")
        results.append(result)
    return results


# Canonical ESPN live activity + IR confirmation set used by dry-run / tests.
KNOWN_ESPN_EVENTS: list[dict[str, Any]] = [
    {
        "description": "2026-09-03 ET WAIVER_ADD Jacob Saylors $6",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "waiver",
        "added_player": "Jacob Saylors",
        "dropped_player": None,
        "calendar_day_ET": "2026-09-03",
        "faab_amount": 6,
    },
    {
        "description": "2026-09-03 ET ADD Kaelon Black + DROP Ja'Kobi Lane $0",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "add/drop",
        "added_player": "Kaelon Black",
        "dropped_player": "Ja'Kobi Lane",
        "calendar_day_ET": "2026-09-03",
        "faab_amount": 0,
    },
    {
        "description": "2026-09-03 ET ADD Tre Tucker + DROP Nicholas Singleton $0",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "add/drop",
        "added_player": "Tre Tucker",
        "dropped_player": "Nicholas Singleton",
        "calendar_day_ET": "2026-09-03",
        "faab_amount": 0,
    },
    {
        "description": "2026-09-08 ET ADD Ja'Kobi Lane + DROP Kayshon Boutte $0",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "FREE_AGENT_ADD",  # ESPN wording; paired drop → ADD_DROP family
        "added_player": "Jakobi Lane",  # alternate spelling; alias resolves
        "dropped_player": "Kayshon Boutte",
        "calendar_day_ET": "2026-09-08",
        "faab_amount": 0,
    },
    {
        "description": "2026-09-08 ET ADD Malik Davis + DROP Jacob Saylors $0",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "add/drop",
        "added_player": "Malik Davis",
        "dropped_player": "Jacob Saylors",
        "calendar_day_ET": "2026-09-08",
        "faab_amount": 0,
    },
    {
        "description": "2026-09-11 ET FREE_AGENT_ADD Emari Demercado $0",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "add",
        "added_player": "Emari Demercado",
        "dropped_player": None,
        "calendar_day_ET": "2026-09-11",
        "faab_amount": 0,
    },
    {
        "description": "2026-09-11 ET IR_MOVE Malik Davis BN→IR (user confirmation; not on ESPN activity filter)",
        "league": "mongo",
        "team": "jdd",
        "transaction_type": "IR_MOVE",
        "added_player": "Malik Davis",
        "dropped_player": None,
        "calendar_day_ET": "2026-09-11",
        "faab_amount": None,
    },
]
