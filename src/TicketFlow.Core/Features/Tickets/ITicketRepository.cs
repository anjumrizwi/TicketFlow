using System.Data;

namespace TicketFlow.Core.Features.Tickets;

public sealed record TicketStatusOwners
{
    public required string Status { get; init; }
    public required int RequesterId { get; init; }
    public int? AssigneeId { get; init; }
}

public sealed record TicketFieldOwners
{
    public required string CurrentValue { get; init; }
    public required int RequesterId { get; init; }
    public int? AssigneeId { get; init; }
}

/// <summary>
/// Holds every Dapper call this feature needs — TicketService depends on
/// this interface, not Dapper directly, so tests can fake it. Every
/// write method takes the transaction it should participate in.
/// </summary>
public interface ITicketRepository
{
    Task<int> InsertTicketAsync(
        IDbConnection connection, int requesterId, string title, string description, string category, string priority,
        IDbTransaction? transaction = null);

    Task UpdateTicketNumberAsync(
        IDbConnection connection, int ticketId, string ticketNumber, IDbTransaction? transaction = null);

    Task InsertActivityAsync(
        IDbConnection connection, int ticketId, int actorId, string action, string? fieldChanged,
        string? oldValue, string? newValue, IDbTransaction? transaction = null);

    Task<Ticket?> GetByIdAsync(IDbConnection connection, int ticketId, IDbTransaction? transaction = null);

    Task<TicketStatusOwners?> GetStatusAndOwnersAsync(
        IDbConnection connection, int ticketId, IDbTransaction? transaction = null);

    Task UpdateStatusAsync(
        IDbConnection connection, int ticketId, string newStatus, IDbTransaction? transaction = null);

    Task<TicketFieldOwners?> GetFieldAndOwnersAsync(
        IDbConnection connection, string field, int ticketId, IDbTransaction? transaction = null);

    Task UpdateFieldAsync(
        IDbConnection connection, string field, string newValue, int ticketId, IDbTransaction? transaction = null);

    Task<Ticket?> GetByIdScopedAsync(IDbConnection connection, int ticketId, int userId);

    Task<Ticket?> GetByNumberScopedAsync(IDbConnection connection, string ticketNumber, int userId);

    Task<IReadOnlyList<Ticket>> ListAsync(IDbConnection connection, TicketListFilter filter);

    Task<bool> ExistsScopedAsync(IDbConnection connection, int ticketId, int userId);

    Task<IReadOnlyList<TicketActivity>> GetActivityAsync(IDbConnection connection, int ticketId);
}
