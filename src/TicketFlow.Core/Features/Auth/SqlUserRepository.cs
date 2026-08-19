using System.Data;
using Dapper;
using Microsoft.Data.SqlClient;
using TicketFlow.Core.Common.Db;

namespace TicketFlow.Core.Features.Auth;

public sealed class SqlUserRepository : IUserRepository
{
    // SQL Server error numbers for a unique-constraint/unique-index violation.
    private const int UniqueConstraintViolation = 2627;
    private const int UniqueIndexViolation = 2601;

    public async Task<bool> ExistsByUsernameOrEmailAsync(
        IDbConnection connection, string username, string email, IDbTransaction? transaction = null)
    {
        var id = await connection.ExecuteScalarAsync<int?>(
            "SELECT TOP 1 id FROM users WHERE username = @username OR email = @email",
            new { username, email },
            transaction);
        return id is not null;
    }

    public async Task<int> InsertAsync(
        IDbConnection connection, string username, string email, string passwordHash, IDbTransaction? transaction = null)
    {
        try
        {
            return await connection.ExecuteScalarAsync<int>(
                """
                INSERT INTO users (username, email, password_hash, role)
                OUTPUT INSERTED.id
                VALUES (@username, @email, @passwordHash, 'REQUESTER')
                """,
                new { username, email, passwordHash },
                transaction);
        }
        catch (SqlException ex) when (ex.Number is UniqueConstraintViolation or UniqueIndexViolation)
        {
            throw new UniqueConstraintViolationException(
                "A row with the same username or email already exists.", ex);
        }
    }

    public async Task<int> InsertWithRoleAsync(
        IDbConnection connection, string username, string email, string passwordHash, string role,
        IDbTransaction? transaction = null)
    {
        try
        {
            return await connection.ExecuteScalarAsync<int>(
                """
                INSERT INTO users (username, email, password_hash, role)
                OUTPUT INSERTED.id
                VALUES (@username, @email, @passwordHash, @role)
                """,
                new { username, email, passwordHash, role },
                transaction);
        }
        catch (SqlException ex) when (ex.Number is UniqueConstraintViolation or UniqueIndexViolation)
        {
            throw new UniqueConstraintViolationException(
                "A row with the same username or email already exists.", ex);
        }
    }

    public Task<User?> GetByIdAsync(IDbConnection connection, int id, IDbTransaction? transaction = null)
    {
        return connection.QuerySingleOrDefaultAsync<User?>(
            "SELECT id AS Id, username AS Username, email AS Email, role AS Role, created_at AS CreatedAt " +
            "FROM users WHERE id = @id",
            new { id },
            transaction);
    }

    public Task<User?> FindForLoginAsync(IDbConnection connection, string identifier, IDbTransaction? transaction = null)
    {
        return connection.QuerySingleOrDefaultAsync<User?>(
            "SELECT id AS Id, username AS Username, email AS Email, password_hash AS PasswordHash, " +
            "role AS Role, created_at AS CreatedAt FROM users WHERE username = @identifier OR email = @identifier",
            new { identifier },
            transaction);
    }
}
