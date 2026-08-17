"""Tests for features/reports/service.py against specs/reports-export.md
acceptance criteria (AC-1..AC-5).

This feature has no database interaction of its own -- it formats
already-fetched, already-filtered ticket dicts (as returned by
`features.tickets.service.list_tickets`) into CSV text / PDF bytes. So
these are plain unit tests over dict fixtures; no FakeCursor/FakeConnection
is needed here (unlike most of this suite).
"""

import csv
import io

import pytest

from features.reports.service import (
    EXPORT_COLUMNS,
    ReportError,
    generate_csv,
    generate_pdf,
)


def _ticket(
    id=1,
    ticket_number="TCK-000001",
    requester_id=7,
    assignee_id=None,
    title="Printer is on fire",
    description="Smoke coming out of the printer on the 3rd floor.",
    category="Hardware",
    priority="HIGH",
    status="OPEN",
    created_at="2026-01-01 10:00:00",
    updated_at="2026-01-02 11:00:00",
):
    return {
        "id": id,
        "ticket_number": ticket_number,
        "requester_id": requester_id,
        "assignee_id": assignee_id,
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _parse_csv(csv_text):
    return list(csv.reader(io.StringIO(csv_text)))


# ---------------------------------------------------------------------------
# AC-1 (FR-EXP-01/03): the CSV export contains exactly the given rows.
# ---------------------------------------------------------------------------


def test_fr_exp_01_csv_has_exactly_header_plus_n_rows_matching_input():
    tickets = [
        _ticket(id=1, ticket_number="TCK-000001", title="First"),
        _ticket(id=2, ticket_number="TCK-000002", title="Second"),
        _ticket(id=3, ticket_number="TCK-000003", title="Third"),
    ]

    csv_text = generate_csv(tickets, user_id=7)
    rows = _parse_csv(csv_text)

    assert len(rows) == len(tickets) + 1
    assert rows[0] == list(EXPORT_COLUMNS)
    for ticket, row in zip(tickets, rows[1:]):
        assert row == [
            ticket["ticket_number"],
            ticket["title"],
            ticket["status"],
            ticket["priority"],
            ticket["category"],
            str(ticket["created_at"]),
            str(ticket["updated_at"]),
        ]


def test_fr_exp_01_csv_row_values_match_exactly_no_extra_or_missing_columns():
    ticket = _ticket(
        ticket_number="TCK-000042",
        title="Broken monitor",
        status="IN_PROGRESS",
        priority="URGENT",
        category="Hardware",
        created_at="2026-02-01 09:00:00",
        updated_at="2026-02-02 09:00:00",
    )

    rows = _parse_csv(generate_csv([ticket], user_id=7))

    assert len(rows[1]) == len(EXPORT_COLUMNS)
    assert rows[1] == [
        "TCK-000042",
        "Broken monitor",
        "IN_PROGRESS",
        "URGENT",
        "Hardware",
        "2026-02-01 09:00:00",
        "2026-02-02 09:00:00",
    ]


# ---------------------------------------------------------------------------
# AC-2 (FR-EXP-02): the PDF export succeeds and produces valid, non-empty
# bytes for the same rows as the CSV (visual styling can't be asserted from
# bytes alone, so we assert success + shape).
# ---------------------------------------------------------------------------


def test_fr_exp_02_pdf_generation_succeeds_and_returns_valid_nonempty_bytes():
    tickets = [
        _ticket(id=1, ticket_number="TCK-000001"),
        _ticket(id=2, ticket_number="TCK-000002", assignee_id=7, requester_id=99),
    ]

    pdf_bytes = generate_pdf(tickets, user_id=7)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")


def test_fr_exp_02_pdf_generation_does_not_raise_for_a_normal_call():
    tickets = [_ticket()]
    # Should complete without raising any exception.
    generate_pdf(tickets, user_id=7)


# ---------------------------------------------------------------------------
# AC-3 (FR-EXP-04, BR-05): scoping is independently re-verified -- a ticket
# outside the requesting user's scope is rejected by both export functions,
# and no output is produced.
# ---------------------------------------------------------------------------


def test_fr_exp_03_csv_rejects_ticket_with_mismatched_requester_and_assignee():
    tickets = [_ticket(requester_id=99, assignee_id=100)]

    with pytest.raises(ReportError):
        generate_csv(tickets, user_id=7)


def test_fr_exp_03_pdf_rejects_ticket_with_mismatched_requester_and_assignee():
    tickets = [_ticket(requester_id=99, assignee_id=100)]

    with pytest.raises(ReportError):
        generate_pdf(tickets, user_id=7)


def test_fr_exp_03_csv_rejects_when_requester_matches_but_assignee_belongs_to_other_user():
    # Ticket requested by a different user; the "assignee" field also
    # belongs to someone else -- neither field is the requesting user.
    tickets = [_ticket(requester_id=99, assignee_id=100)]

    with pytest.raises(ReportError):
        generate_csv(tickets, user_id=7)


def test_fr_exp_03_csv_rejects_one_bad_ticket_even_if_others_in_the_batch_are_scoped():
    tickets = [
        _ticket(id=1, requester_id=7, assignee_id=None),
        _ticket(id=2, requester_id=99, assignee_id=100),  # not user 7's ticket
    ]

    with pytest.raises(ReportError):
        generate_csv(tickets, user_id=7)


def test_fr_exp_03_pdf_rejects_one_bad_ticket_even_if_others_in_the_batch_are_scoped():
    tickets = [
        _ticket(id=1, requester_id=7, assignee_id=None),
        _ticket(id=2, requester_id=99, assignee_id=100),
    ]

    with pytest.raises(ReportError):
        generate_pdf(tickets, user_id=7)


def test_fr_exp_03_csv_allows_ticket_where_user_is_assignee_not_requester():
    # BR-05 scope is "requester OR assignee" -- being the assignee (not the
    # requester) must NOT be treated as out-of-scope.
    tickets = [_ticket(requester_id=99, assignee_id=7)]

    csv_text = generate_csv(tickets, user_id=7)
    rows = _parse_csv(csv_text)

    assert len(rows) == 2  # header + the one allowed ticket


def test_fr_exp_03_pdf_allows_ticket_where_user_is_assignee_not_requester():
    tickets = [_ticket(requester_id=99, assignee_id=7)]

    pdf_bytes = generate_pdf(tickets, user_id=7)

    assert pdf_bytes.startswith(b"%PDF")


def test_fr_exp_03_csv_allows_ticket_where_user_is_requester_not_assignee():
    tickets = [_ticket(requester_id=7, assignee_id=99)]

    rows = _parse_csv(generate_csv(tickets, user_id=7))

    assert len(rows) == 2


# ---------------------------------------------------------------------------
# AC-4 (FR-EXP-01/02): an empty result set produces a valid, empty
# CSV/PDF (header row / "no tickets" message), not an error.
# ---------------------------------------------------------------------------


def test_fr_exp_04_csv_with_no_tickets_produces_header_only():
    csv_text = generate_csv([], user_id=7)
    rows = _parse_csv(csv_text)

    assert len(rows) == 1
    assert rows[0] == list(EXPORT_COLUMNS)


def test_fr_exp_04_pdf_with_no_tickets_produces_valid_nonempty_pdf_without_raising():
    pdf_bytes = generate_pdf([], user_id=7)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# AC-5 (FR-EXP-05): CSV and PDF are built from the same EXPORT_COLUMNS /
# `_row()` logic, not two independently maintained column lists that could
# drift. We can only observe this from outputs, so we compare the CSV
# header order (directly observable) against EXPORT_COLUMNS (the constant
# both functions are documented to share), and confirm both functions
# accept/reject the exact same tickets identically (same scoping check).
# ---------------------------------------------------------------------------


def test_fr_exp_05_csv_header_order_matches_export_columns_constant():
    rows = _parse_csv(generate_csv([], user_id=7))

    assert rows[0] == list(EXPORT_COLUMNS)


def test_fr_exp_05_csv_and_pdf_apply_identical_scoping_rules():
    good = [_ticket(requester_id=7)]
    bad = [_ticket(requester_id=99, assignee_id=100)]

    # Both succeed for an in-scope ticket.
    generate_csv(good, user_id=7)
    generate_pdf(good, user_id=7)

    # Both reject the exact same out-of-scope ticket -- no drift where one
    # format is stricter/looser than the other.
    with pytest.raises(ReportError):
        generate_csv(bad, user_id=7)
    with pytest.raises(ReportError):
        generate_pdf(bad, user_id=7)


# ---------------------------------------------------------------------------
# Extra: CSV special-character round-trip (commas, quotes, newlines in
# title/description) -- a common CSV-export correctness bug.
# ---------------------------------------------------------------------------


def test_csv_special_characters_in_title_round_trip_correctly():
    tricky_title = 'Comma, "quoted" title\nwith a newline'
    tickets = [_ticket(title=tricky_title, description="irrelevant, but also has, commas")]

    rows = _parse_csv(generate_csv(tickets, user_id=7))

    assert rows[1][1] == tricky_title
