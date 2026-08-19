using System.Data;

namespace TicketFlow.Core.Features.Auth;

/// <summary>
/// Holds every Dapper call this feature needs. AuthService depends on
/// this interface, not Dapper directly, so tests can fake it (mirrors
/// tests/conftest.py's FakeConnection/FakeCursor pattern in the Python
/// reference app). Every method takes the transaction it should
/// participate in — passing null means "no transaction, standalone call."
/// </summary>
public interface IUserRepository
{
    Task<bool> ExistsByUsernameOrEmailAsync(
        IDbConnection connection, string username, string email, IDbTransaction? transaction = null);

    Task<int> InsertAsync(
        IDbConnection connection, string username, string email, string passwordHash, IDbTransaction? transaction = null);

    /// <summary>
    /// Insert a user with an explicit role. Only self-registration
    /// (InsertAsync above) hardcodes role='REQUESTER'; seed-data is the
    /// one caller that ever creates a SUPPORT_AGENT account, matching
    /// features/seed_data/service.py's separate raw INSERT in the Python
    /// reference app (there is no in-app role picker/self-escalation).
    /// </summary>
    Task<int> InsertWithRoleAsync(
        IDbConnection connection, string username, string email, string passwordHash, string role,
        IDbTransaction? transaction = null);

    Task<User?> GetByIdAsync(IDbConnection connection, int id, IDbTransaction? transaction = null);

    Task<User?> FindForLoginAsync(IDbConnection connection, string identifier, IDbTransaction? transaction = null);
}
