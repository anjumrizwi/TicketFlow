namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Registered when OPENAI_API_KEY isn't set, so ChatOrchestrator can
/// still be constructed and the Chat Assistant page can still render —
/// the failure only surfaces when a question is actually submitted, at
/// which point it flows through the same classify-and-log path as any
/// other external-service failure (ChatExceptionClassifier), rather than
/// crashing the whole page on load.
/// </summary>
public sealed class UnconfiguredChatCompletionClient : IChatCompletionClient
{
    public Task<string> GenerateSqlAsync(
        string question, IReadOnlyList<ChatMessage> history, string? validationError, CancellationToken ct = default) =>
        throw new InvalidOperationException("OPENAI_API_KEY is not configured.");

    public Task<string> SummarizeAsync(
        string question, IReadOnlyList<IDictionary<string, object?>> rows, CancellationToken ct = default) =>
        throw new InvalidOperationException("OPENAI_API_KEY is not configured.");
}
