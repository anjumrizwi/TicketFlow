using System.Data;
using Dapper;

namespace TicketFlow.Core.Features.SeedData;

public sealed class SqlSeedDataRepository : ISeedDataRepository
{
    public async Task<IReadOnlyList<int>> FindDemoUserIdsAsync(IDbConnection connection, string usernamePrefix)
    {
        var ids = await connection.QueryAsync<int>(
            "SELECT id FROM users WHERE username LIKE @pattern",
            new { pattern = $"{usernamePrefix}%" });
        return ids.AsList();
    }

    public async Task<IReadOnlyList<int>> FindTicketIdsForUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds)
    {
        if (userIds.Count == 0)
        {
            return Array.Empty<int>();
        }

        var ids = await connection.QueryAsync<int>(
            "SELECT id FROM tickets WHERE requester_id IN @userIds",
            new { userIds });
        return ids.AsList();
    }

    public Task DeleteTicketActivityForTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds)
    {
        if (ticketIds.Count == 0)
        {
            return Task.CompletedTask;
        }

        return connection.ExecuteAsync("DELETE FROM ticket_activity WHERE ticket_id IN @ticketIds", new { ticketIds });
    }

    public Task DeleteTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds)
    {
        if (ticketIds.Count == 0)
        {
            return Task.CompletedTask;
        }

        return connection.ExecuteAsync("DELETE FROM tickets WHERE id IN @ticketIds", new { ticketIds });
    }

    public Task DeleteUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds)
    {
        if (userIds.Count == 0)
        {
            return Task.CompletedTask;
        }

        return connection.ExecuteAsync("DELETE FROM users WHERE id IN @userIds", new { userIds });
    }
}
