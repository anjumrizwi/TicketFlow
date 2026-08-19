using Microsoft.SqlServer.TransactSql.ScriptDom;

namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Structurally ANDs the user-scoping condition into a validated query's
/// WHERE clause (code-controlled, never LLM text) — the sole enforcement
/// of BR-05/BR-06 for this feature. If a WHERE clause already exists,
/// whatever the LLM wrote is wrapped in parentheses first, so it can only
/// ever narrow the scoping condition, never widen or bypass it. Because
/// this operates on the parsed AST (via <see cref="SqlValidator.Parse"/>)
/// rather than splicing raw text at a "clause boundary" the way the
/// Python reference app's `_inject_scope` does, there's no risk of the
/// injected clause landing in the wrong position relative to
/// GROUP BY/ORDER BY/HAVING — `QuerySpecification.WhereClause` is a
/// well-defined property, not a text offset.
/// </summary>
public static class ScopeInjector
{
    public const string ScopeConditionSql = "requester_id = @userId OR assignee_id = @userId";

    public static string InjectScope(string sql)
    {
        var fragment = SqlValidator.Parse(sql, out _);
        var selectStatement = (SelectStatement)fragment.Batches[0].Statements[0];
        var querySpec = (QuerySpecification)selectStatement.QueryExpression;

        var scopeCondition = ParseScopeCondition();

        if (querySpec.WhereClause is not null)
        {
            var existing = querySpec.WhereClause.SearchCondition;
            querySpec.WhereClause.SearchCondition = new BooleanBinaryExpression
            {
                BinaryExpressionType = BooleanBinaryExpressionType.And,
                FirstExpression = new BooleanParenthesisExpression { Expression = existing },
                SecondExpression = new BooleanParenthesisExpression { Expression = scopeCondition },
            };
        }
        else
        {
            querySpec.WhereClause = new WhereClause
            {
                SearchCondition = new BooleanParenthesisExpression { Expression = scopeCondition },
            };
        }

        var generator = new Sql160ScriptGenerator();
        generator.GenerateScript(fragment, out var scopedSql);
        return scopedSql;
    }

    private static BooleanExpression ParseScopeCondition()
    {
        // ScriptDom parses full statements/scripts, not bare expression
        // fragments, so a throwaway "SELECT 1 WHERE ..." is parsed purely
        // to extract its WHERE clause as a reusable AST fragment.
        var fragment = SqlValidator.Parse($"SELECT 1 WHERE {ScopeConditionSql}", out _);
        var selectStatement = (SelectStatement)fragment.Batches[0].Statements[0];
        var querySpec = (QuerySpecification)selectStatement.QueryExpression;
        return querySpec.WhereClause.SearchCondition;
    }
}
