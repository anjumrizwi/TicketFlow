using System.Data;

namespace TicketFlow.Core.Features.Tickets;

/// <summary>Raised for invalid ticket input or a ticket that doesn't exist.</summary>
public sealed class TicketError : Exception
{
    public TicketError(string message) : base(message)
    {
    }
}

/// <summary>Raised for an illegal status transition (BR-02/BR-03).</summary>
public sealed class TransitionError : Exception
{
    public TransitionError(string message) : base(message)
    {
    }
}

/// <summary>Raised when the actor is not the ticket's requester or assignee (BR-05).</summary>
public sealed class TicketPermissionError : Exception
{
    public TicketPermissionError(string message) : base(message)
    {
    }
}

/// <summary>
/// Ticket creation, status-transition, field-update, and list/search logic
/// (specs/tickets.md, specs/status-workflow.md, specs/list-search.md).
/// Direct port of features/tickets/service.py from the Python reference app.
///
/// FR-TKT-01..05, BR-01 (new ticket starts OPEN).
/// FR-STAT-01..06, BR-02/BR-03 (legal transitions, CLOSED is terminal),
/// BR-04/FR-STAT-05 (every change writes exactly one activity row, in the
/// same transaction as the change, rolled back together on failure), BR-05
/// (a user may only modify a ticket they are requester or assignee for).
/// FR-LIST-01..05 (composable status/priority/category/date filters plus
/// free-text search, always scoped to the user as requester or assignee).
/// </summary>
public sealed class TicketService
{
    private readonly ITicketRepository _tickets;

    public TicketService(ITicketRepository tickets)
    {
        _tickets = tickets;
    }

    private static void RequireNonEmpty(string? value, string fieldName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new TicketError($"{fieldName} is required.");
        }
    }

    private static void RequireOwner(int requesterId, int? assigneeId, int actorId)
    {
        if (actorId != requesterId && actorId != assigneeId)
        {
            throw new TicketPermissionError(
                "You cannot modify a ticket you are not the requester or assignee for.");
        }
    }

    /// <summary>Create a ticket owned by requesterId. Throws TicketError on invalid input.</summary>
    public async Task<Ticket> CreateTicketAsync(
        IDbConnection connection, int requesterId, string title, string description, string category, string priority)
    {
        RequireNonEmpty(title, "Title");
        RequireNonEmpty(description, "Description");

        if (!TicketConstants.Categories.Contains(category))
        {
            throw new TicketError("Category must be one of: " + string.Join(", ", TicketConstants.Categories));
        }

        if (!TicketConstants.Priorities.Contains(priority))
        {
            throw new TicketError("Priority must be one of: " + string.Join(", ", TicketConstants.Priorities));
        }

        title = title.Trim();
        description = description.Trim();

        using var transaction = connection.BeginTransaction();
        Ticket ticket;
        try
        {
            var ticketId = await _tickets.InsertTicketAsync(
                connection, requesterId, title, description, category, priority, transaction);
            var ticketNumber = $"TCK-{ticketId:D6}";

            await _tickets.UpdateTicketNumberAsync(connection, ticketId, ticketNumber, transaction);
            await _tickets.InsertActivityAsync(
                connection, ticketId, requesterId, "CREATED", null, null, "OPEN", transaction);

            ticket = (await _tickets.GetByIdAsync(connection, ticketId, transaction))!;
            transaction.Commit();
        }
        catch
        {
            transaction.Rollback();
            throw;
        }

        return ticket;
    }

    /// <summary>
    /// Move a ticket to newStatus if the actor owns it (BR-05) and the
    /// transition is legal (BR-02, BR-03), writing exactly one activity row
    /// in the same transaction as the status change (FR-STAT-05).
    /// </summary>
    public async Task TransitionStatusAsync(IDbConnection connection, int ticketId, int actorId, string newStatus)
    {
        var row = await _tickets.GetStatusAndOwnersAsync(connection, ticketId)
            ?? throw new TicketError("Ticket not found.");

        RequireOwner(row.RequesterId, row.AssigneeId, actorId);

        var currentStatus = row.Status;
        if (!TicketConstants.AllowedTransitions.TryGetValue(currentStatus, out var allowed) || !allowed.Contains(newStatus))
        {
            throw new TransitionError($"Cannot transition from {currentStatus} to {newStatus}.");
        }

        using var transaction = connection.BeginTransaction();
        try
        {
            await _tickets.UpdateStatusAsync(connection, ticketId, newStatus, transaction);
            await _tickets.InsertActivityAsync(
                connection, ticketId, actorId, "STATUS_CHANGE", "status", currentStatus, newStatus, transaction);
            transaction.Commit();
        }
        catch
        {
            transaction.Rollback();
            throw;
        }
    }

    /// <summary>
    /// Update a permitted ticket field (priority or category) if the actor
    /// owns the ticket (BR-05), writing exactly one activity row in the same
    /// transaction as the field change (FR-STAT-03/04/05). A no-op update
    /// (new value equal to current) writes nothing, since BR-04 covers actual
    /// changes, not resubmission of the same value.
    /// </summary>
    public async Task UpdateTicketFieldAsync(IDbConnection connection, int ticketId, int actorId, string field, string newValue)
    {
        if (!TicketConstants.FieldValidators.TryGetValue(field, out var allowedValues))
        {
            throw new TicketError($"Field '{field}' cannot be updated.");
        }

        if (!allowedValues.Contains(newValue))
        {
            throw new TicketError(
                $"{char.ToUpperInvariant(field[0])}{field[1..]} must be one of: " + string.Join(", ", allowedValues));
        }

        var row = await _tickets.GetFieldAndOwnersAsync(connection, field, ticketId)
            ?? throw new TicketError("Ticket not found.");

        RequireOwner(row.RequesterId, row.AssigneeId, actorId);

        var oldValue = row.CurrentValue;
        if (oldValue == newValue)
        {
            return;
        }

        using var transaction = connection.BeginTransaction();
        try
        {
            await _tickets.UpdateFieldAsync(connection, field, newValue, ticketId, transaction);
            await _tickets.InsertActivityAsync(
                connection, ticketId, actorId, "FIELD_UPDATE", field, oldValue, newValue, transaction);
            transaction.Commit();
        }
        catch
        {
            transaction.Rollback();
            throw;
        }
    }

    /// <summary>Fetch a ticket scoped to the user as requester or assignee (BR-05).</summary>
    public Task<Ticket?> GetTicketAsync(IDbConnection connection, int ticketId, int userId) =>
        _tickets.GetByIdScopedAsync(connection, ticketId, userId);

    /// <summary>
    /// Fetch a ticket by its human-facing number, scoped to the user as
    /// requester or assignee (BR-05).
    /// </summary>
    public Task<Ticket?> GetTicketByNumberAsync(IDbConnection connection, string ticketNumber, int userId) =>
        _tickets.GetByNumberScopedAsync(connection, ticketNumber, userId);

    /// <summary>
    /// Return the user's tickets (requester or assignee), newest first,
    /// narrowed by any combination of the given filters/search — filters
    /// intersect (AND), and search composes with them rather than replacing
    /// them (FR-LIST-01..05, BR-05).
    /// </summary>
    public Task<IReadOnlyList<Ticket>> ListTicketsAsync(IDbConnection connection, TicketListFilter filter) =>
        _tickets.ListAsync(connection, filter);

    /// <summary>
    /// Return a ticket's activity rows newest-first (FR-STAT-06), scoped to
    /// the user as requester or assignee (BR-05). Empty if the ticket doesn't
    /// exist or isn't the user's.
    /// </summary>
    public async Task<IReadOnlyList<TicketActivity>> GetTicketActivityAsync(IDbConnection connection, int ticketId, int userId)
    {
        if (!await _tickets.ExistsScopedAsync(connection, ticketId, userId))
        {
            return Array.Empty<TicketActivity>();
        }

        return await _tickets.GetActivityAsync(connection, ticketId);
    }
}
