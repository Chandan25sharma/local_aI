"""Entry point for the Local AI Assistant desktop app."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

# In a PyInstaller --onefile build, __file__ is unreliable — bundled data lives under
# sys._MEIPASS (the temp extraction dir). Fall back to the source layout in dev mode.
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "app"


def _load_icon() -> QIcon:
    ico = APP_DIR / "resources" / "icon.ico"
    png = APP_DIR / "resources" / "icon.png"
    path = ico if ico.exists() else png
    return QIcon(str(path))


def _load_stylesheet() -> str:
    qss_path = APP_DIR / "ui" / "style.qss"
    return qss_path.read_text(encoding="utf-8") if qss_path.exists() else ""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Local AI Assistant")
    app.setOrganizationName("LocalAI")

    icon = _load_icon()
    app.setWindowIcon(icon)
    app.setStyleSheet(_load_stylesheet())

    from app.ui.main_window import MainWindow  # imported late so QApplication exists first
    window = MainWindow(icon=icon)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
