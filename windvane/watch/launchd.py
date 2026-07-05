"""macOS launchd integration."""
from __future__ import annotations

import shutil
from pathlib import Path

LABEL = "com.windvane.watch"
def _uv():
    return shutil.which("uv") or "/opt/homebrew/bin/uv"
def generate_plist(project_dir: Path, log_dir: Path) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{_uv()}</string><string>run</string><string>--directory</string><string>{project_dir}</string><string>windvane</string><string>watch</string></array>
  <key>WorkingDirectory</key><string>{project_dir}</string>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>{log_dir / "watch.out.log"}</string>
  <key>StandardErrorPath</key><string>{log_dir / "watch.err.log"}</string>
</dict></plist>
"""
def plist_target(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
def install(project_dir: Path, log_dir: Path, home: Path):
    t = plist_target(home)
    t.parent.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    t.write_text(generate_plist(project_dir, log_dir), encoding="utf-8")
    return t, [f"launchctl unload {t} 2>/dev/null", f"launchctl load {t}"]
