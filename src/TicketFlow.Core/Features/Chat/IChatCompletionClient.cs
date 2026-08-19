namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// LLM calls the chat orchestrator needs. Injectable, mirroring the
/// Python reference app's `llm=None` testability parameter — tests
/// supply a fake that returns scripted SQL/summary text with no network
/// call.
/// </summary>
public interface IChatCompletionClient
{
    Task<string> GenerateSqlAsync(
        string question, IReadOnlyList<ChatMessage> history, string? validationError, CancellationToken ct = default);

    Task<string> SummarizeAsync(
        string question, IReadOnlyList<IDictionary<string, object?>> rows, CancellationToken ct = default);
}
