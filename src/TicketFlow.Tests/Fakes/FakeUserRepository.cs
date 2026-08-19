using System.Data;
using TicketFlow.Core.Features.Auth;

namespace TicketFlow.Tests.Fakes;

/// <summary>
/// Scripted IUserRepository fake — records every call so tests can assert
/// what was/wasn't sent to "the database" (e.g. "no INSERT happened"),
/// mirroring tests/conftest.py's FakeCursor.executed list in the Python
/// reference app.
/// </summary>
public sealed class FakeUserRepository : IUserRepository
{
    public List<(string Username, string Email, string PasswordHash)> InsertedUsers { get; } = new();

    public List<(string Username, string Email, string PasswordHash, string Role)> InsertedUsersWithRole { get; } = new();

    public bool ExistsResult { get; set; }

    public User? GetByIdResult { get; set; }

    public User? FindForLoginResult { get; set; }

    public Exception? ThrowOnInsert { get; set; }

    private int _nextId = 1;

    public Task<bool> ExistsByUsernameOrEmailAsync(
        IDbConnection connection, string username, string email, IDbTransaction? transaction = null) =>
        Task.FromResult(ExistsResult);

    public Task<int> InsertAsync(
        IDbConnection connection, string username, string email, string passwordHash, IDbTransaction? transaction = null)
    {
        if (ThrowOnInsert is not null)
        {
            throw ThrowOnInsert;
        }

        InsertedUsers.Add((username, email, passwordHash));
        return Task.FromResult(_nextId++);
    }

    public Task<int> InsertWithRoleAsync(
        IDbConnection connection, string username, string email, string passwordHash, string role,
        IDbTransaction? transaction = null)
    {
        InsertedUsersWithRole.Add((username, email, passwordHash, role));
        return Task.FromResult(_nextId++);
    }

    public Task<User?> GetByIdAsync(IDbConnection connection, int id, IDbTransaction? transaction = null) =>
        Task.FromResult(GetByIdResult);

    public Task<User?> FindForLoginAsync(IDbConnection connection, string identifier, IDbTransaction? transaction = null) =>
        Task.FromResult(FindForLoginResult);
}
