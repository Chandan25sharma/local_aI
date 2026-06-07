"""Models page: backend status banner, installed-model list, and a 'pull a model' panel with progress."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from app.backends.base import ModelInfo, NotSupportedError
from app.backends.registry import BackendRegistry
from app.core.workers import BackendStatusWorker, DeleteModelWorker, PullWorker
from app.ui.widgets.model_row import ModelRow

OLLAMA_DOWNLOAD_URL = "https://ollama.com/download"

SUGGESTED_MODELS = [
    "qwen2.5-coder:7b",
    "llama3.1:8b",
    "deepseek-coder:6.7b",
    "nomic-embed-text",
]


class ModelsPage(QWidget):
    def __init__(self, registry: BackendRegistry, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._status_worker: BackendStatusWorker | None = None
        self._pull_worker: PullWorker | None = None
        self._delete_worker: DeleteModelWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        top = QHBoxLayout()
        top.addWidget(QLabel("Backend:"))
        self._backend_selector = QComboBox()
        self._backend_selector.currentIndexChanged.connect(self.refresh)
        top.addWidget(self._backend_selector)
        top.addStretch(1)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh)
        top.addWidget(refresh_btn)
        outer.addLayout(top)

        self._banner = QFrame()
        self._banner.setObjectName("statusBanner")
        banner_layout = QHBoxLayout(self._banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        self._banner_label = QLabel("Checking backend status…")
        self._banner_label.setObjectName("bannerLabel")
        banner_layout.addWidget(self._banner_label, 1)
        self._banner_action = QPushButton("Open download page")
        self._banner_action.setCursor(Qt.PointingHandCursor)
        self._banner_action.clicked.connect(lambda: webbrowser.open(OLLAMA_DOWNLOAD_URL))
        self._banner_action.setVisible(False)
        banner_layout.addWidget(self._banner_action)
        outer.addWidget(self._banner)

        outer.addWidget(QLabel("Installed models"))
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setObjectName("modelListScroll")
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_container)
        self._list_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self._list_scroll, 1)

        outer.addWidget(self._build_pull_panel())

        self._populate_backend_selector()

    # ------------------------------------------------------------------
    def _build_pull_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("pullPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Install a new model"))

        row = QHBoxLayout()
        self._pull_input = QLineEdit()
        self._pull_input.setPlaceholderText("e.g. qwen2.5-coder:7b")
        row.addWidget(self._pull_input, 1)
        self._pull_btn = QPushButton("Pull")
        self._pull_btn.setObjectName("primaryBtn")
        self._pull_btn.setCursor(Qt.PointingHandCursor)
        self._pull_btn.clicked.connect(self._on_pull_clicked)
        row.addWidget(self._pull_btn)
        layout.addLayout(row)

        suggestions_row = QHBoxLayout()
        suggestions_row.addWidget(QLabel("Suggestions:"))
        for name in SUGGESTED_MODELS:
            btn = QPushButton(name)
            btn.setObjectName("chipBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, n=name: self._pull_input.setText(n))
            suggestions_row.addWidget(btn)
        suggestions_row.addStretch(1)
        layout.addLayout(suggestions_row)

        self._pull_status = QLabel("")
        self._pull_status.setObjectName("modelMeta")
        layout.addWidget(self._pull_status)
        self._pull_progress = QProgressBar()
        self._pull_progress.setVisible(False)
        layout.addWidget(self._pull_progress)
        return panel

    # ------------------------------------------------------------------
    def _populate_backend_selector(self) -> None:
        self._backend_selector.blockSignals(True)
        self._backend_selector.clear()
        for backend in self._registry.backends:
            self._backend_selector.addItem(backend.display_name, backend.name)
        self._backend_selector.blockSignals(False)
        self.refresh()

    def refresh_backends(self) -> None:
        current = self._backend_selector.currentData()
        self._populate_backend_selector()
        idx = self._backend_selector.findData(current)
        if idx >= 0:
            self._backend_selector.setCurrentIndex(idx)

    def _current_backend(self):
        name = self._backend_selector.currentData()
        return self._registry.get(name) if name else None

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        backend = self._current_backend()
        self._clear_list()
        if backend is None:
            self._set_banner("No backend configured.", "error")
            return

        manageable = backend.supports_model_management()
        self._pull_input.setEnabled(manageable)
        self._pull_btn.setEnabled(manageable)
        self._pull_status.setText("" if manageable else f"{backend.display_name} doesn't support installing models from this app.")

        self._set_banner(f"Checking {backend.display_name}…", "info")
        self._status_worker = BackendStatusWorker(backend)
        self._status_worker.result.connect(self._on_status_result)
        self._status_worker.failed.connect(self._on_status_failed)
        self._status_worker.start()

    def _on_status_result(self, backend, available: bool, models: list) -> None:
        if backend is not self._current_backend():
            return
        if not available:
            is_ollama = backend.name == "ollama"
            self._set_banner(
                f"⚠ {backend.display_name} is not running or not installed."
                + (" Install it, then start it, and refresh." if is_ollama else " Check that its server is running."),
                "error",
                show_install=is_ollama,
            )
            return
        self._set_banner(f"✓ {backend.display_name} is running — {len(models)} model(s) installed", "ok")
        self._populate_list(models, backend.supports_model_management())

    def _on_status_failed(self, backend, message: str) -> None:
        if backend is self._current_backend():
            self._set_banner(f"⚠ Could not reach {backend.display_name}: {message}", "error",
                             show_install=(backend.name == "ollama"))

    def _set_banner(self, text: str, kind: str, show_install: bool = False) -> None:
        self._banner_label.setText(text)
        self._banner.setProperty("status", kind)
        self._banner.style().unpolish(self._banner)
        self._banner.style().polish(self._banner)
        self._banner_action.setVisible(show_install)

    # ------------------------------------------------------------------
    def _clear_list(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_list(self, models: list[ModelInfo], deletable: bool) -> None:
        self._clear_list()
        if not models:
            empty = QLabel("No models installed yet — pull one below to get started.")
            empty.setObjectName("modelMeta")
            self._list_layout.insertWidget(0, empty)
            return
        for model in models:
            row = ModelRow(model, deletable=deletable)
            row.delete_requested.connect(self._on_delete_requested)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    # ------------------------------------------------------------------
    def _on_pull_clicked(self) -> None:
        backend = self._current_backend()
        name = self._pull_input.text().strip()
        if backend is None or not name:
            return
        if self._pull_worker is not None:
            return
        try:
            if not backend.supports_model_management():
                raise NotSupportedError
        except NotSupportedError:
            return

        self._pull_btn.setEnabled(False)
        self._pull_progress.setVisible(True)
        self._pull_progress.setRange(0, 0)
        self._pull_status.setText(f"Starting download of {name}…")

        self._pull_worker = PullWorker(backend, name)
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.finished_ok.connect(lambda: self._on_pull_done(name))
        self._pull_worker.failed.connect(self._on_pull_failed)
        self._pull_worker.start()

    def _on_pull_progress(self, status: str, completed: int, total: int) -> None:
        if total > 0:
            self._pull_progress.setRange(0, total)
            self._pull_progress.setValue(completed)
            pct = completed / total * 100
            self._pull_status.setText(f"{status} — {pct:.1f}%")
        else:
            self._pull_progress.setRange(0, 0)
            self._pull_status.setText(status)

    def _on_pull_done(self, name: str) -> None:
        self._pull_status.setText(f"✓ {name} installed successfully")
        self._pull_progress.setVisible(False)
        self._pull_btn.setEnabled(True)
        self._pull_input.clear()
        self._pull_worker = None
        self.refresh()

    def _on_pull_failed(self, message: str) -> None:
        self._pull_status.setText(f"⚠ Download failed: {message}")
        self._pull_progress.setVisible(False)
        self._pull_btn.setEnabled(True)
        self._pull_worker = None

    # ------------------------------------------------------------------
    def _on_delete_requested(self, name: str) -> None:
        backend = self._current_backend()
        if backend is None or self._delete_worker is not None:
            return
        confirm = QMessageBox.question(
            self, "Delete model", f"Delete '{name}' from {backend.display_name}? This frees disk space but you'll need to re-download it to use it again.",
        )
        if confirm != QMessageBox.Yes:
            return
        self._delete_worker = DeleteModelWorker(backend, name)
        self._delete_worker.finished_ok.connect(self._on_delete_done)
        self._delete_worker.failed.connect(self._on_delete_failed)
        self._delete_worker.start()

    def _on_delete_done(self, name: str) -> None:
        self._delete_worker = None
        self.refresh()

    def _on_delete_failed(self, name: str, message: str) -> None:
        self._delete_worker = None
        QMessageBox.warning(self, "Delete failed", f"Could not delete '{name}': {message}")
