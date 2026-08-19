using TicketFlow.Core.Features.Tickets;

namespace TicketFlow.Core.Features.Dashboard;

public sealed record DashboardData
{
    public required IReadOnlyDictionary<string, int> StatusCounts { get; init; }
    public required IReadOnlyList<Ticket> RecentTickets { get; init; }
}
