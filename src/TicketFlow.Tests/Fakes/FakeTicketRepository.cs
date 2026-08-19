using System.Data;
using TicketFlow.Core.Features.Tickets;

namespace TicketFlow.Tests.Fakes;

/// <summary>Scripted ITicketRepository fake — mirrors FakeUserRepository's approach.</summary>
public sealed class FakeTicketRepository : ITicketRepository
{
    public List<(int RequesterId, string Title, string Description, string Category, string Priority)> InsertedTickets { get; } = new();

    public List<(int TicketId, string TicketNumber)> UpdatedTicketNumbers { get; } = new();

    public List<(int TicketId, int ActorId, string Action, string? FieldChanged, string? OldValue, string? NewValue)> InsertedActivities { get; } = new();

    public List<(int TicketId, string NewStatus)> UpdatedStatuses { get; } = new();

    public List<(string Field, string NewValue, int TicketId)> UpdatedFields { get; } = new();

    public int NextInsertId { get; set; } = 1;

    public Ticket? GetByIdResult { get; set; }

    public TicketStatusOwners? GetStatusAndOwnersResult { get; set; }

    public TicketFieldOwners? GetFieldAndOwnersResult { get; set; }

    public Ticket? GetByIdScopedResult { get; set; }

    public Ticket? GetByNumberScopedResult { get; set; }

    public IReadOnlyList<Ticket> ListResult { get; set; } = Array.Empty<Ticket>();

    public bool ExistsScopedResult { get; set; }

    public IReadOnlyList<TicketActivity> ActivityResult { get; set; } = Array.Empty<TicketActivity>();

    public Exception? ThrowOnInsertActivity { get; set; }

    public Task<int> InsertTicketAsync(
        IDbConnection connection, int requesterId, string title, string description, string category, string priority,
        IDbTransaction? transaction = null)
    {
        InsertedTickets.Add((requesterId, title, description, category, priority));
        return Task.FromResult(NextInsertId);
    }

    public Task UpdateTicketNumberAsync(IDbConnection connection, int ticketId, string ticketNumber, IDbTransaction? transaction = null)
    {
        UpdatedTicketNumbers.Add((ticketId, ticketNumber));
        return Task.CompletedTask;
    }

    public Task InsertActivityAsync(
        IDbConnection connection, int ticketId, int actorId, string action, string? fieldChanged,
        string? oldValue, string? newValue, IDbTransaction? transaction = null)
    {
        if (ThrowOnInsertActivity is not null)
        {
            throw ThrowOnInsertActivity;
        }

        InsertedActivities.Add((ticketId, actorId, action, fieldChanged, oldValue, newValue));
        return Task.CompletedTask;
    }

    public Task<Ticket?> GetByIdAsync(IDbConnection connection, int ticketId, IDbTransaction? transaction = null) =>
        Task.FromResult(GetByIdResult);

    public Task<TicketStatusOwners?> GetStatusAndOwnersAsync(IDbConnection connection, int ticketId, IDbTransaction? transaction = null) =>
        Task.FromResult(GetStatusAndOwnersResult);

    public Task UpdateStatusAsync(IDbConnection connection, int ticketId, string newStatus, IDbTransaction? transaction = null)
    {
        UpdatedStatuses.Add((ticketId, newStatus));
        return Task.CompletedTask;
    }

    public Task<TicketFieldOwners?> GetFieldAndOwnersAsync(IDbConnection connection, string field, int ticketId, IDbTransaction? transaction = null) =>
        Task.FromResult(GetFieldAndOwnersResult);

    public Task UpdateFieldAsync(IDbConnection connection, string field, string newValue, int ticketId, IDbTransaction? transaction = null)
    {
        UpdatedFields.Add((field, newValue, ticketId));
        return Task.CompletedTask;
    }

    public Task<Ticket?> GetByIdScopedAsync(IDbConnection connection, int ticketId, int userId) =>
        Task.FromResult(GetByIdScopedResult);

    public Task<Ticket?> GetByNumberScopedAsync(IDbConnection connection, string ticketNumber, int userId) =>
        Task.FromResult(GetByNumberScopedResult);

    public Task<IReadOnlyList<Ticket>> ListAsync(IDbConnection connection, TicketListFilter filter) =>
        Task.FromResult(ListResult);

    public Task<bool> ExistsScopedAsync(IDbConnection connection, int ticketId, int userId) =>
        Task.FromResult(ExistsScopedResult);

    public Task<IReadOnlyList<TicketActivity>> GetActivityAsync(IDbConnection connection, int ticketId) =>
        Task.FromResult(ActivityResult);
}
