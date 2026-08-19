namespace TicketFlow.Core.Features.Chat;

public sealed record ChatTurnResult
{
    public required string? Answer { get; init; }
    public string? Sql { get; init; }
    public required bool Failed { get; init; }
    public string? ValidationError { get; init; }
}
