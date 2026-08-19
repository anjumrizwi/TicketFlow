using System.Data;

namespace TicketFlow.Core.Features.Chat;

public interface IChatErrorLogRepository
{
    /// <summary>
    /// Persist one scrubbed failure record for this chat turn, scoped to
    /// userId (specs/chat-assistant.md AC-7/AC-9). Never throws - a
    /// logging failure degrades to "no row written", never a broken chat
    /// turn.
    /// </summary>
    Task LogAsync(IDbConnection connection, int userId, string errorType, string errorMessage);
}
