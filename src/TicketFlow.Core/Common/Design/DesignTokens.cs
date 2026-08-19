namespace TicketFlow.Core.Common.Design;

/// <summary>
/// Brand palette (BRD §12). Kept in one place so the Blazor UI
/// (wwwroot/css/ticketflow.css) and any non-CSS consumer — e.g. the PDF
/// exporter — stay visually consistent. A CSS file can't reference these
/// constants directly, so TicketFlow.Tests asserts the two stay in sync.
/// </summary>
public static class DesignTokens
{
    public const string ColorGreen = "#00E676";
    public const string ColorPurple = "#6C3FC5";
    public const string ColorPink = "#FF4FA3";
    public const string ColorBackground = "#FFFFFF";
    public const string ColorText = "#000000";
}
