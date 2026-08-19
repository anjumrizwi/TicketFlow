using System.Data;

namespace TicketFlow.Tests.Fakes;

/// <summary>
/// Minimal IDbConnection/IDbTransaction stand-ins so AuthService's direct
/// BeginTransaction()/Commit()/Rollback() calls can be exercised and
/// asserted on without a real SQL Server connection — the C# equivalent
/// of tests/conftest.py's FakeConnection commit_calls/rollback_calls
/// counters in the Python reference app. Unused IDbConnection members
/// throw, matching that file's "minimal stand-in" philosophy.
/// </summary>
public sealed class FakeDbConnection : IDbConnection
{
    public int CommitCount { get; private set; }
    public int RollbackCount { get; private set; }

    [System.Diagnostics.CodeAnalysis.AllowNull]
    public string ConnectionString { get; set; } = string.Empty;
    public int ConnectionTimeout => 0;
    public string Database => string.Empty;
    public ConnectionState State => ConnectionState.Open;

    public IDbTransaction BeginTransaction() => new FakeDbTransaction(this);

    public IDbTransaction BeginTransaction(IsolationLevel il) => new FakeDbTransaction(this);

    public void ChangeDatabase(string databaseName) => throw new NotSupportedException();

    public void Close()
    {
    }

    public IDbCommand CreateCommand() => throw new NotSupportedException();

    public void Open()
    {
    }

    public void Dispose()
    {
    }

    internal sealed class FakeDbTransaction : IDbTransaction
    {
        private readonly FakeDbConnection _connection;

        public FakeDbTransaction(FakeDbConnection connection)
        {
            _connection = connection;
        }

        public IDbConnection? Connection => _connection;

        public IsolationLevel IsolationLevel => IsolationLevel.Unspecified;

        public void Commit() => _connection.CommitCount++;

        public void Rollback() => _connection.RollbackCount++;

        public void Dispose()
        {
        }
    }
}
