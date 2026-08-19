using System.Globalization;
using System.Text;
using CsvHelper;
using PdfSharpCore.Drawing;
using PdfSharpCore.Pdf;
using TicketFlow.Core.Common.Design;
using TicketFlow.Core.Features.Tickets;

namespace TicketFlow.Core.Features.Reports;

/// <summary>Raised when a ticket outside the current user's scope is found in an export set.</summary>
public sealed class ReportError : Exception
{
    public ReportError(string message) : base(message)
    {
    }
}

/// <summary>
/// CSV/PDF export formatting over an already-filtered ticket list
/// (specs/reports-export.md, FR-EXP-01..05). No DB access of its own —
/// callers pass in tickets already fetched via TicketService.ListTicketsAsync,
/// exactly like the ticket-export skill's generate_csv/generate_pdf in the
/// Python reference app reuse tickets/service.py's list_tickets output.
/// Both formats share this one class (single row-projection, single
/// column-ordering), so a column change is made in exactly one place.
/// </summary>
public sealed class ReportService
{
    private static readonly string[] ExportColumns =
    {
        "Ticket Number", "Title", "Status", "Priority", "Category", "Created", "Updated",
    };

    private const string DateFormat = "yyyy-MM-dd HH:mm";

    /// <summary>
    /// Defense-in-depth re-check (BR-05/FR-EXP-04): even though callers are
    /// expected to have already scoped the ticket list to userId via
    /// TicketService, this independently verifies every row belongs to
    /// userId before any export bytes are produced, exactly like
    /// _assert_scoped() in the Python reference app.
    /// </summary>
    private static void AssertScoped(IReadOnlyList<Ticket> tickets, int userId)
    {
        foreach (var ticket in tickets)
        {
            if (ticket.RequesterId != userId && ticket.AssigneeId != userId)
            {
                throw new ReportError("A ticket outside the current user's scope was found in the export set.");
            }
        }
    }

    private static string[] ProjectRow(Ticket ticket) =>
        new[]
        {
            ticket.TicketNumber ?? "",
            ticket.Title,
            ticket.Status,
            ticket.Priority,
            ticket.Category,
            ticket.CreatedAt.ToString(DateFormat, CultureInfo.InvariantCulture),
            ticket.UpdatedAt.ToString(DateFormat, CultureInfo.InvariantCulture),
        };

    /// <summary>UTF-8 CSV; an empty ticket list produces a valid header-only CSV, not an error.</summary>
    public byte[] GenerateCsv(IReadOnlyList<Ticket> tickets, int userId)
    {
        AssertScoped(tickets, userId);

        using var stringWriter = new StringWriter();
        using (var csv = new CsvWriter(stringWriter, CultureInfo.InvariantCulture))
        {
            foreach (var column in ExportColumns)
            {
                csv.WriteField(column);
            }

            csv.NextRecord();

            foreach (var ticket in tickets)
            {
                foreach (var value in ProjectRow(ticket))
                {
                    csv.WriteField(value);
                }

                csv.NextRecord();
            }
        }

        return Encoding.UTF8.GetBytes(stringWriter.ToString());
    }

    /// <summary>
    /// Landscape A4, purple title bar (brand design system, BRD §12),
    /// bordered equal-width-column table. An empty ticket list still emits
    /// the title bar plus a "no matches" message, not an error.
    /// </summary>
    public byte[] GeneratePdf(IReadOnlyList<Ticket> tickets, int userId)
    {
        AssertScoped(tickets, userId);

        using var document = new PdfDocument();
        var page = document.AddPage();
        page.Orientation = PdfSharpCore.PageOrientation.Landscape;
        page.Size = PdfSharpCore.PageSize.A4;

        using var gfx = XGraphics.FromPdfPage(page);

        var titleFont = new XFont("Arial", 16, XFontStyle.Bold);
        var headerFont = new XFont("Arial", 9, XFontStyle.Bold);
        var bodyFont = new XFont("Arial", 8, XFontStyle.Regular);

        var purpleBrush = new XSolidBrush(HexToXColor(DesignTokens.ColorPurple));
        var borderPen = new XPen(XColors.Black, 0.5);

        const double margin = 24;
        const double titleBarHeight = 40;

        gfx.DrawRectangle(purpleBrush, new XRect(0, 0, page.Width, titleBarHeight));
        gfx.DrawString(
            "TicketFlow Report", titleFont, XBrushes.White,
            new XRect(margin, 0, page.Width - (2 * margin), titleBarHeight),
            XStringFormats.CenterLeft);

        var y = titleBarHeight + 20;

        if (tickets.Count == 0)
        {
            gfx.DrawString("No tickets match the current filters.", bodyFont, XBrushes.Black, new XPoint(margin, y));
        }
        else
        {
            var usableWidth = page.Width - (2 * margin);
            var columnWidth = usableWidth / ExportColumns.Length;
            const double rowHeight = 20;

            var x = margin;
            foreach (var column in ExportColumns)
            {
                var rect = new XRect(x, y, columnWidth, rowHeight);
                gfx.DrawRectangle(borderPen, rect);
                gfx.DrawString(column, headerFont, XBrushes.Black, rect, XStringFormats.Center);
                x += columnWidth;
            }

            y += rowHeight;

            foreach (var ticket in tickets)
            {
                x = margin;
                foreach (var value in ProjectRow(ticket))
                {
                    var rect = new XRect(x, y, columnWidth, rowHeight);
                    gfx.DrawRectangle(borderPen, rect);
                    gfx.DrawString(value, bodyFont, XBrushes.Black, rect, XStringFormats.CenterLeft);
                    x += columnWidth;
                }

                y += rowHeight;
            }
        }

        using var stream = new MemoryStream();
        document.Save(stream, false);
        return stream.ToArray();
    }

    private static XColor HexToXColor(string hex)
    {
        var value = hex.TrimStart('#');
        var r = Convert.ToByte(value[..2], 16);
        var g = Convert.ToByte(value.Substring(2, 2), 16);
        var b = Convert.ToByte(value.Substring(4, 2), 16);
        return XColor.FromArgb(r, g, b);
    }
}
