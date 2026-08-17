#!/usr/bin/env python3
"""PostToolUse hook for Edit/Write/MultiEdit.

Per the BRD risk mitigation table (Section 14): "Post-hooks format and
test after edits." Formats the touched Python file and runs its nearest
matching test module, if any. Best-effort and non-blocking: a missing
tool (black/ruff/pytest not installed yet) or a project with no tests
yet must never break the edit that already succeeded.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path


def which_or_none(name):
    return shutil.which(name)


def run(cmd, cwd):
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=60
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except Exception as exc:
        return None, str(exc)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return

    path = Path(file_path)
    if not path.exists():
        return

    cwd = payload.get("cwd", str(path.parent))
    notes = []

    if which_or_none("ruff"):
        code, out = run(["ruff", "check", "--fix", str(path)], cwd)
        if code not in (0, None):
            notes.append(f"ruff check found unresolved issues:\n{out.strip()}")
    if which_or_none("black"):
        run(["black", str(path)], cwd)

    if which_or_none("pytest"):
        stem = path.stem
        candidates = list(Path(cwd).rglob(f"test_{stem}.py")) + list(
            Path(cwd).rglob(f"{stem}_test.py")
        )
        if candidates:
            code, out = run(["pytest", "-q", str(candidates[0])], cwd)
            if code not in (0, None):
                notes.append(
                    f"Tests failed after edit ({candidates[0]}):\n{out.strip()[-2000:]}"
                )

    if notes:
        # Non-zero exit with stderr surfaces this feedback back to Claude
        # without blocking the already-completed edit.
        print("\n\n".join(notes), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
