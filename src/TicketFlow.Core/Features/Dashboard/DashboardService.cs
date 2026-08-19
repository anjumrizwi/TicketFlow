using System.Data;
using TicketFlow.Core.Features.Tickets;

namespace TicketFlow.Core.Features.Dashboard;

/// <summary>
/// Home page data (specs/dashboard.md, FR-DASH-01..05). Deliberately
/// reuses TicketService.ListTicketsAsync rather than a separate query
/// path, so the dashboard can never drift from Ticket List/BR-05 scoping
/// — direct port of features/dashboard/service.py's get_dashboard_data()
/// in the Python reference app.
/// </summary>
public sealed class DashboardService
{
    private const int RecentTicketLimit = 5;

    private readonly TicketService _tickets;

    public DashboardService(TicketService tickets)
    {
        _tickets = tickets;
    }

    /// <summary>
    /// Always a fresh, live, user-scoped query — no caching layer, so a
    /// change made just before navigating back here is never stale
    /// (specs/dashboard.md AC-5).
    /// </summary>
    public async Task<DashboardData> GetDashboardDataAsync(IDbConnection connection, int userId)
    {
        var tickets = await _tickets.ListTicketsAsync(connection, new TicketListFilter { UserId = userId });

        var counts = TicketConstants.Statuses.ToDictionary(
            status => status,
            status => tickets.Count(t => t.Status == status));

        var recent = tickets.Take(RecentTicketLimit).ToList();

        return new DashboardData { StatusCounts = counts, RecentTickets = recent };
    }
}
