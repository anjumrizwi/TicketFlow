using TicketFlow.Core.Features.Chat;
using Xunit;

namespace TicketFlow.Tests.Features.Chat;

/// <summary>
/// AC-10: only a fixed classification string is ever persisted, never
/// the raw exception message (which third-party SDK exceptions aren't
/// guaranteed not to embed request headers, endpoints, or key fragments).
/// </summary>
public sealed class ChatExceptionClassifierTests
{
    [Fact(DisplayName = "classification never includes the exception's own message")]
    public void Classify_NeverIncludesExceptionMessage()
    {
        var exception = new InvalidOperationException("api key sk-secret-should-never-leak was rejected");

        var (errorType, errorMessage) = ChatExceptionClassifier.Classify(exception);

        Assert.Equal(nameof(InvalidOperationException), errorType);
        Assert.Equal(ChatExceptionClassifier.ExternalFailureMessage, errorMessage);
        Assert.DoesNotContain("sk-secret-should-never-leak", errorMessage);
    }

    [Fact(DisplayName = "different exception types are still classified to the same fixed, safe message")]
    public void Classify_DifferentExceptionTypes_SameFixedMessage()
    {
        var (_, message1) = ChatExceptionClassifier.Classify(new TimeoutException("connection to internal-host:443 timed out"));
        var (_, message2) = ChatExceptionClassifier.Classify(new HttpRequestException("401 Unauthorized"));

        Assert.Equal(message1, message2);
        Assert.Equal(ChatExceptionClassifier.ExternalFailureMessage, message1);
    }
}
