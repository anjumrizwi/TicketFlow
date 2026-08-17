"""CSV/PDF ticket export (specs/reports-export.md; the `ticket-export` skill).

FR-EXP-01..05, BR-05. This module never queries the database itself —
callers pass the already-filtered rows from
`features.tickets.service.list_tickets` (so CSV/PDF always reflect exactly
the same result set as the Ticket List feature, per the spec's "no
independent query logic" requirement) plus the requesting user's id, which
is used to independently re-verify scope (AC-3) even if the caller's
filter state were somehow wrong — never trust the input blindly.
"""
import csv
import io

from fpdf import FPDF

from common.design import COLOR_PURPLE

EXPORT_COLUMNS = ("Ticket Number", "Title", "Status", "Priority", "Category", "Created", "Updated")


class ReportError(Exception):
    """Raised when an export would include a ticket outside the requesting user's scope."""


def _assert_scoped(tickets, user_id):
    for ticket in tickets:
        if user_id not in (ticket["requester_id"], ticket["assignee_id"]):
            raise ReportError("Refusing to export a ticket outside the requesting user's scope.")


def _row(ticket):
    return (
        ticket["ticket_number"],
        ticket["title"],
        ticket["status"],
        ticket["priority"],
        ticket["category"],
        str(ticket["created_at"]),
        str(ticket["updated_at"]),
    )


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def generate_csv(tickets, user_id):
    """Return CSV text for exactly the given (already-filtered) tickets,
    after independently re-verifying each belongs to `user_id` (BR-05,
    FR-EXP-04). An empty ticket list still produces a valid header-only
    CSV, never an error (AC-4)."""
    _assert_scoped(tickets, user_id)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for ticket in tickets:
        writer.writerow(_row(ticket))
    return buffer.getvalue()


def generate_pdf(tickets, user_id):
    """Return PDF bytes for exactly the given (already-filtered) tickets,
    after independently re-verifying scope (BR-05, FR-EXP-04), styled per
    the brand design system (BRD §12): white background, black text,
    purple header, no gradients. An empty ticket list still produces a
    valid PDF with the header and an explanatory line, never an error
    (AC-4)."""
    _assert_scoped(tickets, user_id)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    purple = _hex_to_rgb(COLOR_PURPLE)
    pdf.set_fill_color(*purple)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "TicketFlow Report", fill=True)
    pdf.ln(16)

    pdf.set_text_color(0, 0, 0)

    if not tickets:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, "No tickets match the current filters.")
        return bytes(pdf.output())

    col_width = pdf.epw / len(EXPORT_COLUMNS)

    pdf.set_font("Helvetica", "B", 10)
    for column in EXPORT_COLUMNS:
        pdf.cell(col_width, 8, column, border=1)
    pdf.ln(8)

    pdf.set_font("Helvetica", "", 9)
    for ticket in tickets:
        for value in _row(ticket):
            pdf.cell(col_width, 8, str(value), border=1)
        pdf.ln(8)

    return bytes(pdf.output())
