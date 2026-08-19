using System.IO;
using TicketFlow.Core.Common.Design;
using Xunit;

namespace TicketFlow.Tests;

/// <summary>
/// A static CSS file can't reference a C# constant, so this test is the
/// concrete mechanism keeping "one place for brand colors" honest across
/// DesignTokens.cs and wwwroot/css/ticketflow.css (see that file's header
/// comment) — if someone changes one without the other, this fails.
/// </summary>
public sealed class DesignTokensCssParityTests
{
    private static string CssFilePath =>
        Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "TicketFlow.Web", "wwwroot", "css", "ticketflow.css");

    [Theory]
    [InlineData("--tf-color-green", DesignTokens.ColorGreen)]
    [InlineData("--tf-color-purple", DesignTokens.ColorPurple)]
    [InlineData("--tf-color-pink", DesignTokens.ColorPink)]
    [InlineData("--tf-color-background", DesignTokens.ColorBackground)]
    [InlineData("--tf-color-text", DesignTokens.ColorText)]
    public void CssCustomProperty_MatchesDesignTokenConstant(string cssVariableName, string expectedHex)
    {
        var css = File.ReadAllText(Path.GetFullPath(CssFilePath));

        var marker = $"{cssVariableName}:";
        var markerIndex = css.IndexOf(marker, StringComparison.Ordinal);
        Assert.True(markerIndex >= 0, $"CSS variable {cssVariableName} not found in ticketflow.css.");

        var valueStart = markerIndex + marker.Length;
        var valueEnd = css.IndexOf(';', valueStart);
        var actualHex = css[valueStart..valueEnd].Trim();

        Assert.Equal(expectedHex, actualHex, ignoreCase: true);
    }
}
