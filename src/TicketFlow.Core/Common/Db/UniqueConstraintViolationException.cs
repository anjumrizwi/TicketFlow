namespace TicketFlow.Core.Common.Db;

/// <summary>
/// Thrown by a repository when an insert/update violates a unique
/// constraint or index — a driver-agnostic signal so service-layer code
/// (and its tests) never need to know about Microsoft.Data.SqlClient's
/// SqlException directly (which has no public constructor and so can't
/// be raised from a test fake).
/// </summary>
public sealed class UniqueConstraintViolationException : Exception
{
    public UniqueConstraintViolationException(string message, Exception? innerException = null)
        : base(message, innerException)
    {
    }
}
