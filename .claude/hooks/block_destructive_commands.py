#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool.

Blocks destructive database/shell operations before they run, per the BRD
risk mitigation table (Section 14): "Pre-hooks block dangerous operations
such as DROP TABLE; safe operations can be auto-approved."

Reads the PreToolUse JSON payload from stdin and writes a permission
decision to stdout. Never silently swallows an error: any exception here
falls through to a conservative "ask" decision rather than allowing an
unreviewed command through.
"""
import json
import re
import sys

DESTRUCTIVE_PATTERNS = [
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", "DROP TABLE/DATABASE"),
    (r"\bTRUNCATE\s+TABLE\b", "TRUNCATE TABLE"),
    (r"\bDELETE\s+FROM\s+\w+\s*;", "DELETE FROM without a WHERE clause"),
    (r"\bALTER\s+TABLE\b.*\bDROP\b", "ALTER TABLE ... DROP"),
    (r"\brm\s+-rf\b", "rm -rf"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "git push --force"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bgit\s+clean\s+-[a-z]*f", "git clean -f"),
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # If we can't parse the hook payload at all, fail safe: don't block,
        # don't crash the tool call either. Let normal permissions apply.
        print(json.dumps({}))
        return

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        print(json.dumps({}))
        return

    command = payload.get("tool_input", {}).get("command", "") or ""

    for pattern, label in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked: command matches destructive pattern "
                        f"'{label}'. If this is genuinely needed, run it "
                        f"manually outside Claude Code after review."
                    ),
                }
            }
            print(json.dumps(output))
            return

    # No match: stay silent so normal permission rules (settings.json) decide.
    print(json.dumps({}))


if __name__ == "__main__":
    main()
