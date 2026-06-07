"""Builds Local AI Assistant into a single portable .exe with its own icon — no Python or
terminal needed to run it afterwards. Usage:  python build_exe.py
Output:  dist\\LocalAI Assistant.exe
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "LocalAI Assistant"
ICON = ROOT / "app" / "resources" / "icon.ico"
ENTRY = ROOT / "app" / "main.py"


def main() -> int:
    for stale in ("build", "dist", f"{APP_NAME}.spec"):
        path = ROOT / stale
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--icon", str(ICON),
        "--add-data", f"{ROOT / 'app' / 'ui' / 'style.qss'};app/ui",
        "--add-data", f"{ROOT / 'app' / 'resources'};app/resources",
        "--noconfirm",
        str(ENTRY),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe_path = ROOT / "dist" / f"{APP_NAME}.exe"
    print()
    print(f"Build complete: {exe_path}")
    print("Double-click it to run the app — no Python or terminal required.")
    print("Run `python make_shortcut.py` to add a Desktop/Start Menu shortcut with the app icon.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
