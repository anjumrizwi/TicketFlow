using TicketFlow.Core.Features.Dashboard;
using TicketFlow.Core.Features.Tickets;
using TicketFlow.Tests.Fakes;
using Xunit;

namespace TicketFlow.Tests.Features.Dashboard;

/// <summary>Tests traced to specs/dashboard.md's acceptance criteria.</summary>
public sealed class DashboardServiceTests
{
    private static Ticket MakeTicket(int id, string status, DateTime createdAt) => new()
    {
        Id = id,
        TicketNumber = $"TCK-{id:D6}",
        RequesterId = 1,
        Title = $"Ticket {id}",
        Description = "Description",
        Category = "Bug",
        Priority = "LOW",
        Status = status,
        CreatedAt = createdAt,
        UpdatedAt = createdAt,
    };

    [Fact(DisplayName = "AC-2: status counts match the actual per-status ticket counts")]
    public async Task GetDashboardData_CountsMatchTicketsPerStatus()
    {
        var tickets = new FakeTicketRepository
        {
            ListResult = new[]
            {
                MakeTicket(1, "OPEN", DateTime.UtcNow.AddMinutes(-1)),
                MakeTicket(2, "OPEN", DateTime.UtcNow.AddMinutes(-2)),
                MakeTicket(3, "IN_PROGRESS", DateTime.UtcNow.AddMinutes(-3)),
                MakeTicket(4, "CLOSED", DateTime.UtcNow.AddMinutes(-4)),
            },
        };
        var service = new DashboardService(new TicketService(tickets));
        var connection = new FakeDbConnection();

        var data = await service.GetDashboardDataAsync(connection, 1);

        Assert.Equal(2, data.StatusCounts["OPEN"]);
        Assert.Equal(1, data.StatusCounts["IN_PROGRESS"]);
        Assert.Equal(0, data.StatusCounts["RESOLVED"]);
        Assert.Equal(1, data.StatusCounts["CLOSED"]);
    }

    [Fact(DisplayName = "AC-3: only the 5 most recent tickets are returned, newest-first order preserved")]
    public async Task GetDashboardData_ReturnsAtMostFiveMostRecentTickets()
    {
        // ListTicketsAsync already returns newest-first (ORDER BY created_at DESC);
        // the fake mirrors that ordering, and DashboardService just takes the first 5.
        var now = DateTime.UtcNow;
        var allTickets = Enumerable.Range(1, 7)
            .Select(i => MakeTicket(i, "OPEN", now.AddMinutes(-i)))
            .ToArray();
        var tickets = new FakeTicketRepository { ListResult = allTickets };
        var service = new DashboardService(new TicketService(tickets));
        var connection = new FakeDbConnection();

        var data = await service.GetDashboardDataAsync(connection, 1);

        Assert.Equal(5, data.RecentTickets.Count);
        Assert.Equal(allTickets.Take(5).Select(t => t.Id), data.RecentTickets.Select(t => t.Id));
    }

    [Fact(DisplayName = "no tickets yet: counts are all zero and the recent list is empty")]
    public async Task GetDashboardData_NoTickets_AllCountsZero()
    {
        var tickets = new FakeTicketRepository { ListResult = Array.Empty<Ticket>() };
        var service = new DashboardService(new TicketService(tickets));
        var connection = new FakeDbConnection();

        var data = await service.GetDashboardDataAsync(connection, 1);

        Assert.All(TicketConstants.Statuses, status => Assert.Equal(0, data.StatusCounts[status]));
        Assert.Empty(data.RecentTickets);
    }
}
