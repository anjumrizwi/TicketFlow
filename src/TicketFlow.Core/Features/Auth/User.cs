namespace TicketFlow.Core.Features.Auth;

public static class Roles
{
    public const string Requester = "REQUESTER";
    public const string SupportAgent = "SUPPORT_AGENT";
}

/// <summary>
/// A user row. PasswordHash is null on any instance handed back to a
/// caller outside the auth layer itself (see AuthService.AuthenticateUserAsync) —
/// never serialize/log this field.
/// </summary>
public sealed record User
{
    public required int Id { get; init; }
    public required string Username { get; init; }
    public required string Email { get; init; }
    public string? PasswordHash { get; init; }
    public required string Role { get; init; }
    public required DateTime CreatedAt { get; init; }
}
