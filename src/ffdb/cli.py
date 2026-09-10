from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import typer
from sqlalchemy import select

from .db import DEFAULT_DB, make_engine, session_scope
from .models import Authority, Base, CurrentOwnership, FantasyTeam, LineupAssignment, NFLPlayer, OwnershipEvent, ReconciliationIssue, Source, WaiverWatch
from .seed import seed_mongo
from .services import DomainError, add_drop, backup_database, export_state, faab_balance, league, ownership, player, rebuild_state, roster, team, validate

app = typer.Typer(no_args_is_help=True)
roster_app = typer.Typer(); player_app = typer.Typer(); tx_app = typer.Typer(); faab_app = typer.Typer(); lineup_app = typer.Typer(); watch_app = typer.Typer()
app.add_typer(roster_app, name="roster"); app.add_typer(player_app, name="player"); app.add_typer(tx_app, name="transaction")
app.add_typer(faab_app, name="faab"); app.add_typer(lineup_app, name="lineup"); app.add_typer(watch_app, name="waiver-watch")

def _run(fn):
    engine = make_engine()
    try:
        with session_scope(engine) as session: return fn(session)
    except DomainError as exc:
        typer.echo(f"ERROR: {exc}", err=True); raise typer.Exit(2)

@app.command()
def init(seed: bool = True):
    engine = make_engine(); Base.metadata.create_all(engine)
    if seed:
        with session_scope(engine) as session:
            seed_mongo(session)
    typer.echo(f"Initialized {DEFAULT_DB}")

@roster_app.command("show")
def roster_show(league_slug: str = typer.Option(..., "--league")):
    def go(s):
        rows = roster(s, league_slug)
        for p, current in rows: typer.echo(f"{p.position:4} {p.canonical_name}")
        typer.echo(f"{len(rows)} players")
    _run(go)

@player_app.command("ownership")
def player_ownership(name: str, league_slug: str = typer.Option(..., "--league")):
    def go(s):
        row = ownership(s, league_slug, name)
        if not row: typer.echo(f"{name}: UNKNOWN (no ownership evidence)"); return
        team_name = s.get(FantasyTeam, row.fantasy_team_id).name if row.fantasy_team_id else None
        event = s.get(OwnershipEvent, row.winning_event_id); source = s.get(Source, event.source_id)
        detail = f" by {team_name}" if team_name else ""
        typer.echo(f"{name}: {row.state.value}{detail}; verified {row.verified_at}; source: {source.description}")
    _run(go)

@player_app.command("history")
def player_history(name: str, league_slug: str = typer.Option(..., "--league")):
    def go(s):
        lg, p = league(s, league_slug), player(s, name)
        events = s.scalars(select(OwnershipEvent).where(OwnershipEvent.league_id == lg.id, OwnershipEvent.player_id == p.id).order_by(OwnershipEvent.effective_at, OwnershipEvent.id))
        for e in events: typer.echo(f"{e.effective_at} {e.event_type} {e.state.value} source={e.source_id}")
    _run(go)

@tx_app.command("add-drop")
def transaction_add_drop(league_slug: str = typer.Option(..., "--league"), team_slug: str = typer.Option("mine", "--team"),
                         drop: str = typer.Option(...), add: str = typer.Option(...), faab: Decimal = typer.Option(Decimal("0"))):
    def go(s):
        lg = league(s, league_slug)
        src = Source(league_id=lg.id, source_type="USER_CONFIRMATION", description="Completed transaction supplied conversationally",
            platform="CLI", observed_at=datetime.now(timezone.utc), authority=Authority.CONFIRMED_TRANSACTION)
        s.add(src); s.flush(); gid = add_drop(s, league_slug, team_slug, drop, add, faab, src.id)
        typer.echo(f"Recorded atomic transaction {gid}; FAAB balance: {faab_balance(s, league_slug, team_slug)}")
    _run(go)

@faab_app.command("show")
def faab_show(league_slug: str = typer.Option(..., "--league")):
    _run(lambda s: typer.echo(f"FAAB: {faab_balance(s, league_slug)}"))

@lineup_app.command("show")
def lineup_show(league_slug: str = typer.Option(..., "--league"), week: int = typer.Option(...)):
    def go(s):
        lg = league(s, league_slug); tm = team(s, lg, "mine")
        rows = s.execute(select(LineupAssignment, NFLPlayer).join(NFLPlayer, LineupAssignment.player_id == NFLPlayer.id)
            .where(LineupAssignment.league_id == lg.id, LineupAssignment.fantasy_team_id == tm.id, LineupAssignment.week == week)
            .order_by(LineupAssignment.placement.desc(), LineupAssignment.slot)).all()
        for a, p in rows: typer.echo(f"{a.placement:7} {a.slot:5} {p.canonical_name}")
    _run(go)

@watch_app.command("show")
def waiver_show(league_slug: str = typer.Option(..., "--league")):
    def go(s):
        lg = league(s, league_slug)
        rows = s.execute(select(WaiverWatch, NFLPlayer, CurrentOwnership).join(NFLPlayer, WaiverWatch.player_id == NFLPlayer.id)
            .outerjoin(CurrentOwnership, (CurrentOwnership.player_id == NFLPlayer.id) & (CurrentOwnership.league_id == lg.id))
            .where(WaiverWatch.league_id == lg.id)).all()
        for w, p, own in rows: typer.echo(f"{p.canonical_name}: TARGET — {(own.state.value if own else 'UNKNOWN / NEEDS VERIFICATION')} — {w.reason or ''}")
        if not rows: typer.echo("No waiver-watch entries")
    _run(go)

@app.command("rebuild-state")
def rebuild(league_slug: str = typer.Option(..., "--league")):
    _run(lambda s: typer.echo(f"Rebuilt {rebuild_state(s, league_slug)} player states"))

@app.command("validate")
def validate_cmd(league_slug: str = typer.Option(..., "--league", help="League slug")):
    def go(s):
        errors = validate(s, league_slug)
        if errors:
            for x in errors: typer.echo(f"FAIL: {x}", err=True)
            raise typer.Exit(1)
        typer.echo(f"{league_slug}: validation passed")
    _run(go)

@app.command()
def reconcile(league_slug: str = typer.Option(..., "--league")):
    def go(s):
        lg = league(s, league_slug); issues = s.scalars(select(ReconciliationIssue).where(ReconciliationIssue.league_id == lg.id, ReconciliationIssue.status == "OPEN"))
        count = 0
        for i in issues: count += 1; typer.echo(f"{i.category}: {i.details}")
        typer.echo(f"{count} open reconciliation issues")
    _run(go)

@app.command()
def backup(db: Path = DEFAULT_DB):
    typer.echo(backup_database(db, Path("data/backups")))

@app.command("export")
def export_cmd(league_slug: str = typer.Option(..., "--league")):
    _run(lambda s: [typer.echo(p) for p in export_state(s, league_slug, Path("data/exports"))])

if __name__ == "__main__": app()
