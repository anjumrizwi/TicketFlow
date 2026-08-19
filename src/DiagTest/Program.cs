using OpenAI.Chat;

var apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
if (string.IsNullOrEmpty(apiKey))
{
    Console.WriteLine("OPENAI_API_KEY not set in process env - loading from .env manually for this diagnostic.");
    var envPath = Path.Combine("..", "..", ".env");
    if (File.Exists(envPath))
    {
        foreach (var line in File.ReadAllLines(envPath))
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("OPENAI_API_KEY="))
            {
                apiKey = trimmed["OPENAI_API_KEY=".Length..].Trim();
            }
        }
    }
}

Console.WriteLine($"Key present: {!string.IsNullOrEmpty(apiKey)}, length: {apiKey?.Length ?? 0}, prefix: {apiKey?[..Math.Min(7, apiKey.Length)]}");

try
{
    var client = new ChatClient("gpt-4o-mini", apiKey);
    var response = await client.CompleteChatAsync("Say hello in exactly 3 words.");
    Console.WriteLine("SUCCESS: " + response.Value.Content[0].Text);
}
catch (Exception ex)
{
    Console.WriteLine("EXCEPTION TYPE: " + ex.GetType().FullName);
    Console.WriteLine("EXCEPTION MESSAGE: " + ex.Message);
    if (ex.InnerException is not null)
    {
        Console.WriteLine("INNER: " + ex.InnerException.Message);
    }
}
