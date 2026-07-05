"""macOS notifications via osascript (built-in)."""

from __future__ import annotations

import subprocess


def notify_macos(title: str, message: str, *, subtitle: str = "") -> bool:
    t = title.replace('"', '\\"')
    m = message.replace('"', '\\"')
    s = subtitle.replace('"', '\\"')
    script = f'display notification "{m}" with title "{t}"'
    if s:
        script += f' subtitle "{s}"'
    script += ' sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=10)
        return True
    except Exception:
        return False
