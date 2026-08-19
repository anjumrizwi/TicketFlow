namespace TicketFlow.Core.Features.Tickets;

public sealed record Ticket
{
    public required int Id { get; init; }
    public string? TicketNumber { get; init; }
    public required int RequesterId { get; init; }
    public int? AssigneeId { get; init; }
    public required string Title { get; init; }
    public required string Description { get; init; }
    public required string Category { get; init; }
    public required string Priority { get; init; }
    public required string Status { get; init; }
    public required DateTime CreatedAt { get; init; }
    public required DateTime UpdatedAt { get; init; }
}
