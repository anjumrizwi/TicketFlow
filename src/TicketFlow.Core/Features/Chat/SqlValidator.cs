using Microsoft.SqlServer.TransactSql.ScriptDom;

namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Validates that generated SQL is a single, read-only, subquery-free,
/// JOIN-free SELECT that references exactly the `tickets` table — see
/// the chat feature's module-level design note (specs/chat-assistant.md)
/// for why joins/`ticket_activity` are banned outright rather than
/// validated. This checks structure only; user-scoping itself is applied
/// afterwards by <see cref="ScopeInjector"/>, not requested of the LLM.
///
/// Uses the real T-SQL parser (Microsoft.SqlServer.TransactSql.ScriptDom,
/// the same parser SSDT/DacFx use) instead of token/keyword scanning —
/// a strictly stronger guarantee than the Python reference app's
/// sqlparse-based approach: a comment can't hide a second statement from
/// a real parser the way it can from regex/keyword-banning, and
/// INSERT/UPDATE/DELETE/EXEC/etc. simply fail to parse as a
/// <see cref="SelectStatement"/> in the first place rather than needing
/// an enumerated blocklist.
/// </summary>
public static class SqlValidator
{
    private const string RequiredTable = "tickets";

    public static string Validate(string sql)
    {
        if (string.IsNullOrWhiteSpace(sql))
        {
            throw new ChatSqlException("Empty query.");
        }

        var fragment = Parse(sql, out var errors);
        if (errors.Count > 0)
        {
            throw new ChatSqlException($"Query failed to parse: {errors[0].Message}");
        }

        var statements = fragment.Batches.SelectMany(b => b.Statements).ToList();
        if (statements.Count != 1)
        {
            throw new ChatSqlException("Only a single SQL statement is allowed.");
        }

        if (statements[0] is not SelectStatement selectStatement)
        {
            throw new ChatSqlException("Only read-only SELECT queries are allowed.");
        }

        if (selectStatement.QueryExpression is not QuerySpecification querySpec)
        {
            // A BinaryQueryExpression here means UNION/EXCEPT/INTERSECT at the top level.
            throw new ChatSqlException("Subqueries and set operations (e.g. UNION) are not allowed.");
        }

        var querySpecCount = new QuerySpecificationCounter();
        selectStatement.Accept(querySpecCount);
        if (querySpecCount.Count > 1)
        {
            throw new ChatSqlException("Subqueries and nested SELECTs are not allowed.");
        }

        if (querySpec.FromClause is null || querySpec.FromClause.TableReferences.Count != 1)
        {
            throw new ChatSqlException(
                "Query must reference exactly one table (tickets), referenced exactly once.");
        }

        // A JOIN (of any kind, including old-style comma joins, which
        // produce a second TableReferences entry rather than a
        // QualifiedJoin node) is already excluded by the count check
        // above; this additionally excludes derived tables, table-valued
        // functions, and any other non-plain-table FROM target.
        if (querySpec.FromClause.TableReferences[0] is not NamedTableReference namedTable)
        {
            throw new ChatSqlException("Query must reference exactly the tickets table, nothing else.");
        }

        if (namedTable.SchemaObject.SchemaIdentifier is not null ||
            namedTable.SchemaObject.DatabaseIdentifier is not null ||
            !string.Equals(namedTable.SchemaObject.BaseIdentifier.Value, RequiredTable, StringComparison.OrdinalIgnoreCase))
        {
            throw new ChatSqlException("Query must reference exactly the tickets table, nothing else.");
        }

        return sql;
    }

    internal static TSqlScript Parse(string sql, out IList<ParseError> errors)
    {
        var parser = new TSql160Parser(initialQuotedIdentifiers: true);
        using var reader = new StringReader(sql);
        var fragment = parser.Parse(reader, out errors);
        return fragment as TSqlScript ?? throw new ChatSqlException("Query could not be parsed.");
    }

    private sealed class QuerySpecificationCounter : TSqlFragmentVisitor
    {
        public int Count { get; private set; }

        public override void Visit(QuerySpecification node)
        {
            Count++;
            base.Visit(node);
        }
    }
}
