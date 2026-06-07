"""Creates a Desktop (and optionally Start Menu) shortcut for the packaged app,
using its bundled icon — so it opens like any other installed Windows program.

Usage:  python make_shortcut.py
Run this AFTER `python build_exe.py` has produced dist\\LocalAI Assistant.exe
"""
from __future__ import annotations

from pathlib import Path

import winshell
from win32com.client import Dispatch

ROOT = Path(__file__).resolve().parent
APP_NAME = "LocalAI Assistant"
EXE_PATH = ROOT / "dist" / f"{APP_NAME}.exe"
ICON_PATH = ROOT / "app" / "resources" / "icon.ico"


def _create_shortcut(folder: Path, label: str) -> Path:
    shortcut_path = folder / f"{label}.lnk"
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(EXE_PATH)
    shortcut.WorkingDirectory = str(EXE_PATH.parent)
    shortcut.IconLocation = str(ICON_PATH)
    shortcut.Description = "Your private, local-LLM coding assistant"
    shortcut.save()
    return shortcut_path


def main() -> int:
    if not EXE_PATH.exists():
        print(f"Couldn't find {EXE_PATH}")
        print("Build it first with:  python build_exe.py")
        return 1

    desktop = Path(winshell.desktop())
    start_menu = Path(winshell.start_menu()) / "Programs"

    desktop_shortcut = _create_shortcut(desktop, APP_NAME)
    print(f"Desktop shortcut created: {desktop_shortcut}")

    try:
        start_menu_shortcut = _create_shortcut(start_menu, APP_NAME)
        print(f"Start Menu shortcut created: {start_menu_shortcut}")
    except OSError as exc:
        print(f"Could not create Start Menu shortcut ({exc}) — Desktop shortcut is enough to launch the app.")

    print()
    print(f"Done — double-click the '{APP_NAME}' icon on your Desktop (or search the Start Menu) to launch it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
