"""Tests for pure order business logic."""

from muninn.services.orders import (
    board_version_for_rows,
    can_archive_order,
    digits_only,
    parse_stale_days,
    phone_matches,
    should_auto_notify_customer,
)


def test_digits_only():
    assert digits_only("+354 555-1234") == "3545551234"


def test_phone_matches_exact():
    assert phone_matches("5551234", "555-1234") is True


def test_phone_matches_last_seven():
    assert phone_matches("5551234", "3545551234") is True


def test_phone_matches_no_match():
    assert phone_matches("111", "2223333") is False


def test_should_auto_notify_komid():
    order = {"suppress_auto_email": 0}
    assert should_auto_notify_customer(order, "Komið") is True


def test_should_auto_notify_suppressed():
    order = {"suppress_auto_email": 1}
    assert should_auto_notify_customer(order, "Komið") is False


def test_should_auto_notify_other_status():
    order = {"suppress_auto_email": 0}
    assert should_auto_notify_customer(order, "Staðfest") is False


def test_can_archive_order():
    order = {"status": "Lokið", "payment_status": "Greitt"}
    assert can_archive_order(order) is True
    order2 = {"status": "Lokið", "payment_status": "Ógreitt"}
    assert can_archive_order(order2) is False


def test_parse_stale_days():
    assert parse_stale_days("7") == 7
    assert parse_stale_days("") is None
    assert parse_stale_days("0") is None
    assert parse_stale_days("bad") is None


def test_board_version_for_rows():
    class Row:
        def __init__(self, updated_at):
            self._data = {"updated_at": updated_at}

        def __getitem__(self, key):
            return self._data[key]

    rows = [Row("2026-01-01"), Row("2026-01-02")]
    v = board_version_for_rows(rows, "query", 7)
    assert v == "2:2026-01-02:query:7"
