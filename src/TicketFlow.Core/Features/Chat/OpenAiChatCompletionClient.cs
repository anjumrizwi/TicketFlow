using System.Text.Json;
using OpenAI.Chat;

namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Direct OpenAI SDK implementation of <see cref="IChatCompletionClient"/>.
/// A direct SDK call (rather than an agent/orchestration framework like
/// Semantic Kernel) keeps the same deterministic, fully-auditable control
/// flow as the Python reference app's hand-rolled LangGraph graph — the
/// whole point of this feature's design is a small, code-controlled loop
/// that <c>security-auditor</c> can point at one exact call site, not an
/// autonomous agent (see BRD §11a).
/// </summary>
public sealed class OpenAiChatCompletionClient : IChatCompletionClient
{
    private const string SummarizePrompt =
        "You answer the user's question conversationally using ONLY the query result rows given below. " +
        "Never invent a number or fact that isn't in the rows. If the rows are empty, say so plainly.";

    private readonly ChatClient _client;

    public OpenAiChatCompletionClient(string apiKey, string model = "gpt-4o-mini")
    {
        _client = new ChatClient(model, apiKey);
    }

    public async Task<string> GenerateSqlAsync(
        string question, IReadOnlyList<ChatMessage> history, string? validationError, CancellationToken ct = default)
    {
        var messages = new List<OpenAI.Chat.ChatMessage> { new SystemChatMessage(ChatOrchestrator.SystemPrompt) };
        foreach (var turn in history)
        {
            messages.Add(turn.Role == "user"
                ? new UserChatMessage(turn.Content)
                : new AssistantChatMessage(turn.Content));
        }

        messages.Add(new UserChatMessage(question));
        if (validationError is not null)
        {
            messages.Add(new UserChatMessage(
                $"Your previous query was rejected: {validationError} Generate a corrected query following all the rules above."));
        }

        var response = await _client.CompleteChatAsync(messages, cancellationToken: ct);
        return response.Value.Content[0].Text;
    }

    public async Task<string> SummarizeAsync(
        string question, IReadOnlyList<IDictionary<string, object?>> rows, CancellationToken ct = default)
    {
        var rowsJson = JsonSerializer.Serialize(rows);
        var messages = new List<OpenAI.Chat.ChatMessage>
        {
            new SystemChatMessage(SummarizePrompt),
            new UserChatMessage($"Question: {question}\nQuery result rows: {rowsJson}"),
        };

        var response = await _client.CompleteChatAsync(messages, cancellationToken: ct);
        return response.Value.Content[0].Text;
    }
}
