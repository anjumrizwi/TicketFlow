using System.Data;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;

namespace TicketFlow.Core.Common.Db;

/// <summary>
/// Opens SQL Server connections using Windows/AD integrated auth
/// (Trusted_Connection) against a local/demo instance, matching
/// common/db.py's connection string in the Python reference app.
/// TrustServerCertificate is on because a local/demo instance won't have
/// a CA-signed TLS cert.
/// </summary>
public sealed class SqlConnectionFactory : IDbConnectionFactory
{
    private readonly string _connectionString;

    public SqlConnectionFactory(IConfiguration configuration)
    {
        var server = configuration["DB_HOST"] ?? @"localhost\SQLEXPRESS";
        var port = configuration["DB_PORT"];
        if (!string.IsNullOrEmpty(port))
        {
            server = $"{server},{port}";
        }

        var builder = new SqlConnectionStringBuilder
        {
            DataSource = server,
            InitialCatalog = configuration["DB_NAME"] ?? "TicketFlow",
            IntegratedSecurity = true,
            TrustServerCertificate = true,
        };
        _connectionString = builder.ConnectionString;
    }

    public IDbConnection CreateConnection()
    {
        var connection = new SqlConnection(_connectionString);
        connection.Open();
        return connection;
    }
}
