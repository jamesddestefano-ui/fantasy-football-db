"""Semantic dedupe safety for ESPN → Mongo ingest (dry-run only)."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from ffdb.dedupe import (
    KNOWN_ESPN_EVENTS,
    Classification,
    calendar_day_et,
    dry_run_classify,
    find_existing_transaction,
    normalize_transaction_type,
    resolve_player_key,
    semantic_key,
)
from ffdb.models import FaabEntry, PlayerAlias
from ffdb.names import normalize_name
from ffdb.services import faab_balance


def test_normalize_transaction_type_mapping():
    assert normalize_transaction_type("FREE_AGENT_ADD", added_player="A", dropped_player="B") == "ADD_DROP"
    assert normalize_transaction_type("ADD_DROP", added_player="A", dropped_player="B") == "ADD_DROP"
    assert normalize_transaction_type(event_types=["DROP", "FREE_AGENT_ADD"]) == "ADD_DROP"
    assert normalize_transaction_type("add/drop") == "ADD_DROP"
    assert normalize_transaction_type("waiver") == "WAIVER_ADD"
    assert normalize_transaction_type("add") == "FREE_AGENT_ADD"
    assert normalize_transaction_type("IR_MOVE") == "IR_MOVE"
    assert normalize_transaction_type("FREE_AGENT_ADD", added_player="A") == "FREE_AGENT_ADD"


def test_calendar_day_et_normalizes_utc_confirmation_timestamps():
    # Demercado confirmation 21:43 UTC still Sep 11 ET (EDT = UTC-4).
    assert calendar_day_et(datetime(2026, 9, 11, 21, 43, tzinfo=timezone.utc)) == "2026-09-11"
    assert calendar_day_et("2026-09-03") == "2026-09-03"
    # Noon ET stored as 16:00 UTC
    assert calendar_day_et(datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc)) == "2026-09-03"


def test_player_aliases_seeded_for_known_gaps(session):
    assert resolve_player_key(session, "Jakobi Lane") == normalize_name("Ja'Kobi Lane")
    assert resolve_player_key(session, "Ja'Kobi Lane") == normalize_name("Ja'Kobi Lane")
    assert resolve_player_key(session, "Eagles") == normalize_name("Eagles D/ST")
    assert resolve_player_key(session, "Devon Achane") == normalize_name("De'Von Achane")
    aliases = session.scalars(select(PlayerAlias)).all()
    norms = {a.normalized_alias for a in aliases}
    assert normalize_name("Jakobi Lane") in norms
    assert normalize_name("Eagles") in norms
    assert normalize_name("Devon Achane") in norms


def test_all_known_espn_events_classify_already_recorded(session):
    results = dry_run_classify(session, KNOWN_ESPN_EVENTS)
    assert len(results) == 7
    for r, event in zip(results, KNOWN_ESPN_EVENTS):
        assert r.classification == Classification.ALREADY_RECORDED, (
            f"{event['description']} → {r.classification} {r.reasons}"
        )
        assert r.would_append is False
        assert r.matched_group_id


def test_six_espn_live_plus_ir_confirmation_match_expected_groups(session):
    results = dry_run_classify(session, KNOWN_ESPN_EVENTS)
    expected = {
        "Jacob Saylors": "saylors-waiver-20260903-faab6-001",
        "Kaelon Black": "black-add-lane-drop-20260903-001",
        "Tre Tucker": "tucker-add-singleton-drop-20260903-001",
        "Jakobi Lane": "lane-add-boutte-drop-20260908-001",
        "Malik Davis": None,  # two Malik events; check by description below
        "Emari Demercado": "demercado-add-20260911-free-001",
    }
    by_desc = {e["description"]: r for e, r in zip(KNOWN_ESPN_EVENTS, results)}
    assert by_desc[KNOWN_ESPN_EVENTS[0]["description"]].matched_group_id == expected["Jacob Saylors"]
    assert by_desc[KNOWN_ESPN_EVENTS[1]["description"]].matched_group_id == expected["Kaelon Black"]
    assert by_desc[KNOWN_ESPN_EVENTS[2]["description"]].matched_group_id == expected["Tre Tucker"]
    assert by_desc[KNOWN_ESPN_EVENTS[3]["description"]].matched_group_id == expected["Jakobi Lane"]
    assert by_desc[KNOWN_ESPN_EVENTS[4]["description"]].matched_group_id == "malik-add-saylors-drop-20260908-001"
    assert by_desc[KNOWN_ESPN_EVENTS[5]["description"]].matched_group_id == expected["Emari Demercado"]
    assert by_desc[KNOWN_ESPN_EVENTS[6]["description"]].matched_group_id == "malik-ir-20260911-confirmed-001"


def test_hypothetical_new_fa_add_on_new_day_classifies_new(session):
    result = find_existing_transaction(
        session,
        "mongo",
        "jdd",
        transaction_type="FREE_AGENT_ADD",
        added_player="Player Z",
        dropped_player=None,
        effective_at="2026-09-15",
        faab_amount=0,
    )
    assert result.classification == Classification.NEW
    assert result.would_append is True
    assert result.would_append_faab is False
    assert result.semantic_key.calendar_day_ET == "2026-09-15"
    assert result.semantic_key.transaction_type == "FREE_AGENT_ADD"


def test_reclassifying_saylors_waiver_does_not_recommend_second_faab_debit(session):
    before = faab_balance(session, "mongo")
    assert before == Decimal("94.00")
    debit_count = len(session.scalars(select(FaabEntry).where(FaabEntry.kind == "WAIVER_EXPENDITURE")).all())
    assert debit_count == 1

    result = find_existing_transaction(
        session,
        "mongo",
        "jdd",
        transaction_type="WAIVER_ADD",
        added_player="Jacob Saylors",
        dropped_player=None,
        effective_at="2026-09-03",
        faab_amount=6,
    )
    assert result.classification == Classification.ALREADY_RECORDED
    assert result.would_append is False
    assert result.would_append_faab is False
    assert result.matched_group_id == "saylors-waiver-20260903-faab6-001"
    # No write occurred — balance and debit count unchanged.
    assert faab_balance(session, "mongo") == Decimal("94.00")
    assert len(session.scalars(select(FaabEntry).where(FaabEntry.kind == "WAIVER_EXPENDITURE")).all()) == 1


def test_semantic_key_ignores_source_label_and_exact_timestamp(session):
    k1 = semantic_key(
        session,
        league_slug="mongo",
        team_slug="Tom Brady of Ass",
        transaction_type="ADD_DROP",
        added_player="Kaelon Black",
        dropped_player="Ja'Kobi Lane",
        effective_at="2026-09-03",
    )
    k2 = semantic_key(
        session,
        league_slug="mongo",
        team_slug="jdd",
        event_types=["DROP", "FREE_AGENT_ADD"],
        added_player="Kaelon Black",
        dropped_player="Jakobi Lane",  # alias
        effective_at=datetime(2026, 9, 3, 16, 0, tzinfo=timezone.utc),
    )
    assert k1.as_tuple() == k2.as_tuple()
    assert k1.transaction_type == "ADD_DROP"
