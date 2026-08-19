using Microsoft.AspNetCore.Components.Authorization;
using TicketFlow.Core.Common.Auth;
using TicketFlow.Core.Common.Db;
using TicketFlow.Core.Features.Auth;
using TicketFlow.Core.Features.Chat;
using TicketFlow.Core.Features.Dashboard;
using TicketFlow.Core.Features.Reports;
using TicketFlow.Core.Features.Tickets;
using TicketFlow.Web;
using TicketFlow.Web.Components;

DotEnvLoader.LoadFromRepoRoot();

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// [Authorize] on a Razor component page is also evaluated by ASP.NET
// Core's HTTP-level endpoint routing (not just Blazor's own
// AuthorizeRouteView), which requires an IAuthenticationService to be
// registered even though our actual auth model never uses it — real
// authorization decisions flow entirely through the circuit-scoped
// CurrentUserAccessor/AppAuthenticationStateProvider below. This cookie
// scheme is registered only to satisfy that DI requirement; the app
// never signs into it.
builder.Services.AddAuthentication().AddCookie(options => options.LoginPath = "/login");
builder.Services.AddAuthorizationCore();
builder.Services.AddCascadingAuthenticationState();
builder.Services.AddScoped<CurrentUserAccessor>();
builder.Services.AddScoped<AuthenticationStateProvider, AppAuthenticationStateProvider>();

builder.Services.AddSingleton<IDbConnectionFactory, SqlConnectionFactory>();
builder.Services.AddScoped<IUserRepository, SqlUserRepository>();
builder.Services.AddScoped<AuthService>();
builder.Services.AddScoped<ITicketRepository, SqlTicketRepository>();
builder.Services.AddScoped<TicketService>();
builder.Services.AddScoped<DashboardService>();
builder.Services.AddScoped<ReportService>();

var openAiApiKey = builder.Configuration["OPENAI_API_KEY"];
if (!string.IsNullOrEmpty(openAiApiKey))
{
    builder.Services.AddSingleton<IChatCompletionClient>(_ => new OpenAiChatCompletionClient(openAiApiKey));
}
else
{
    builder.Services.AddSingleton<IChatCompletionClient, UnconfiguredChatCompletionClient>();
}

builder.Services.AddScoped<IChatErrorLogRepository, SqlChatErrorLogRepository>();
builder.Services.AddScoped<ChatOrchestrator>();

var app = builder.Build();

// One-time schema init at process startup — mirrors app.py's
// @st.cache_resource-guarded _ensure_schema() in the Python reference app,
// simpler here since there's no per-rerun re-execution to guard against.
using (var scope = app.Services.CreateScope())
{
    var connectionFactory = scope.ServiceProvider.GetRequiredService<IDbConnectionFactory>();
    using var connection = connectionFactory.CreateConnection();
    SchemaInitializer.Initialize(connection);
}

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}
app.UseStatusCodePagesWithReExecute("/not-found", createScopeForStatusCodePages: true);
app.UseHttpsRedirection();

app.UseAuthentication();
app.UseAuthorization();
app.UseAntiforgery();

app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
