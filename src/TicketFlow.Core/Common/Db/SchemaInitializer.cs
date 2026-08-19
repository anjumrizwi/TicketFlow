using System.Data;
using Dapper;

namespace TicketFlow.Core.Common.Db;

/// <summary>
/// Creates the tables this app owns if they don't already exist. Exact
/// port of common/db.py's init_schema() — same IDENTITY/CHECK-constraint/
/// filtered-unique-index/trigger design, see that file's comments for why
/// each construct was chosen over its MySQL predecessor.
/// </summary>
public static class SchemaInitializer
{
    public static void Initialize(IDbConnection connection)
    {
        connection.Execute("""
            IF OBJECT_ID('dbo.users', 'U') IS NULL
            CREATE TABLE users (
                id INT IDENTITY(1,1) PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(60) NOT NULL,
                role VARCHAR(16) NOT NULL DEFAULT 'REQUESTER'
                    CHECK (role IN ('REQUESTER', 'SUPPORT_AGENT')),
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
            )
            """);

        connection.Execute("""
            IF OBJECT_ID('dbo.tickets', 'U') IS NULL
            CREATE TABLE tickets (
                id INT IDENTITY(1,1) PRIMARY KEY,
                ticket_number VARCHAR(20) NULL,
                requester_id INT NOT NULL,
                assignee_id INT NULL,
                title VARCHAR(255) NOT NULL,
                description VARCHAR(MAX) NOT NULL,
                category VARCHAR(32) NOT NULL
                    CHECK (category IN ('Bug', 'Feature Request', 'Access', 'Hardware', 'How-to / Other')),
                priority VARCHAR(16) NOT NULL
                    CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')),
                status VARCHAR(16) NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')),
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                updated_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (requester_id) REFERENCES users(id),
                FOREIGN KEY (assignee_id) REFERENCES users(id)
            )
            """);

        connection.Execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.indexes
                WHERE name = 'UQ_tickets_ticket_number' AND object_id = OBJECT_ID('dbo.tickets')
            )
            CREATE UNIQUE INDEX UQ_tickets_ticket_number ON tickets(ticket_number)
                WHERE ticket_number IS NOT NULL
            """);

        // SQL Server has no column-level "ON UPDATE CURRENT_TIMESTAMP";
        // a trigger is the standard replacement. CREATE TRIGGER must be
        // the only statement in its batch, hence EXEC(...).
        connection.Execute("""
            IF OBJECT_ID('dbo.trg_tickets_updated_at', 'TR') IS NULL
            EXEC('
                CREATE TRIGGER trg_tickets_updated_at ON tickets
                AFTER UPDATE AS
                BEGIN
                    SET NOCOUNT ON;
                    UPDATE t SET updated_at = SYSDATETIME()
                    FROM tickets t
                    INNER JOIN inserted i ON t.id = i.id
                END
            ')
            """);

        connection.Execute("""
            IF OBJECT_ID('dbo.ticket_activity', 'U') IS NULL
            CREATE TABLE ticket_activity (
                id INT IDENTITY(1,1) PRIMARY KEY,
                ticket_id INT NOT NULL,
                actor_id INT NOT NULL,
                action VARCHAR(32) NOT NULL,
                field_changed VARCHAR(64) NULL,
                old_value VARCHAR(MAX) NULL,
                new_value VARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id),
                FOREIGN KEY (actor_id) REFERENCES users(id)
            )
            """);

        connection.Execute("""
            IF OBJECT_ID('dbo.chat_error_log', 'U') IS NULL
            CREATE TABLE chat_error_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                user_id INT NOT NULL,
                error_type VARCHAR(64) NOT NULL,
                error_message VARCHAR(500) NOT NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """);
    }
}
