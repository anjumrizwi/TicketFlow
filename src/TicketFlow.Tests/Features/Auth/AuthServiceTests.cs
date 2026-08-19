using TicketFlow.Core.Common.Db;
using TicketFlow.Core.Features.Auth;
using TicketFlow.Tests.Fakes;
using Xunit;

namespace TicketFlow.Tests.Features.Auth;

/// <summary>
/// Tests traced to specs/auth.md's acceptance criteria (AC-1..AC-4 are
/// exercisable at the AuthService level; AC-5..AC-7 are session/routing
/// behavior covered by the Blazor auth-gate wiring itself, not unit
/// tests here — consistent with how the Python reference app's
/// tests/test_auth_service.py scopes its own unit tests).
/// </summary>
public sealed class AuthServiceTests
{
    private static (AuthService Service, FakeUserRepository Users, FakeDbConnection Connection) CreateSut()
    {
        var users = new FakeUserRepository();
        var service = new AuthService(users);
        var connection = new FakeDbConnection();
        return (service, users, connection);
    }

    [Fact(DisplayName = "AC-1: registering with an existing username/email is rejected, non-enumerating")]
    public async Task Ac1_RegisterWithDuplicateUsernameOrEmail_IsRejected()
    {
        var (service, users, connection) = CreateSut();
        users.ExistsResult = true;

        var ex = await Assert.ThrowsAsync<AuthError>(
            () => service.RegisterUserAsync(connection, "alice", "alice@example.com", "Sup3rSecret!"));

        Assert.Equal(AuthService.RegisterConflictMessage, ex.Message);
        Assert.Empty(users.InsertedUsers);
        Assert.Equal(1, connection.RollbackCount);
        Assert.Equal(0, connection.CommitCount);
    }

    [Fact(DisplayName = "AC-1 (race): a concurrent duplicate insert is also rejected with the same message")]
    public async Task Ac1_ConcurrentDuplicateInsert_IsRejectedAfterRollback()
    {
        var (service, users, connection) = CreateSut();
        users.ExistsResult = false; // pre-check passes...
        users.ThrowOnInsert = new UniqueConstraintViolationException("dup"); // ...but a concurrent insert won the race

        var ex = await Assert.ThrowsAsync<AuthError>(
            () => service.RegisterUserAsync(connection, "alice", "alice@example.com", "Sup3rSecret!"));

        Assert.Equal(AuthService.RegisterConflictMessage, ex.Message);
        Assert.Equal(1, connection.RollbackCount);
        Assert.Equal(0, connection.CommitCount);
    }

    [Theory(DisplayName = "AC-2: empty username/email/password is rejected; no row is written")]
    [InlineData("", "alice@example.com", "Sup3rSecret!")]
    [InlineData("alice", "", "Sup3rSecret!")]
    [InlineData("alice", "alice@example.com", "")]
    [InlineData("   ", "alice@example.com", "Sup3rSecret!")]
    public async Task Ac2_EmptyRequiredField_IsRejectedWithNoInsert(string username, string email, string password)
    {
        var (service, users, connection) = CreateSut();

        await Assert.ThrowsAsync<AuthError>(() => service.RegisterUserAsync(connection, username, email, password));

        Assert.Empty(users.InsertedUsers);
    }

    [Fact(DisplayName = "AC-3: a valid registration creates a Requester with a bcrypt hash, never the raw password")]
    public async Task Ac3_ValidRegistration_CreatesRequesterWithBcryptHash()
    {
        var (service, users, connection) = CreateSut();
        users.ExistsResult = false;
        var expected = new User
        {
            Id = 1,
            Username = "alice",
            Email = "alice@example.com",
            Role = Roles.Requester,
            CreatedAt = DateTime.UtcNow,
        };
        users.GetByIdResult = expected;

        var created = await service.RegisterUserAsync(connection, "alice", "alice@example.com", "Sup3rSecret!");

        Assert.Same(expected, created);
        var (_, _, storedHash) = Assert.Single(users.InsertedUsers);
        Assert.NotEqual("Sup3rSecret!", storedHash);
        Assert.True(AuthService.VerifyPassword("Sup3rSecret!", storedHash));
        Assert.Equal(1, connection.CommitCount);
    }

    [Fact(DisplayName = "AC-4: correct credentials log in successfully")]
    public async Task Ac4_CorrectCredentials_LogsIn()
    {
        var (service, users, connection) = CreateSut();
        var hash = AuthService.HashPassword("Sup3rSecret!");
        users.FindForLoginResult = new User
        {
            Id = 1,
            Username = "alice",
            Email = "alice@example.com",
            PasswordHash = hash,
            Role = Roles.Requester,
            CreatedAt = DateTime.UtcNow,
        };

        var user = await service.AuthenticateUserAsync(connection, "alice", "Sup3rSecret!");

        Assert.Equal("alice", user.Username);
        Assert.Null(user.PasswordHash);
    }

    [Fact(DisplayName = "AC-4: wrong password on an existing account fails with the generic message")]
    public async Task Ac4_WrongPasswordForExistingAccount_FailsGenerically()
    {
        var (service, users, connection) = CreateSut();
        users.FindForLoginResult = new User
        {
            Id = 1,
            Username = "alice",
            Email = "alice@example.com",
            PasswordHash = AuthService.HashPassword("Sup3rSecret!"),
            Role = Roles.Requester,
            CreatedAt = DateTime.UtcNow,
        };

        var ex = await Assert.ThrowsAsync<AuthError>(
            () => service.AuthenticateUserAsync(connection, "alice", "WrongPassword!"));

        Assert.Equal(AuthService.LoginFailureMessage, ex.Message);
    }

    [Fact(DisplayName = "AC-4: a nonexistent account fails with the identical generic message (no enumeration)")]
    public async Task Ac4_NonexistentAccount_FailsWithIdenticalMessage()
    {
        var (service, users, connection) = CreateSut();
        users.FindForLoginResult = null;

        var ex = await Assert.ThrowsAsync<AuthError>(
            () => service.AuthenticateUserAsync(connection, "nobody", "WhateverPassword!"));

        Assert.Equal(AuthService.LoginFailureMessage, ex.Message);
    }
}
