using System.Text;
using TicketFlow.Core.Features.Reports;
using TicketFlow.Core.Features.Tickets;
using Xunit;

namespace TicketFlow.Tests.Features.Reports;

/// <summary>Tests traced to specs/reports-export.md's acceptance criteria.</summary>
public sealed class ReportServiceTests
{
    private static Ticket MakeTicket(int id, int requesterId, int? assigneeId = null) => new()
    {
        Id = id,
        TicketNumber = $"TCK-{id:D6}",
        RequesterId = requesterId,
        AssigneeId = assigneeId,
        Title = $"Ticket {id}",
        Description = "Description",
        Category = "Bug",
        Priority = "LOW",
        Status = "OPEN",
        CreatedAt = new DateTime(2026, 1, 2, 3, 4, 0, DateTimeKind.Utc),
        UpdatedAt = new DateTime(2026, 1, 3, 4, 5, 0, DateTimeKind.Utc),
    };

    [Fact(DisplayName = "AC-1: CSV contains exactly the given rows plus a header")]
    public void GenerateCsv_ContainsHeaderAndAllRows()
    {
        var service = new ReportService();
        var tickets = new[] { MakeTicket(1, 7), MakeTicket(2, 7) };

        var bytes = service.GenerateCsv(tickets, 7);
        var csv = Encoding.UTF8.GetString(bytes);
        var lines = csv.TrimEnd().Split(Environment.NewLine.ToCharArray(), StringSplitOptions.RemoveEmptyEntries);

        Assert.Equal(3, lines.Length); // header + 2 rows
        Assert.Contains("Ticket Number", lines[0]);
        Assert.Contains("TCK-000001", lines[1]);
        Assert.Contains("TCK-000002", lines[2]);
    }

    [Fact(DisplayName = "AC-4: an empty ticket list produces a valid header-only CSV, not an error")]
    public void GenerateCsv_EmptyList_ProducesHeaderOnly()
    {
        var service = new ReportService();

        var bytes = service.GenerateCsv(Array.Empty<Ticket>(), 7);
        var csv = Encoding.UTF8.GetString(bytes);
        var lines = csv.TrimEnd().Split(Environment.NewLine.ToCharArray(), StringSplitOptions.RemoveEmptyEntries);

        Assert.Single(lines);
        Assert.Contains("Ticket Number", lines[0]);
    }

    [Fact(DisplayName = "AC-3: a ticket outside the current user's scope is rejected before any bytes are produced (CSV)")]
    public void GenerateCsv_TicketOutsideScope_ThrowsReportError()
    {
        var service = new ReportService();
        var tickets = new[] { MakeTicket(1, 7), MakeTicket(2, 999) };

        Assert.Throws<ReportError>(() => service.GenerateCsv(tickets, 7));
    }

    [Fact(DisplayName = "a ticket where the user is the assignee (not requester) is still in-scope")]
    public void GenerateCsv_AssignedTicket_IsInScope()
    {
        var service = new ReportService();
        var tickets = new[] { MakeTicket(1, 999, assigneeId: 7) };

        var bytes = service.GenerateCsv(tickets, 7);

        Assert.NotEmpty(bytes);
    }

    [Fact(DisplayName = "AC-2: PDF export produces non-empty, valid PDF bytes for a non-empty ticket list")]
    public void GeneratePdf_NonEmptyList_ProducesPdfBytes()
    {
        var service = new ReportService();
        var tickets = new[] { MakeTicket(1, 7) };

        var bytes = service.GeneratePdf(tickets, 7);

        Assert.NotEmpty(bytes);
        // PDF files start with the "%PDF-" magic header.
        Assert.Equal("%PDF-", Encoding.ASCII.GetString(bytes, 0, 5));
    }

    [Fact(DisplayName = "AC-4: an empty ticket list still produces a valid PDF, not an error")]
    public void GeneratePdf_EmptyList_ProducesValidPdf()
    {
        var service = new ReportService();

        var bytes = service.GeneratePdf(Array.Empty<Ticket>(), 7);

        Assert.NotEmpty(bytes);
        Assert.Equal("%PDF-", Encoding.ASCII.GetString(bytes, 0, 5));
    }

    [Fact(DisplayName = "AC-3: a ticket outside the current user's scope is rejected before any bytes are produced (PDF)")]
    public void GeneratePdf_TicketOutsideScope_ThrowsReportError()
    {
        var service = new ReportService();
        var tickets = new[] { MakeTicket(1, 999) };

        Assert.Throws<ReportError>(() => service.GeneratePdf(tickets, 7));
    }
}
