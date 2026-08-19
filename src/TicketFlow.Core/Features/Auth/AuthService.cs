using System.Data;
using TicketFlow.Core.Common.Db;

namespace TicketFlow.Core.Features.Auth;

/// <summary>Raised for invalid input, duplicate accounts, or failed login.</summary>
public sealed class AuthError : Exception
{
    public AuthError(string message) : base(message)
    {
    }
}

/// <summary>
/// Registration and login logic (specs/auth.md). FR-AUTH-01..03,
/// FR-AUTH-02 (bcrypt only), NFR-01 (no plaintext password ever
/// logged/persisted). Callers own the connection's lifecycle. Direct
/// port of features/auth/service.py from the Python reference app.
/// </summary>
public sealed class AuthService
{
    public const string RegisterConflictMessage = "That username or email is already registered.";
    public const string LoginFailureMessage = "Invalid username or password.";

    // Verified against a real login attempt so a nonexistent account takes
    // roughly as long to reject as a wrong password does (AC-4: identical
    // failure whether or not the account exists).
    private static readonly string DummyHash = BCrypt.Net.BCrypt.HashPassword("dummy-password");

    private readonly IUserRepository _users;

    public AuthService(IUserRepository users)
    {
        _users = users;
    }

    public static string HashPassword(string password) => BCrypt.Net.BCrypt.HashPassword(password);

    public static bool VerifyPassword(string password, string passwordHash) =>
        BCrypt.Net.BCrypt.Verify(password, passwordHash);

    private static void RequireNonEmpty(string? value, string fieldName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new AuthError($"{fieldName} is required.");
        }
    }

    /// <summary>Create a Requester account. Throws AuthError on invalid/duplicate input.</summary>
    public async Task<User> RegisterUserAsync(IDbConnection connection, string username, string email, string password)
    {
        RequireNonEmpty(username, "Username");
        RequireNonEmpty(email, "Email");
        RequireNonEmpty(password, "Password");

        username = username.Trim();
        email = email.Trim();
        var passwordHash = HashPassword(password);

        using var transaction = connection.BeginTransaction();
        int userId;
        try
        {
            if (await _users.ExistsByUsernameOrEmailAsync(connection, username, email, transaction))
            {
                transaction.Rollback();
                throw new AuthError(RegisterConflictMessage);
            }

            try
            {
                userId = await _users.InsertAsync(connection, username, email, passwordHash, transaction);
            }
            catch (UniqueConstraintViolationException)
            {
                // A concurrent registration won the race between the check above
                // and this insert; the unique constraint is the source of truth.
                transaction.Rollback();
                throw new AuthError(RegisterConflictMessage);
            }

            transaction.Commit();
        }
        catch (AuthError)
        {
            throw; // already rolled back above
        }
        catch
        {
            transaction.Rollback();
            throw;
        }

        var user = await _users.GetByIdAsync(connection, userId);
        return user!;
    }

    /// <summary>
    /// Returns the user row on success. Throws AuthError on any failure,
    /// with an identical message whether the account exists or not.
    /// </summary>
    public async Task<User> AuthenticateUserAsync(IDbConnection connection, string identifier, string password)
    {
        RequireNonEmpty(identifier, "Username");
        RequireNonEmpty(password, "Password");

        identifier = identifier.Trim();
        var user = await _users.FindForLoginAsync(connection, identifier);

        if (user is null)
        {
            VerifyPassword(password, DummyHash);
            throw new AuthError(LoginFailureMessage);
        }

        if (!VerifyPassword(password, user.PasswordHash!))
        {
            throw new AuthError(LoginFailureMessage);
        }

        return user with { PasswordHash = null };
    }
}
