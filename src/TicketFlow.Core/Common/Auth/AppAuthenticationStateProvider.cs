using System.Security.Claims;
using Microsoft.AspNetCore.Components.Authorization;

namespace TicketFlow.Core.Common.Auth;

/// <summary>
/// Bridges CurrentUserAccessor into Blazor's [Authorize]/&lt;AuthorizeView&gt;
/// system, so pages/components can use the framework's own auth
/// primitives instead of manually checking IsAuthenticated everywhere
/// (that manual check is what common/session.py's require_auth() did in
/// the Python reference app via st.stop() — Blazor's routing handles the
/// "redirect to login" part declaratively instead, see Routes.razor).
/// </summary>
public sealed class AppAuthenticationStateProvider : AuthenticationStateProvider
{
    private readonly CurrentUserAccessor _currentUser;

    public AppAuthenticationStateProvider(CurrentUserAccessor currentUser)
    {
        _currentUser = currentUser;
        _currentUser.Changed += () => NotifyAuthenticationStateChanged(GetAuthenticationStateAsync());
    }

    public override Task<AuthenticationState> GetAuthenticationStateAsync()
    {
        var identity = _currentUser.CurrentUser is { } user
            ? new ClaimsIdentity(
                new[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                    new Claim(ClaimTypes.Name, user.Username),
                    new Claim(ClaimTypes.Email, user.Email),
                    new Claim(ClaimTypes.Role, user.Role),
                },
                authenticationType: "TicketFlow")
            : new ClaimsIdentity();

        return Task.FromResult(new AuthenticationState(new ClaimsPrincipal(identity)));
    }
}
