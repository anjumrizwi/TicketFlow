using System.Data;
using TicketFlow.Core.Features.SeedData;

namespace TicketFlow.Tests.Fakes;

public sealed class FakeSeedDataRepository : ISeedDataRepository
{
    public IReadOnlyList<int> DemoUserIds { get; set; } = Array.Empty<int>();

    public IReadOnlyList<int> TicketIdsForUsers { get; set; } = Array.Empty<int>();

    public List<IReadOnlyList<int>> DeletedTicketActivityCalls { get; } = new();

    public List<IReadOnlyList<int>> DeletedTicketsCalls { get; } = new();

    public List<IReadOnlyList<int>> DeletedUsersCalls { get; } = new();

    public Task<IReadOnlyList<int>> FindDemoUserIdsAsync(IDbConnection connection, string usernamePrefix) =>
        Task.FromResult(DemoUserIds);

    public Task<IReadOnlyList<int>> FindTicketIdsForUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds) =>
        Task.FromResult(TicketIdsForUsers);

    public Task DeleteTicketActivityForTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds)
    {
        DeletedTicketActivityCalls.Add(ticketIds);
        return Task.CompletedTask;
    }

    public Task DeleteTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds)
    {
        DeletedTicketsCalls.Add(ticketIds);
        return Task.CompletedTask;
    }

    public Task DeleteUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds)
    {
        DeletedUsersCalls.Add(userIds);
        return Task.CompletedTask;
    }
}
