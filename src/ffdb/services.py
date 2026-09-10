from __future__ import annotations

import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (AUTHORITY_RANK, Authority, CurrentOwnership, FaabBalanceObservation,
    FaabEntry, FantasyTeam, League, NFLPlayer, OwnershipEvent, OwnershipState,
    ReconciliationIssue, Source, TransactionEvent, TransactionGroup)
from .names import normalize_name


class DomainError(ValueError): pass


def league(session: Session, slug: str) -> League:
    obj = session.scalar(select(League).where(League.slug == slug))
    if not obj: raise DomainError(f"Unknown league: {slug}")
    return obj


def team(session: Session, lg: League, slug: str) -> FantasyTeam:
    stmt = select(FantasyTeam).where(FantasyTeam.league_id == lg.id)
    stmt = stmt.where(FantasyTeam.is_mine.is_(True)) if slug == "mine" else stmt.where(FantasyTeam.slug == slug)
    obj = session.scalar(stmt)
    if not obj: raise DomainError(f"Unknown team in {lg.slug}: {slug}")
    return obj


def player(session: Session, name: str) -> NFLPlayer:
    obj = session.scalar(select(NFLPlayer).where(NFLPlayer.normalized_name == normalize_name(name)))
    if not obj: raise DomainError(f"Unknown player: {name}")
    return obj


def winner(events: list[OwnershipEvent]) -> OwnershipEvent:
    if not events: raise DomainError("No ownership evidence")
    return max(events, key=lambda e: (e.effective_at, bool(e.explicit_override), AUTHORITY_RANK[e.authority], e.recorded_at, e.id))


def rebuild_state(session: Session, league_slug: str) -> int:
    lg = league(session, league_slug)
    session.query(CurrentOwnership).filter(CurrentOwnership.league_id == lg.id).delete()
    events = session.scalars(select(OwnershipEvent).where(OwnershipEvent.league_id == lg.id)).all()
    grouped: dict[int, list[OwnershipEvent]] = {}
    for event in events: grouped.setdefault(event.player_id, []).append(event)
    for player_id, rows in grouped.items():
        event = winner(rows)
        session.add(CurrentOwnership(league_id=lg.id, player_id=player_id, fantasy_team_id=event.fantasy_team_id,
            state=event.state, winning_event_id=event.id, verified_at=event.effective_at))
    session.flush()
    return len(grouped)


def ownership(session: Session, league_slug: str, player_name: str):
    lg, p = league(session, league_slug), player(session, player_name)
    return session.scalar(select(CurrentOwnership).where(CurrentOwnership.league_id == lg.id, CurrentOwnership.player_id == p.id))


def roster(session: Session, league_slug: str, team_slug: str = "mine"):
    lg = league(session, league_slug); tm = team(session, lg, team_slug)
    return session.execute(select(NFLPlayer, CurrentOwnership).join(CurrentOwnership, CurrentOwnership.player_id == NFLPlayer.id)
        .where(CurrentOwnership.league_id == lg.id, CurrentOwnership.fantasy_team_id == tm.id, CurrentOwnership.state == OwnershipState.OWNED)
        .order_by(NFLPlayer.position, NFLPlayer.canonical_name)).all()


def faab_balance(session: Session, league_slug: str, team_slug: str = "mine") -> Decimal | None:
    lg = league(session, league_slug); tm = team(session, lg, team_slug)
    checkpoint = session.scalar(select(FaabBalanceObservation).where(FaabBalanceObservation.league_id == lg.id,
        FaabBalanceObservation.fantasy_team_id == tm.id).order_by(FaabBalanceObservation.observed_at.desc(), FaabBalanceObservation.id.desc()))
    if not checkpoint: return None
    delta = session.scalar(select(func.coalesce(func.sum(FaabEntry.amount), 0)).where(FaabEntry.league_id == lg.id,
        FaabEntry.fantasy_team_id == tm.id, FaabEntry.effective_at > checkpoint.observed_at))
    return Decimal(checkpoint.balance) + Decimal(delta)


def add_drop(session: Session, league_slug: str, team_slug: str, drop_name: str, add_name: str,
             faab: Decimal, source_id: int, effective_at: datetime | None = None):
    if faab < 0: raise DomainError("FAAB cannot be negative")
    lg, when = league(session, league_slug), effective_at or datetime.now(timezone.utc)
    tm, dropped, added = team(session, lg, team_slug), player(session, drop_name), player(session, add_name)
    drop_state = ownership(session, league_slug, drop_name)
    if not drop_state or drop_state.state != OwnershipState.OWNED or drop_state.fantasy_team_id != tm.id:
        raise DomainError(f"{drop_name} is not currently owned by {tm.name}")
    add_state = ownership(session, league_slug, add_name)
    if add_state and add_state.state == OwnershipState.OWNED and add_state.fantasy_team_id != tm.id:
        raise DomainError(f"{add_name} is owned by another team; use a trade or explicit correction")
    new_balance = faab_balance(session, league_slug, team_slug)
    if new_balance is not None and new_balance - faab < 0: raise DomainError("Transaction would make FAAB negative")
    gid = str(uuid.uuid4())
    # Flush the parent transaction group first. Without an ORM relationship SQLAlchemy is not
    # guaranteed to order the pending child inserts ahead of this FK dependency on every flush.
    session.add(TransactionGroup(id=gid, league_id=lg.id, fantasy_team_id=tm.id, effective_at=when, source_id=source_id))
    session.flush()
    session.add_all([
        TransactionEvent(group_id=gid, sequence=1, event_type="DROP", player_id=dropped.id),
        TransactionEvent(group_id=gid, sequence=2, event_type="ADD", player_id=added.id, faab_amount=faab),
        OwnershipEvent(league_id=lg.id, player_id=dropped.id, state=OwnershipState.UNKNOWN, event_type="DROPPED",
            effective_at=when, source_id=source_id, authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=gid,
            notes="Drop proves departure from roster, not current free agency."),
        OwnershipEvent(league_id=lg.id, player_id=added.id, fantasy_team_id=tm.id, state=OwnershipState.OWNED, event_type="ADDED",
            effective_at=when, source_id=source_id, authority=Authority.CONFIRMED_TRANSACTION, transaction_group_id=gid),
    ])
    if faab:
        session.add(FaabEntry(league_id=lg.id, fantasy_team_id=tm.id, amount=-faab, kind="WAIVER_EXPENDITURE",
            effective_at=when, transaction_group_id=gid, source_id=source_id))
    session.flush(); rebuild_state(session, league_slug)
    errors = validate(session, league_slug)
    if errors: raise DomainError("Validation failed: " + "; ".join(errors))
    return gid


def validate(session: Session, league_slug: str) -> list[str]:
    lg = league(session, league_slug); errors = []
    duplicate = session.execute(select(CurrentOwnership.player_id, func.count()).where(CurrentOwnership.league_id == lg.id)
        .group_by(CurrentOwnership.player_id).having(func.count() > 1)).first()
    if duplicate: errors.append("multiple current ownership rows for a player")
    for tm in session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == lg.id, FantasyTeam.active.is_(True))):
        count = session.scalar(select(func.count()).select_from(CurrentOwnership).where(CurrentOwnership.league_id == lg.id,
            CurrentOwnership.fantasy_team_id == tm.id, CurrentOwnership.state == OwnershipState.OWNED))
        size = lg.settings.get("roster_size") if lg.settings else None
        if size is not None and tm.is_mine and count != size: errors.append(f"{tm.name} roster size {count}, expected {size}")
        balance = faab_balance(session, league_slug, tm.slug)
        if balance is not None and balance < 0: errors.append(f"{tm.name} has negative FAAB")
    missing_source = session.scalar(select(func.count()).select_from(CurrentOwnership).join(OwnershipEvent,
        CurrentOwnership.winning_event_id == OwnershipEvent.id).where(CurrentOwnership.league_id == lg.id, OwnershipEvent.source_id.is_(None)))
    if missing_source: errors.append("current ownership lacks provenance")
    return errors


def backup_database(db_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"fantasy-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(db_path, out); return out


def export_state(session: Session, league_slug: str, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True); lg = league(session, league_slug)
    rows = session.execute(select(NFLPlayer.canonical_name, NFLPlayer.position, CurrentOwnership.state,
        FantasyTeam.name, CurrentOwnership.verified_at).join(CurrentOwnership, CurrentOwnership.player_id == NFLPlayer.id)
        .outerjoin(FantasyTeam, CurrentOwnership.fantasy_team_id == FantasyTeam.id).where(CurrentOwnership.league_id == lg.id)).all()
    payload = [{"player": r[0], "position": r[1], "state": r[2].value, "team": r[3], "verified_at": r[4].isoformat()} for r in rows]
    json_path = target_dir / f"{league_slug}-current-state.json"; json_path.write_text(json.dumps(payload, indent=2))
    csv_path = target_dir / f"{league_slug}-current-ownership.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=payload[0].keys() if payload else ["player", "position", "state", "team", "verified_at"]); w.writeheader(); w.writerows(payload)
    return [json_path, csv_path]
