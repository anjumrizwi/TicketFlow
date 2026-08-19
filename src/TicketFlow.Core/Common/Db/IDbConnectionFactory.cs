using System.Data;

namespace TicketFlow.Core.Common.Db;

/// <summary>
/// Opens a new connection scoped to one request/unit of work. Callers own
/// the connection's lifecycle (dispose it themselves), mirroring
/// common/db.py's get_connection() contract in the Python reference app.
/// </summary>
public interface IDbConnectionFactory
{
    IDbConnection CreateConnection();
}
