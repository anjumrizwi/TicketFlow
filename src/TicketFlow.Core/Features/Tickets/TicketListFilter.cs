namespace TicketFlow.Core.Features.Tickets;

/// <summary>
/// Composable filters for ListTicketsAsync (FR-LIST-01..05). Every filter
/// left null is simply not applied; search composes with filters rather
/// than replacing them, matching list_tickets() in the Python reference
/// app's features/tickets/service.py.
/// </summary>
public sealed class TicketListFilter
{
    public required int UserId { get; init; }

    public string? Status { get; init; }

    public string? Priority { get; init; }

    public string? Category { get; init; }

    public DateOnly? DateFrom { get; init; }

    public DateOnly? DateTo { get; init; }

    public string? Search { get; init; }
}
