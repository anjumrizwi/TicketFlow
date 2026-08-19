using TicketFlow.Core.Features.Chat;

namespace TicketFlow.Tests.Fakes;

/// <summary>Scripted IChatCompletionClient — returns queued SQL responses, records every call.</summary>
public sealed class FakeChatCompletionClient : IChatCompletionClient
{
    private readonly Queue<string> _sqlResponses;
    private string _lastResponse;

    public string SummaryResponse { get; set; } = "Here is your answer.";

    public List<(string Question, string? ValidationError)> GenerateSqlCalls { get; } = new();

    public List<IReadOnlyList<IDictionary<string, object?>>> SummarizeCalls { get; } = new();

    public FakeChatCompletionClient(params string[] sqlResponses)
    {
        _sqlResponses = new Queue<string>(sqlResponses);
        _lastResponse = sqlResponses.Length > 0 ? sqlResponses[^1] : "";
    }

    public Task<string> GenerateSqlAsync(
        string question, IReadOnlyList<ChatMessage> history, string? validationError, CancellationToken ct = default)
    {
        GenerateSqlCalls.Add((question, validationError));
        var response = _sqlResponses.Count > 0 ? _sqlResponses.Dequeue() : _lastResponse;
        return Task.FromResult(response);
    }

    public Task<string> SummarizeAsync(
        string question, IReadOnlyList<IDictionary<string, object?>> rows, CancellationToken ct = default)
    {
        SummarizeCalls.Add(rows);
        return Task.FromResult(SummaryResponse);
    }
}
