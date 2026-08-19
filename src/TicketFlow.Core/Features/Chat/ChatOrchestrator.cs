using System.Data;
using System.Text.RegularExpressions;
using Dapper;

namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Guarded text-to-SQL chat assistant (specs/chat-assistant.md).
/// FR-AI-01..08, BR-06 (read-only, always user-scoped), NFR-01, NFR-03.
/// This is the highest-risk feature in the app: every LLM-generated query
/// passes through <see cref="SqlValidator"/> and <see cref="ScopeInjector"/>
/// before it can ever reach the database.
///
/// The security property this class is built around — same as the Python
/// reference app's LangGraph-based implementation, just as a plain
/// bounded loop instead of a graph library (see BRD §11a: the mechanism
/// name differs, the behavior doesn't): the LLM never writes the
/// user-scoping condition itself, and never controls the actual numeric
/// user id. The LLM writes its own business-logic filters (status,
/// priority, date ranges) with no scoping clause of its own;
/// <see cref="ScopeInjector"/> — plain code, not an LLM — structurally
/// ANDs `(requester_id = @userId OR assignee_id = @userId)` onto
/// whatever WHERE clause the LLM wrote (wrapped in parentheses first),
/// so it can only ever narrow the LLM's own WHERE clause further, never
/// widen it. The real, session-authenticated user id is bound as a
/// genuine Dapper parameter at execution time, never string-substituted.
/// </summary>
public sealed class ChatOrchestrator
{
    public const int MaxAttempts = 2;

    public const string SystemPrompt = """
        You are a text-to-SQL assistant for TicketFlow, a ticket management system. You answer questions about the current user's own tickets by generating exactly one read-only SQL SELECT query.

        Schema (SQL Server / T-SQL):
          tickets(id, ticket_number, requester_id, assignee_id, title, description,
                  category, priority, status, created_at, updated_at)

        Rules, all mandatory:
        - Output ONLY the SQL query. No explanation, no markdown code fences.
        - Exactly one SELECT statement, with no subqueries and no CTEs (no WITH).
          Never write; never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
          TRUNCATE, GRANT, REVOKE, UNION, or any statement type other than one
          plain SELECT.
        - The query's only table is `tickets` - no other table, no JOIN of any
          kind, no second reference to `tickets`. Activity-history questions
          can't be answered by this assistant; say so rather than guessing.
        - Do NOT add any condition on `requester_id` or `assignee_id` yourself -
          the system adds the user-scoping filter automatically after you
          respond. Just write whatever business-logic filters the question needs
          (status, priority, category, dates) and nothing about the user.
        """;

    private readonly IChatCompletionClient _llm;

    public ChatOrchestrator(IChatCompletionClient llm)
    {
        _llm = llm;
    }

    /// <summary>
    /// Run one turn of the guarded text-to-SQL loop (FR-AI-01..08).
    /// `history` is the prior conversation; the caller owns trimming and
    /// persistence — this method reads it but doesn't store anything.
    /// </summary>
    public async Task<ChatTurnResult> AskAsync(
        string question, int userId, IReadOnlyList<ChatMessage> history, IDbConnection connection,
        CancellationToken ct = default)
    {
        string? validationError = null;

        for (var attempt = 1; attempt <= MaxAttempts; attempt++)
        {
            var generated = await _llm.GenerateSqlAsync(question, history, validationError, ct);
            var candidate = ExtractSql(generated);

            string scopedSql;
            try
            {
                SqlValidator.Validate(candidate);
                scopedSql = ScopeInjector.InjectScope(candidate);
            }
            catch (ChatSqlException ex)
            {
                validationError = ex.Message;
                continue;
            }

            var rows = (await connection.QueryAsync(scopedSql, new { userId }))
                .Cast<IDictionary<string, object?>>()
                .ToList();
            var answer = await _llm.SummarizeAsync(question, rows, ct);

            return new ChatTurnResult { Answer = answer, Sql = scopedSql, Failed = false, ValidationError = null };
        }

        return new ChatTurnResult
        {
            Answer = "I couldn't safely answer that question.",
            Sql = null,
            Failed = true,
            ValidationError = validationError,
        };
    }

    private static string ExtractSql(string content)
    {
        var text = content.Trim();
        if (text.StartsWith("```", StringComparison.Ordinal))
        {
            text = text.Trim('`');
            text = Regex.Replace(text, "^sql\\s*", "", RegexOptions.IgnoreCase);
        }

        return text.Trim();
    }
}
