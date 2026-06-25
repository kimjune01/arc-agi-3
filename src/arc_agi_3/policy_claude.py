"""Call Claude as the policy via the `claude` CLI in headless mode.

Uses the local Claude Code subscription (no ARC/Anthropic API key) by shelling
out to `claude -p ... --output-format json` and reading the `result` field.
"""

from __future__ import annotations

import json
import subprocess


class ClaudeError(RuntimeError):
    pass


def ask_claude(
    prompt: str,
    *,
    system: str | None = None,
    model: str = "sonnet",
    timeout: float = 90.0,
) -> str:
    """Send `prompt` to Claude headless, return the text result.

    Runs with tools disabled and no extra turns — this is a pure text policy
    call, not an agentic session.
    """
    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--max-turns", "1",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ClaudeError(f"claude timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise ClaudeError(f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeError(f"non-JSON output: {proc.stdout[:500]}") from e
    if data.get("is_error"):
        raise ClaudeError(f"claude error: {data.get('result')}")
    return (data.get("result") or "").strip()
