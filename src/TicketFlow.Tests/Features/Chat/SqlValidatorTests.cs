using TicketFlow.Core.Features.Chat;
using Xunit;

namespace TicketFlow.Tests.Features.Chat;

/// <summary>
/// Tests traced to specs/chat-assistant.md's SQL-safety acceptance
/// criteria, plus regression coverage for bypass classes the Python
/// reference app's spec documents as previously found (comma-joins,
/// join-keyword-spelling variants, OR-1=1-style scope bypass attempts).
/// </summary>
public sealed class SqlValidatorTests
{
    [Theory(DisplayName = "a plain single-table SELECT on tickets is accepted")]
    [InlineData("SELECT * FROM tickets")]
    [InlineData("SELECT * FROM tickets WHERE status = 'OPEN'")]
    [InlineData("SELECT status, COUNT(*) AS c FROM tickets GROUP BY status")]
    [InlineData("SELECT * FROM tickets ORDER BY created_at DESC")]
    [InlineData("SELECT TOP 5 * FROM tickets ORDER BY created_at DESC")]
    public void Validate_PlainTicketsSelect_IsAccepted(string sql)
    {
        var result = SqlValidator.Validate(sql);
        Assert.Equal(sql, result);
    }

    [Fact(DisplayName = "empty/whitespace input is rejected")]
    public void Validate_Empty_IsRejected()
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate(""));
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate("   "));
    }

    [Theory(DisplayName = "any non-SELECT statement type is rejected")]
    [InlineData("INSERT INTO tickets (title) VALUES ('x')")]
    [InlineData("UPDATE tickets SET status = 'CLOSED'")]
    [InlineData("DELETE FROM tickets")]
    [InlineData("DROP TABLE tickets")]
    [InlineData("ALTER TABLE tickets ADD COLUMN x INT")]
    [InlineData("TRUNCATE TABLE tickets")]
    [InlineData("EXEC sp_who")]
    [InlineData("EXECUTE ('SELECT 1')")]
    public void Validate_NonSelectStatement_IsRejected(string sql)
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate(sql));
    }

    [Fact(DisplayName = "multiple statements in one batch are rejected, even hidden behind a comment")]
    public void Validate_MultipleStatements_IsRejected()
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate("SELECT * FROM tickets; DROP TABLE tickets;"));
        // A real parser (unlike regex/keyword scanning) sees the statement after
        // the comment as a second, separate statement rather than dead text.
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate("SELECT * FROM tickets -- \nDROP TABLE tickets"));
    }

    [Theory(DisplayName = "any subquery or set operation is rejected")]
    [InlineData("SELECT * FROM tickets WHERE id IN (SELECT id FROM tickets WHERE status = 'OPEN')")]
    [InlineData("SELECT (SELECT COUNT(*) FROM tickets) AS c FROM tickets")]
    [InlineData("SELECT * FROM tickets UNION SELECT * FROM tickets")]
    [InlineData("WITH cte AS (SELECT * FROM tickets) SELECT * FROM cte")]
    public void Validate_SubqueryOrSetOperation_IsRejected(string sql)
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate(sql));
    }

    [Theory(DisplayName = "any JOIN, of any spelling/style, is rejected")]
    [InlineData("SELECT * FROM tickets JOIN users ON users.id = tickets.requester_id")]
    [InlineData("SELECT * FROM tickets LEFT JOIN users ON users.id = tickets.requester_id")]
    [InlineData("SELECT * FROM tickets INNER JOIN users ON users.id = tickets.requester_id")]
    [InlineData("SELECT * FROM tickets, users")] // old-style comma join
    [InlineData("SELECT * FROM tickets, tickets")] // second reference to the same table
    public void Validate_AnyJoinStyle_IsRejected(string sql)
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate(sql));
    }

    [Theory(DisplayName = "a query against any table other than tickets is rejected")]
    [InlineData("SELECT * FROM users")]
    [InlineData("SELECT * FROM ticket_activity")]
    [InlineData("SELECT * FROM chat_error_log")]
    [InlineData("SELECT * FROM dbo.tickets")] // schema-qualified reference still rejected per the AST check
    public void Validate_WrongTable_IsRejected(string sql)
    {
        Assert.Throws<ChatSqlException>(() => SqlValidator.Validate(sql));
    }

    [Fact(DisplayName = "a derived table / table-valued function in FROM is rejected")]
    public void Validate_DerivedTable_IsRejected()
    {
        Assert.Throws<ChatSqlException>(
            () => SqlValidator.Validate("SELECT * FROM (SELECT * FROM tickets) AS derived"));
    }
}
