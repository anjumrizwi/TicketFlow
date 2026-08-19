using System.Data;
using TicketFlow.Core.Features.Auth;
using TicketFlow.Core.Features.Tickets;

namespace TicketFlow.Core.Features.SeedData;

/// <summary>Raised for invalid seed-data input.</summary>
public sealed class SeedError : Exception
{
    public SeedError(string message) : base(message)
    {
    }
}

/// <summary>Raised when the target database doesn't look like a local/demo DB.</summary>
public sealed class SeedGuardError : Exception
{
    public SeedGuardError(string message) : base(message)
    {
    }
}

public sealed record SeedSummary
{
    public required int Users { get; init; }
    public required IReadOnlyDictionary<string, int> TicketsByStatus { get; init; }
}

/// <summary>
/// Idempotent demo data generation (specs/seed-data.md). FR-SEED-01..04.
/// Reuses AuthService.HashPassword and TicketService.CreateTicketAsync/
/// TransitionStatusAsync rather than re-deriving password hashing or
/// status-transition rules here — direct port of
/// features/seed_data/service.py in the Python reference app.
/// </summary>
public sealed class SeedDataService
{
    public const string DemoUsernamePrefix = "demo_";

    // Not a real credential: a fixed, obviously-synthetic password shared by
    // every seeded demo account so a presenter/tester can log in as any of them.
    public const string DemoPassword = "DemoPass123!";

    // Weighted so most seeded users are ordinary requesters (BRD §10 roles).
    private static readonly (string Role, int Weight)[] RoleWeights =
    {
        (Roles.Requester, 4),
        (Roles.SupportAgent, 1),
    };

    private static readonly IReadOnlyDictionary<string, string[]> TitlesByCategory = new Dictionary<string, string[]>
    {
        ["Bug"] = new[]
        {
            "Login button unresponsive on mobile",
            "Export cuts off the last row",
            "Dashboard counts don't refresh after status change",
            "Search returns duplicate results",
        },
        ["Feature Request"] = new[]
        {
            "Add dark mode",
            "Allow bulk status updates",
            "Support saved filter presets",
            "Add a keyboard shortcut for ticket search",
        },
        ["Access"] = new[]
        {
            "Need access to the reporting folder",
            "Locked out after password reset",
            "Request elevated permissions for new hire",
            "Cannot see tickets assigned to my team",
        },
        ["Hardware"] = new[]
        {
            "Laptop battery draining too fast",
            "Monitor flickering intermittently",
            "Keyboard keys unresponsive",
            "Docking station not detected",
        },
        ["How-to / Other"] = new[]
        {
            "How do I change my notification settings?",
            "Where can I find past export reports?",
            "How do I reassign a ticket?",
            "General question about the onboarding process",
        },
    };

    // Status -> ordered legal transitions from OPEN needed to reach it. Each
    // step is validated against BR-02 by TransitionStatusAsync itself, so
    // this is just the walk order, not a second copy of the transition rules.
    private static readonly IReadOnlyDictionary<string, string[]> StatusPaths = new Dictionary<string, string[]>
    {
        ["OPEN"] = Array.Empty<string>(),
        ["IN_PROGRESS"] = new[] { "IN_PROGRESS" },
        ["RESOLVED"] = new[] { "IN_PROGRESS", "RESOLVED" },
        ["CLOSED"] = new[] { "IN_PROGRESS", "RESOLVED", "CLOSED" },
    };

    private readonly IUserRepository _users;
    private readonly ISeedDataRepository _seedData;
    private readonly TicketService _tickets;
    private readonly Random _random;

    public SeedDataService(IUserRepository users, ISeedDataRepository seedData, TicketService tickets, Random? random = null)
    {
        _users = users;
        _seedData = seedData;
        _tickets = tickets;
        _random = random ?? Random.Shared;
    }

    /// <summary>
    /// Refuses to seed a database that doesn't look local/demo. A SQL
    /// Server named-instance suffix (e.g. "localhost\SQLEXPRESS") is
    /// stripped before comparing, so this correctly recognizes the
    /// current default connection alongside plain "localhost"/"127.0.0.1".
    /// </summary>
    public static void AssertDemoDatabase(string dbHost)
    {
        var hostPart = dbHost.Trim().ToLowerInvariant().Split('\\')[0];
        if (hostPart is not ("localhost" or "127.0.0.1"))
        {
            throw new SeedGuardError(
                $"Refusing to seed: DB_HOST='{dbHost}' does not look like a local/demo database.");
        }
    }

    private string RandomRole()
    {
        var totalWeight = RoleWeights.Sum(rw => rw.Weight);
        var roll = _random.Next(totalWeight);
        var cumulative = 0;
        foreach (var (role, weight) in RoleWeights)
        {
            cumulative += weight;
            if (roll < cumulative)
            {
                return role;
            }
        }

        return RoleWeights[^1].Role;
    }

    /// <summary>
    /// Delete only demo-prefixed users and their tickets/activity (BR-05-
    /// adjacent: never touch non-seeded/real user data).
    /// </summary>
    private async Task ClearSeededDataAsync(IDbConnection connection)
    {
        var demoUserIds = await _seedData.FindDemoUserIdsAsync(connection, DemoUsernamePrefix);
        if (demoUserIds.Count == 0)
        {
            return;
        }

        var demoTicketIds = await _seedData.FindTicketIdsForUsersAsync(connection, demoUserIds);
        if (demoTicketIds.Count > 0)
        {
            await _seedData.DeleteTicketActivityForTicketsAsync(connection, demoTicketIds);
            await _seedData.DeleteTicketsAsync(connection, demoTicketIds);
        }

        await _seedData.DeleteUsersAsync(connection, demoUserIds);
    }

    private async Task<int> CreateDemoUserAsync(IDbConnection connection, int index)
    {
        var username = $"{DemoUsernamePrefix}user{index:D3}";
        var email = $"{username}@example.invalid";
        var passwordHash = AuthService.HashPassword(DemoPassword);
        var role = RandomRole();

        return await _users.InsertWithRoleAsync(connection, username, email, passwordHash, role);
    }

    private async Task<string> CreateDemoTicketAsync(IDbConnection connection, int userId)
    {
        var category = TicketConstants.Categories[_random.Next(TicketConstants.Categories.Count)];
        var priority = TicketConstants.Priorities[_random.Next(TicketConstants.Priorities.Count)];
        var titles = TitlesByCategory[category];
        var title = titles[_random.Next(titles.Length)];
        var description = $"Demo seed data: {title.ToLowerInvariant()}.";

        var ticket = await _tickets.CreateTicketAsync(connection, userId, title, description, category, priority);

        var statuses = StatusPaths.Keys.ToArray();
        var targetStatus = statuses[_random.Next(statuses.Length)];
        foreach (var step in StatusPaths[targetStatus])
        {
            await _tickets.TransitionStatusAsync(connection, ticket.Id, userId, step);
        }

        return targetStatus;
    }

    /// <summary>
    /// Idempotently (re)generate numUsers demo users, each with
    /// 1..numTickets tickets reached only via legal BR-02 transitions.
    /// Refuses to run against a database that doesn't look local/demo
    /// (SeedGuardError) or against invalid counts (SeedError). Always
    /// clears any previously seeded demo rows first, so re-running never
    /// duplicates or corrupts data and never touches real user data.
    /// </summary>
    public async Task<SeedSummary> SeedDemoDataAsync(IDbConnection connection, string dbHost, int numUsers, int numTickets)
    {
        if (numUsers < 0 || numTickets < 0)
        {
            throw new SeedError("<users> and <tickets> must be zero or positive.");
        }

        AssertDemoDatabase(dbHost);
        await ClearSeededDataAsync(connection);

        var users = 0;
        var ticketsByStatus = StatusPaths.Keys.ToDictionary(status => status, _ => 0);

        for (var i = 1; i <= numUsers; i++)
        {
            var userId = await CreateDemoUserAsync(connection, i);
            users++;

            var ticketCount = numTickets > 0 ? _random.Next(1, numTickets + 1) : 0;
            for (var t = 0; t < ticketCount; t++)
            {
                var status = await CreateDemoTicketAsync(connection, userId);
                ticketsByStatus[status]++;
            }
        }

        return new SeedSummary { Users = users, TicketsByStatus = ticketsByStatus };
    }
}
