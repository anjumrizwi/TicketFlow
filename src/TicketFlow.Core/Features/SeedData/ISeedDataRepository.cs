using System.Data;

namespace TicketFlow.Core.Features.SeedData;

/// <summary>
/// Admin/maintenance queries specific to seeding — never touches
/// non-seeded (real) user data, since every query here is scoped to the
/// reserved demo_ username prefix. Direct port of the raw-SQL cleanup in
/// features/seed_data/service.py's _clear_seeded_data() in the Python
/// reference app.
/// </summary>
public interface ISeedDataRepository
{
    Task<IReadOnlyList<int>> FindDemoUserIdsAsync(IDbConnection connection, string usernamePrefix);

    Task<IReadOnlyList<int>> FindTicketIdsForUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds);

    Task DeleteTicketActivityForTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds);

    Task DeleteTicketsAsync(IDbConnection connection, IReadOnlyList<int> ticketIds);

    Task DeleteUsersAsync(IDbConnection connection, IReadOnlyList<int> userIds);
}
