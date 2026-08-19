namespace TicketFlow.Core.Features.Chat;

/// <summary>One turn of chat history. Role is "user" or "assistant".</summary>
public sealed record ChatMessage(string Role, string Content);
