from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): pass

class OwnershipState(str, enum.Enum):
    OWNED = "OWNED"
    FREE_AGENT_CONFIRMED = "FREE_AGENT_CONFIRMED"
    WAIVERS_CONFIRMED = "WAIVERS_CONFIRMED"
    UNKNOWN = "UNKNOWN"

class Authority(str, enum.Enum):
    MANUAL_CORRECTION = "MANUAL_CORRECTION"
    CONFIRMED_TRANSACTION = "CONFIRMED_TRANSACTION"
    ESPN_CURRENT = "ESPN_CURRENT"
    CURRENT_ROSTER = "CURRENT_ROSTER"
    OTHER_SNAPSHOT = "OTHER_SNAPSHOT"
    DRAFT = "DRAFT"
    NON_OWNERSHIP = "NON_OWNERSHIP"

AUTHORITY_RANK = {a: i for i, a in enumerate(reversed(list(Authority)), start=1)}
AUTHORITY_RANK[Authority.MANUAL_CORRECTION] = 100
AUTHORITY_RANK[Authority.CONFIRMED_TRANSACTION] = 90
AUTHORITY_RANK[Authority.ESPN_CURRENT] = 80
AUTHORITY_RANK[Authority.CURRENT_ROSTER] = 70
AUTHORITY_RANK[Authority.OTHER_SNAPSHOT] = 60
AUTHORITY_RANK[Authority.DRAFT] = 50
AUTHORITY_RANK[Authority.NON_OWNERSHIP] = 0

class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str | None] = mapped_column(String(60))
    season: Mapped[int] = mapped_column()
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

class Manager(Base):
    __tablename__ = "managers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSON, default=list)

class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"
    __table_args__ = (UniqueConstraint("league_id", "slug"), UniqueConstraint("league_id", "name"))
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), index=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("managers.id"))
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    is_mine: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class NFLPlayer(Base):
    __tablename__ = "nfl_players"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    position: Mapped[str | None] = mapped_column(String(20))
    nfl_team: Mapped[str | None] = mapped_column(String(20))
    espn_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    status: Mapped[str | None] = mapped_column(String(40))

class PlayerAlias(Base):
    __tablename__ = "player_aliases"
    __table_args__ = (UniqueConstraint("normalized_alias"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(200))
    normalized_alias: Mapped[str] = mapped_column(String(200))

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    original_ref: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(String(60))
    author: Mapped[str | None] = mapped_column(String(200))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    authority: Mapped[Authority] = mapped_column(Enum(Authority))
    checksum: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)

class OwnershipEvent(Base):
    __tablename__ = "ownership_events"
    __table_args__ = (
        CheckConstraint("(state = 'OWNED' AND fantasy_team_id IS NOT NULL) OR (state <> 'OWNED' AND fantasy_team_id IS NULL)", name="ownership_team_matches_state"),
        Index("ix_ownership_replay", "league_id", "player_id", "effective_at", "id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    fantasy_team_id: Mapped[int | None] = mapped_column(ForeignKey("fantasy_teams.id"))
    state: Mapped[OwnershipState] = mapped_column(Enum(OwnershipState))
    event_type: Mapped[str] = mapped_column(String(50))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    authority: Mapped[Authority] = mapped_column(Enum(Authority))
    explicit_override: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_group_id: Mapped[str | None] = mapped_column(String(36), index=True)
    notes: Mapped[str | None] = mapped_column(Text)

class CurrentOwnership(Base):
    __tablename__ = "current_ownership"
    __table_args__ = (UniqueConstraint("league_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    fantasy_team_id: Mapped[int | None] = mapped_column(ForeignKey("fantasy_teams.id"))
    state: Mapped[OwnershipState] = mapped_column(Enum(OwnershipState))
    winning_event_id: Mapped[int] = mapped_column(ForeignKey("ownership_events.id"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class TransactionGroup(Base):
    __tablename__ = "transaction_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    notes: Mapped[str | None] = mapped_column(Text)

class TransactionEvent(Base):
    __tablename__ = "transaction_events"
    __table_args__ = (UniqueConstraint("group_id", "sequence"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("transaction_groups.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column()
    event_type: Mapped[str] = mapped_column(String(40))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    counterparty_team_id: Mapped[int | None] = mapped_column(ForeignKey("fantasy_teams.id"))
    faab_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)

class FaabEntry(Base):
    __tablename__ = "faab_entries"
    __table_args__ = (CheckConstraint("amount <> 0", name="nonzero_faab_entry"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    kind: Mapped[str] = mapped_column(String(40))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transaction_group_id: Mapped[str | None] = mapped_column(ForeignKey("transaction_groups.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class FaabBalanceObservation(Base):
    __tablename__ = "faab_balance_observations"
    __table_args__ = (CheckConstraint("balance >= 0", name="nonnegative_faab_observation"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"))
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class LineupAssignment(Base):
    __tablename__ = "lineup_assignments"
    __table_args__ = (UniqueConstraint("league_id", "season", "week", "fantasy_team_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    season: Mapped[int] = mapped_column()
    week: Mapped[int] = mapped_column()
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    slot: Mapped[str] = mapped_column(String(20))
    placement: Mapped[str] = mapped_column(String(20))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))

class DraftPick(Base):
    __tablename__ = "draft_picks"
    __table_args__ = (UniqueConstraint("draft_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"), nullable=False)
    fantasy_team_id: Mapped[int] = mapped_column(ForeignKey("fantasy_teams.id"), nullable=False)
    nomination_order: Mapped[int | None] = mapped_column()
    auction_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class PlayerStatusObservation(Base):
    __tablename__ = "player_status_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    category: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class NewsItem(Base):
    __tablename__ = "news_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("nfl_players.id"))
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id"))
    category: Mapped[str] = mapped_column(String(50))
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    significance: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))

class WaiverWatch(Base):
    __tablename__ = "waiver_watch"
    __table_args__ = (UniqueConstraint("league_id", "player_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("nfl_players.id"))
    status: Mapped[str] = mapped_column(String(40))
    priority: Mapped[int | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    potential_drop_player_ids: Mapped[list] = mapped_column(JSON, default=list)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class ReconciliationIssue(Base):
    __tablename__ = "reconciliation_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"))
    player_id: Mapped[int | None] = mapped_column(ForeignKey("nfl_players.id"))
    category: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

