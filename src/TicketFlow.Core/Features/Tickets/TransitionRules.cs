namespace TicketFlow.Core.Features.Tickets;

/// <summary>
/// Fixed-set values and the BR-02/BR-03 status state machine. Direct port
/// of features/tickets/service.py's module-level constants in the Python
/// reference app.
/// </summary>
public static class TicketConstants
{
    public static readonly IReadOnlyList<string> Priorities = new[] { "LOW", "MEDIUM", "HIGH", "URGENT" };

    public static readonly IReadOnlyList<string> Categories = new[]
    {
        "Bug", "Feature Request", "Access", "Hardware", "How-to / Other",
    };

    public static readonly IReadOnlyList<string> Statuses = new[] { "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED" };

    public static readonly IReadOnlyDictionary<string, IReadOnlySet<string>> AllowedTransitions =
        new Dictionary<string, IReadOnlySet<string>>
        {
            ["OPEN"] = new HashSet<string> { "IN_PROGRESS" },
            ["IN_PROGRESS"] = new HashSet<string> { "RESOLVED" },
            ["RESOLVED"] = new HashSet<string> { "CLOSED", "IN_PROGRESS" },
            ["CLOSED"] = new HashSet<string>(),
        };

    // Only these two fixed-set fields are editable post-creation per FR-STAT-03;
    // used as a validated allowlist before building column names into SQL —
    // the column name itself can't be a bind parameter, so it must come only
    // from this hardcoded dict, never from caller input (see SqlTicketRepository).
    public static readonly IReadOnlyDictionary<string, IReadOnlyList<string>> FieldValidators =
        new Dictionary<string, IReadOnlyList<string>>
        {
            ["priority"] = Priorities,
            ["category"] = Categories,
        };
}
