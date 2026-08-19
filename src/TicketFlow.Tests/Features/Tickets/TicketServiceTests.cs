using TicketFlow.Core.Features.Tickets;
using TicketFlow.Tests.Fakes;
using Xunit;

namespace TicketFlow.Tests.Features.Tickets;

/// <summary>
/// Tests traced to specs/tickets.md and specs/status-workflow.md's
/// acceptance criteria.
/// </summary>
public sealed class TicketServiceTests
{
    private static (TicketService Service, FakeTicketRepository Tickets, FakeDbConnection Connection) CreateSut()
    {
        var tickets = new FakeTicketRepository();
        var service = new TicketService(tickets);
        var connection = new FakeDbConnection();
        return (service, tickets, connection);
    }

    // --- specs/tickets.md ---

    [Theory(DisplayName = "tickets.md AC-1/AC-2: empty title/description is rejected; no row is written")]
    [InlineData("", "a valid description")]
    [InlineData("A valid title", "")]
    public async Task Create_EmptyRequiredField_IsRejectedWithNoInsert(string title, string description)
    {
        var (service, tickets, connection) = CreateSut();

        await Assert.ThrowsAsync<TicketError>(
            () => service.CreateTicketAsync(connection, 1, title, description, "Bug", "LOW"));

        Assert.Empty(tickets.InsertedTickets);
    }

    [Fact(DisplayName = "tickets.md AC-2: an invalid category is rejected")]
    public async Task Create_InvalidCategory_IsRejected()
    {
        var (service, tickets, connection) = CreateSut();

        await Assert.ThrowsAsync<TicketError>(
            () => service.CreateTicketAsync(connection, 1, "Title", "Description", "NotACategory", "LOW"));

        Assert.Empty(tickets.InsertedTickets);
    }

    [Fact(DisplayName = "tickets.md AC-2: an invalid priority is rejected")]
    public async Task Create_InvalidPriority_IsRejected()
    {
        var (service, tickets, connection) = CreateSut();

        await Assert.ThrowsAsync<TicketError>(
            () => service.CreateTicketAsync(connection, 1, "Title", "Description", "Bug", "NOT_A_PRIORITY"));

        Assert.Empty(tickets.InsertedTickets);
    }

    [Fact(DisplayName = "tickets.md AC-3/AC-4: a valid ticket is created OPEN, gets a ticket number, and writes one CREATED activity row, all committed together")]
    public async Task Create_ValidTicket_CreatesOpenTicketWithOneActivityRowInOneTransaction()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.NextInsertId = 42;
        var expected = new Ticket
        {
            Id = 42,
            TicketNumber = "TCK-000042",
            RequesterId = 1,
            Title = "Title",
            Description = "Description",
            Category = "Bug",
            Priority = "LOW",
            Status = "OPEN",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow,
        };
        tickets.GetByIdResult = expected;

        var ticket = await service.CreateTicketAsync(connection, 1, "Title", "Description", "Bug", "LOW");

        Assert.Same(expected, ticket);
        var inserted = Assert.Single(tickets.InsertedTickets);
        Assert.Equal(1, inserted.RequesterId);
        var numberUpdate = Assert.Single(tickets.UpdatedTicketNumbers);
        Assert.Equal("TCK-000042", numberUpdate.TicketNumber);
        var activity = Assert.Single(tickets.InsertedActivities);
        Assert.Equal("CREATED", activity.Action);
        Assert.Null(activity.FieldChanged);
        Assert.Equal("OPEN", activity.NewValue);
        Assert.Equal(1, connection.CommitCount);
        Assert.Equal(0, connection.RollbackCount);
    }

    // --- specs/status-workflow.md ---

    [Theory(DisplayName = "status-workflow.md AC-1: every legal transition succeeds and writes exactly one activity row")]
    [InlineData("OPEN", "IN_PROGRESS")]
    [InlineData("IN_PROGRESS", "RESOLVED")]
    [InlineData("RESOLVED", "CLOSED")]
    [InlineData("RESOLVED", "IN_PROGRESS")]
    public async Task Transition_LegalTransition_SucceedsWithOneActivityRow(string from, string to)
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetStatusAndOwnersResult = new TicketStatusOwners { Status = from, RequesterId = 1, AssigneeId = null };

        await service.TransitionStatusAsync(connection, 5, 1, to);

        var statusUpdate = Assert.Single(tickets.UpdatedStatuses);
        Assert.Equal(to, statusUpdate.NewStatus);
        var activity = Assert.Single(tickets.InsertedActivities);
        Assert.Equal("STATUS_CHANGE", activity.Action);
        Assert.Equal("status", activity.FieldChanged);
        Assert.Equal(from, activity.OldValue);
        Assert.Equal(to, activity.NewValue);
        Assert.Equal(1, connection.CommitCount);
    }

    [Fact(DisplayName = "status-workflow.md AC-2: CLOSED is terminal — no transition out of it is legal")]
    public async Task Transition_FromClosed_IsAlwaysRejected()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetStatusAndOwnersResult = new TicketStatusOwners { Status = "CLOSED", RequesterId = 1, AssigneeId = null };

        await Assert.ThrowsAsync<TransitionError>(() => service.TransitionStatusAsync(connection, 5, 1, "OPEN"));

        Assert.Empty(tickets.UpdatedStatuses);
        Assert.Empty(tickets.InsertedActivities);
    }

    [Fact(DisplayName = "status-workflow.md AC-2: an illegal transition is rejected with no state change")]
    public async Task Transition_IllegalTransition_IsRejectedWithNoStateChange()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetStatusAndOwnersResult = new TicketStatusOwners { Status = "OPEN", RequesterId = 1, AssigneeId = null };

        // OPEN can only go to IN_PROGRESS, not straight to RESOLVED.
        await Assert.ThrowsAsync<TransitionError>(() => service.TransitionStatusAsync(connection, 5, 1, "RESOLVED"));

        Assert.Empty(tickets.UpdatedStatuses);
        Assert.Empty(tickets.InsertedActivities);
    }

    [Fact(DisplayName = "status-workflow.md AC-6: a non-requester/non-assignee cannot transition the ticket")]
    public async Task Transition_ByNonOwner_IsRejected()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetStatusAndOwnersResult = new TicketStatusOwners { Status = "OPEN", RequesterId = 1, AssigneeId = 2 };

        await Assert.ThrowsAsync<TicketPermissionError>(() => service.TransitionStatusAsync(connection, 5, 999, "IN_PROGRESS"));

        Assert.Empty(tickets.UpdatedStatuses);
    }

    [Fact(DisplayName = "status-workflow.md: the assignee (not just the requester) may transition the ticket")]
    public async Task Transition_ByAssignee_Succeeds()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetStatusAndOwnersResult = new TicketStatusOwners { Status = "OPEN", RequesterId = 1, AssigneeId = 2 };

        await service.TransitionStatusAsync(connection, 5, 2, "IN_PROGRESS");

        Assert.Single(tickets.UpdatedStatuses);
    }

    [Fact(DisplayName = "status-workflow.md AC-4: if writing the activity row fails, the field change is rolled back")]
    public async Task UpdateField_ActivityWriteFails_RollsBackFieldChange()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetFieldAndOwnersResult = new TicketFieldOwners { CurrentValue = "LOW", RequesterId = 1, AssigneeId = null };
        tickets.ThrowOnInsertActivity = new InvalidOperationException("db exploded");

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => service.UpdateTicketFieldAsync(connection, 5, 1, "priority", "HIGH"));

        Assert.Equal(1, connection.RollbackCount);
        Assert.Equal(0, connection.CommitCount);
    }

    [Fact(DisplayName = "status-workflow.md AC-3: a priority update writes exactly one FIELD_UPDATE activity row")]
    public async Task UpdateField_ValidChange_WritesOneActivityRow()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetFieldAndOwnersResult = new TicketFieldOwners { CurrentValue = "LOW", RequesterId = 1, AssigneeId = null };

        await service.UpdateTicketFieldAsync(connection, 5, 1, "priority", "HIGH");

        var fieldUpdate = Assert.Single(tickets.UpdatedFields);
        Assert.Equal(("priority", "HIGH", 5), fieldUpdate);
        var activity = Assert.Single(tickets.InsertedActivities);
        Assert.Equal("FIELD_UPDATE", activity.Action);
        Assert.Equal("priority", activity.FieldChanged);
        Assert.Equal("LOW", activity.OldValue);
        Assert.Equal("HIGH", activity.NewValue);
        Assert.Equal(1, connection.CommitCount);
    }

    [Fact(DisplayName = "a no-op field update (same value) writes nothing")]
    public async Task UpdateField_SameValue_IsNoOp()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetFieldAndOwnersResult = new TicketFieldOwners { CurrentValue = "LOW", RequesterId = 1, AssigneeId = null };

        await service.UpdateTicketFieldAsync(connection, 5, 1, "priority", "LOW");

        Assert.Empty(tickets.UpdatedFields);
        Assert.Empty(tickets.InsertedActivities);
        Assert.Equal(0, connection.CommitCount);
    }

    [Fact(DisplayName = "status-workflow.md AC-6: a non-owner cannot update a ticket field")]
    public async Task UpdateField_ByNonOwner_IsRejected()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.GetFieldAndOwnersResult = new TicketFieldOwners { CurrentValue = "LOW", RequesterId = 1, AssigneeId = 2 };

        await Assert.ThrowsAsync<TicketPermissionError>(
            () => service.UpdateTicketFieldAsync(connection, 5, 999, "priority", "HIGH"));

        Assert.Empty(tickets.UpdatedFields);
    }

    [Fact(DisplayName = "GetTicketActivity returns empty (not an error) for a ticket the user doesn't own")]
    public async Task GetTicketActivity_ForUnownedTicket_ReturnsEmpty()
    {
        var (service, tickets, connection) = CreateSut();
        tickets.ExistsScopedResult = false;

        var activity = await service.GetTicketActivityAsync(connection, 5, 999);

        Assert.Empty(activity);
    }
}
