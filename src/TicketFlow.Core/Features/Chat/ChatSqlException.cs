namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Raised when generated SQL fails the read-only/single-statement/
/// subquery-free/table-allowlisted guard. The query is never executed.
/// </summary>
public sealed class ChatSqlException : Exception
{
    public ChatSqlException(string message) : base(message)
    {
    }
}
