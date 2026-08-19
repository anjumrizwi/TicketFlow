using System.Data;
using Dapper;

namespace TicketFlow.Core.Features.Tickets;

public sealed class SqlTicketRepository : ITicketRepository
{
    private const string TicketColumns =
        "id AS Id, ticket_number AS TicketNumber, requester_id AS RequesterId, assignee_id AS AssigneeId, " +
        "title AS Title, description AS Description, category AS Category, priority AS Priority, " +
        "status AS Status, created_at AS CreatedAt, updated_at AS UpdatedAt";

    public Task<int> InsertTicketAsync(
        IDbConnection connection, int requesterId, string title, string description, string category, string priority,
        IDbTransaction? transaction = null)
    {
        return connection.ExecuteScalarAsync<int>(
            """
            INSERT INTO tickets (requester_id, title, description, category, priority, status)
            OUTPUT INSERTED.id
            VALUES (@requesterId, @title, @description, @category, @priority, 'OPEN')
            """,
            new { requesterId, title, description, category, priority },
            transaction);
    }

    public Task UpdateTicketNumberAsync(
        IDbConnection connection, int ticketId, string ticketNumber, IDbTransaction? transaction = null)
    {
        return connection.ExecuteAsync(
            "UPDATE tickets SET ticket_number = @ticketNumber WHERE id = @ticketId",
            new { ticketNumber, ticketId },
            transaction);
    }

    public Task InsertActivityAsync(
        IDbConnection connection, int ticketId, int actorId, string action, string? fieldChanged,
        string? oldValue, string? newValue, IDbTransaction? transaction = null)
    {
        return connection.ExecuteAsync(
            """
            INSERT INTO ticket_activity (ticket_id, actor_id, action, field_changed, old_value, new_value)
            VALUES (@ticketId, @actorId, @action, @fieldChanged, @oldValue, @newValue)
            """,
            new { ticketId, actorId, action, fieldChanged, oldValue, newValue },
            transaction);
    }

    public Task<Ticket?> GetByIdAsync(IDbConnection connection, int ticketId, IDbTransaction? transaction = null)
    {
        return connection.QuerySingleOrDefaultAsync<Ticket?>(
            $"SELECT {TicketColumns} FROM tickets WHERE id = @ticketId",
            new { ticketId },
            transaction);
    }

    public Task<TicketStatusOwners?> GetStatusAndOwnersAsync(
        IDbConnection connection, int ticketId, IDbTransaction? transaction = null)
    {
        return connection.QuerySingleOrDefaultAsync<TicketStatusOwners?>(
            "SELECT status AS Status, requester_id AS RequesterId, assignee_id AS AssigneeId " +
            "FROM tickets WHERE id = @ticketId",
            new { ticketId },
            transaction);
    }

    public Task UpdateStatusAsync(
        IDbConnection connection, int ticketId, string newStatus, IDbTransaction? transaction = null)
    {
        return connection.ExecuteAsync(
            "UPDATE tickets SET status = @newStatus WHERE id = @ticketId",
            new { newStatus, ticketId },
            transaction);
    }

    public Task<TicketFieldOwners?> GetFieldAndOwnersAsync(
        IDbConnection connection, string field, int ticketId, IDbTransaction? transaction = null)
    {
        // `field` is validated against TicketConstants.FieldValidators by the
        // caller (TicketService) before ever reaching here — never built from
        // raw user input, so interpolating it into the column list is safe
        // (a column name can't be a bind parameter).
        return connection.QuerySingleOrDefaultAsync<TicketFieldOwners?>(
            $"SELECT {field} AS CurrentValue, requester_id AS RequesterId, assignee_id AS AssigneeId " +
            "FROM tickets WHERE id = @ticketId",
            new { ticketId },
            transaction);
    }

    public Task UpdateFieldAsync(
        IDbConnection connection, string field, string newValue, int ticketId, IDbTransaction? transaction = null)
    {
        return connection.ExecuteAsync(
            $"UPDATE tickets SET {field} = @newValue WHERE id = @ticketId",
            new { newValue, ticketId },
            transaction);
    }

    public Task<Ticket?> GetByIdScopedAsync(IDbConnection connection, int ticketId, int userId)
    {
        return connection.QuerySingleOrDefaultAsync<Ticket?>(
            $"SELECT {TicketColumns} FROM tickets " +
            "WHERE id = @ticketId AND (requester_id = @userId OR assignee_id = @userId)",
            new { ticketId, userId });
    }

    public Task<Ticket?> GetByNumberScopedAsync(IDbConnection connection, string ticketNumber, int userId)
    {
        return connection.QuerySingleOrDefaultAsync<Ticket?>(
            $"SELECT {TicketColumns} FROM tickets " +
            "WHERE ticket_number = @ticketNumber AND (requester_id = @userId OR assignee_id = @userId)",
            new { ticketNumber, userId });
    }

    public async Task<IReadOnlyList<Ticket>> ListAsync(IDbConnection connection, TicketListFilter filter)
    {
        var clauses = new List<string> { "(requester_id = @userId OR assignee_id = @userId)" };
        var parameters = new DynamicParameters();
        parameters.Add("userId", filter.UserId);

        if (filter.Status is not null)
        {
            clauses.Add("status = @status");
            parameters.Add("status", filter.Status);
        }

        if (filter.Priority is not null)
        {
            clauses.Add("priority = @priority");
            parameters.Add("priority", filter.Priority);
        }

        if (filter.Category is not null)
        {
            clauses.Add("category = @category");
            parameters.Add("category", filter.Category);
        }

        if (filter.DateFrom is not null)
        {
            clauses.Add("CAST(created_at AS DATE) >= @dateFrom");
            parameters.Add("dateFrom", filter.DateFrom.Value.ToDateTime(TimeOnly.MinValue));
        }

        if (filter.DateTo is not null)
        {
            clauses.Add("CAST(created_at AS DATE) <= @dateTo");
            parameters.Add("dateTo", filter.DateTo.Value.ToDateTime(TimeOnly.MinValue));
        }

        if (!string.IsNullOrWhiteSpace(filter.Search))
        {
            clauses.Add("(title LIKE @search OR description LIKE @search)");
            parameters.Add("search", $"%{filter.Search}%");
        }

        var where = string.Join(" AND ", clauses);
        var rows = await connection.QueryAsync<Ticket>(
            $"SELECT {TicketColumns} FROM tickets WHERE {where} ORDER BY created_at DESC, id DESC",
            parameters);
        return rows.AsList();
    }

    public async Task<bool> ExistsScopedAsync(IDbConnection connection, int ticketId, int userId)
    {
        var id = await connection.ExecuteScalarAsync<int?>(
            "SELECT id FROM tickets WHERE id = @ticketId AND (requester_id = @userId OR assignee_id = @userId)",
            new { ticketId, userId });
        return id is not null;
    }

    public async Task<IReadOnlyList<TicketActivity>> GetActivityAsync(IDbConnection connection, int ticketId)
    {
        var rows = await connection.QueryAsync<TicketActivity>(
            """
            SELECT ta.id AS Id, ta.actor_id AS ActorId, u.username AS ActorUsername, ta.action AS Action,
                   ta.field_changed AS FieldChanged, ta.old_value AS OldValue, ta.new_value AS NewValue,
                   ta.created_at AS CreatedAt
            FROM ticket_activity ta JOIN users u ON u.id = ta.actor_id
            WHERE ta.ticket_id = @ticketId ORDER BY ta.created_at DESC, ta.id DESC
            """,
            new { ticketId });
        return rows.AsList();
    }
}
