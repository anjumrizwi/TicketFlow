using TicketFlow.Core.Features.Chat;
using Xunit;

namespace TicketFlow.Tests.Features.Chat;

/// <summary>
/// Tests traced to specs/chat-assistant.md's scoping guarantee: the
/// user-scoping condition is always the outermost AND-ed conjunct, so no
/// LLM-authored `OR 1=1` (or similar) can widen access — it can only ever
/// narrow the LLM's own WHERE clause further.
/// </summary>
public sealed class ScopeInjectorTests
{
    [Fact(DisplayName = "a query with no WHERE clause gets one containing only the scope condition")]
    public void InjectScope_NoExistingWhere_AddsScopeOnly()
    {
        var scoped = ScopeInjector.InjectScope("SELECT * FROM tickets");

        Assert.Contains("WHERE", scoped, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("requester_id", scoped);
        Assert.Contains("assignee_id", scoped);
        Assert.Contains("@userId", scoped);
    }

    [Fact(DisplayName = "a query with an existing WHERE clause gets it wrapped and AND-ed with the scope condition")]
    public void InjectScope_ExistingWhere_WrapsAndAndsScope()
    {
        var scoped = ScopeInjector.InjectScope("SELECT * FROM tickets WHERE status = 'OPEN'");

        Assert.Contains("status", scoped);
        Assert.Contains("OPEN", scoped);
        Assert.Contains("requester_id", scoped);
        Assert.Contains("AND", scoped, StringComparison.OrdinalIgnoreCase);
        // Exactly one WHERE keyword - the LLM's condition and the scope
        // condition are combined into a single WHERE clause, not two.
        Assert.Single(System.Text.RegularExpressions.Regex.Matches(scoped, @"\bWHERE\b", System.Text.RegularExpressions.RegexOptions.IgnoreCase));
    }

    [Fact(DisplayName = "an attempted OR-1=1 scope bypass only ever narrows, never widens: the scope condition remains an outer AND-ed conjunct")]
    public void InjectScope_Or1Equals1BypassAttempt_ScopeStaysOuterConjunct()
    {
        var scoped = ScopeInjector.InjectScope("SELECT * FROM tickets WHERE 1 = 1 OR 1 = 1");

        // The validated fragment ends up wrapped: "(1 = 1 OR 1 = 1) AND (requester_id = @userId OR assignee_id = @userId)".
        // Executing this can never return rows outside the scope condition,
        // because SQL AND binds the whole parenthesized LLM clause to the
        // whole parenthesized scope clause - the LLM's OR is trapped inside
        // its own parentheses and cannot escape to combine with the scope
        // clause at the top level.
        var scopeIndex = scoped.IndexOf("requester_id", StringComparison.Ordinal);
        var andIndex = scoped.LastIndexOf("AND", scopeIndex, StringComparison.OrdinalIgnoreCase);
        Assert.True(andIndex >= 0, "Expected an AND between the LLM's clause and the scope clause.");
        Assert.Contains(")", scoped[..scopeIndex]); // the LLM's clause is closed before the scope clause begins
    }

    [Fact(DisplayName = "GROUP BY/ORDER BY after the injected WHERE clause remain syntactically valid")]
    public void InjectScope_WithGroupByOrderBy_RemainsValidAfterInjection()
    {
        var scoped = ScopeInjector.InjectScope("SELECT status, COUNT(*) AS c FROM tickets GROUP BY status ORDER BY c DESC");

        // Re-validating the scoped SQL confirms the injected WHERE landed
        // in the structurally correct position (SqlValidator would throw
        // ChatSqlException on anything that fails to parse as a single
        // valid SELECT).
        var revalidated = SqlValidator.Validate(scoped);
        Assert.Equal(scoped, revalidated);
        Assert.Contains("GROUP BY", scoped, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("ORDER BY", scoped, StringComparison.OrdinalIgnoreCase);
    }
}
