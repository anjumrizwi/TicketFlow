namespace TicketFlow.Core.Features.Chat;

/// <summary>
/// Fixed, non-sensitive classification for any exception AskAsync lets
/// escape (LLM/API/network failures). Never the exception's Message:
/// third-party SDK exceptions aren't guaranteed not to embed request
/// headers, endpoints, or key fragments, so only the exception's class
/// name is recorded (specs/chat-assistant.md AC-10, NFR-01).
/// </summary>
public static class ChatExceptionClassifier
{
    public const string ExternalFailureMessage = "The AI service call failed or was unreachable.";

    public static (string ErrorType, string ErrorMessage) Classify(Exception exception) =>
        (exception.GetType().Name, ExternalFailureMessage);
}
