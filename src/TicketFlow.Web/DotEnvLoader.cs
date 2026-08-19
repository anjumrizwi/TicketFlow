namespace TicketFlow.Web;

/// <summary>
/// Loads KEY=value pairs from the repo-root .env file into process
/// environment variables, mirroring python-dotenv's load_dotenv() in the
/// Python reference app so both apps read secrets (OPENAI_API_KEY) from
/// the same single .env file (NFR-01: secrets only from environment
/// variables, never hardcoded) rather than needing separate
/// configuration. Never logs the file's contents.
/// </summary>
public static class DotEnvLoader
{
    public static void LoadFromRepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, ".env");
            if (File.Exists(candidate))
            {
                Load(candidate);
                return;
            }

            if (Directory.Exists(Path.Combine(directory.FullName, ".git")))
            {
                return; // reached the repo root without finding .env - nothing to load.
            }

            directory = directory.Parent;
        }
    }

    private static void Load(string envFilePath)
    {
        foreach (var line in File.ReadAllLines(envFilePath))
        {
            var trimmed = line.Trim();
            if (trimmed.Length == 0 || trimmed.StartsWith('#'))
            {
                continue;
            }

            var separatorIndex = trimmed.IndexOf('=');
            if (separatorIndex <= 0)
            {
                continue;
            }

            var key = trimmed[..separatorIndex].Trim();
            var value = trimmed[(separatorIndex + 1)..].Trim();

            // Don't override a real environment variable that's already set.
            if (Environment.GetEnvironmentVariable(key) is null)
            {
                Environment.SetEnvironmentVariable(key, value);
            }
        }
    }
}
