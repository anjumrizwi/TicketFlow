using TicketFlow.Core.Features.Auth;

namespace TicketFlow.Core.Common.Auth;

/// <summary>
/// Holds the logged-in user for one Blazor Server circuit — the C#
/// equivalent of common/session.py's st.session_state wrapper in the
/// Python reference app. Registered scoped (per-circuit), giving the
/// same "lives for one session" lifetime as Streamlit's session_state.
/// </summary>
public sealed class CurrentUserAccessor
{
    public User? CurrentUser { get; private set; }

    public bool IsAuthenticated => CurrentUser is not null;

    /// <summary>Raised after Login/Logout so AppAuthenticationStateProvider can notify Blazor.</summary>
    public event Action? Changed;

    public void Login(User user)
    {
        CurrentUser = user;
        Changed?.Invoke();
    }

    public void Logout()
    {
        CurrentUser = null;
        Changed?.Invoke();
    }
}
