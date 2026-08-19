using Microsoft.Extensions.Configuration;
using TicketFlow.Core.Common.Db;
using TicketFlow.Core.Features.Auth;
using TicketFlow.Core.Features.SeedData;
using TicketFlow.Core.Features.Tickets;

if (args.Length != 2 || !int.TryParse(args[0], out var numUsers) || !int.TryParse(args[1], out var numTickets))
{
    Console.Error.WriteLine("Usage: dotnet run --project src/TicketFlow.SeedCli -- <users> <tickets>");
    return 1;
}

var configuration = new ConfigurationBuilder().AddEnvironmentVariables().Build();
var dbHost = configuration["DB_HOST"] ?? @"localhost\SQLEXPRESS";

// Checked before ever opening a connection or touching schema: the whole
// point of this guard is to refuse a suspicious target outright, which is
// only a meaningful safeguard if it runs before any connection attempt —
// not after we've already connected to (and possibly modified) that host.
try
{
    SeedDataService.AssertDemoDatabase(dbHost);
}
catch (SeedGuardError ex)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}

if (numUsers < 0 || numTickets < 0)
{
    Console.Error.WriteLine("<users> and <tickets> must be zero or positive.");
    return 1;
}

IDbConnectionFactory connectionFactory = new SqlConnectionFactory(configuration);
using var connection = connectionFactory.CreateConnection();
SchemaInitializer.Initialize(connection);

var ticketService = new TicketService(new SqlTicketRepository());
var seedDataService = new SeedDataService(new SqlUserRepository(), new SqlSeedDataRepository(), ticketService);

var summary = await seedDataService.SeedDemoDataAsync(connection, dbHost, numUsers, numTickets);
Console.WriteLine($"Seeded {summary.Users} users.");
foreach (var (status, count) in summary.TicketsByStatus)
{
    Console.WriteLine($"  {status}: {count}");
}

Console.WriteLine("Re-run with 0 0 to clear the seed without recreating it.");
return 0;
