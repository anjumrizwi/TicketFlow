using System.Data;
using Dapper;

namespace TicketFlow.Core.Features.Chat;

public sealed class SqlChatErrorLogRepository : IChatErrorLogRepository
{
    public async Task LogAsync(IDbConnection connection, int userId, string errorType, string errorMessage)
    {
        try
        {
            await connection.ExecuteAsync(
                "INSERT INTO chat_error_log (user_id, error_type, error_message) VALUES (@userId, @errorType, @errorMessage)",
                new { userId, errorType, errorMessage });
        }
        catch
        {
            // The connection may already be broken (the likely reason the
            // insert above failed in the first place) - swallow so a
            // logging failure never escapes and breaks the chat turn.
        }
    }
}
