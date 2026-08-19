namespace TicketFlow.Core.Features.Tickets;

public sealed record TicketActivity
{
    public required int Id { get; init; }
    public required int ActorId { get; init; }
    public required string ActorUsername { get; init; }
    public required string Action { get; init; }
    public string? FieldChanged { get; init; }
    public string? OldValue { get; init; }
    public string? NewValue { get; init; }
    public required DateTime CreatedAt { get; init; }
}
