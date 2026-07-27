#!/usr/bin/env python3
"""Ask for explicit approval before likely live mutations or release pushes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

SITES = ("szl", "siezal", "hsm")
MUTATING_BENCH = re.compile(
    r"\b(migrate|restore|reinstall|install-app|uninstall-app|execute|console|"
    r"set-config|set-maintenance-mode|enable-scheduler|disable-scheduler|"
    r"clear-cache|build|restart|start|update|switch-to-branch)\b",
    re.IGNORECASE,
)
READ_ONLY_SQL = re.compile(r"^\s*(select|show|describe|desc|explain)\b", re.IGNORECASE)


def ask(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


def current_branch(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = str(event.get("tool_input", {}).get("command", ""))
    cwd = Path(event.get("cwd") or ".").resolve()
    lowered = command.lower()

    if "git push" in lowered and "posapplication" in str(cwd).lower():
        if current_branch(cwd) == "main" or re.search(r"\bmain\b", lowered):
            ask("Posapplication main publishes every product. Confirm an intentional versioned release before this push.")
            return 0

    mentions_site = any(
        re.search(rf"(?:--site\s+|sites/|https?://[^ ]*){re.escape(site)}\b", lowered)
        for site in SITES
    )
    bench_command = bool(re.search(r"\bbench\b", lowered))
    sql_command = bool(re.search(r"\b(mariadb|mysql)\b", lowered))

    if bench_command and (mentions_site or "bench migrate" in lowered):
        if MUTATING_BENCH.search(command):
            ask("Likely live-impacting bench command: require exact approval, current backup, verification, and rollback.")
            return 0
        if sql_command:
            match = re.search(r"(?:-e|--execute)\s+(['\"])(.*?)\1", command, re.DOTALL)
            if not match or not READ_ONLY_SQL.match(match.group(2)):
                ask("Database command is not provably read-only. Apply the production gate before continuing.")
                return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
