"""Scan the network for phones with Wireless debugging on, and connect to the one you pick."""
import threading

from PySide6.QtCore import QSettings, Qt, Signal, QThread
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from .. import APP_ID, theme
from ..adb import Adb
from ..errors import friendly
from ..log import get_logger
from ..scanner import Found, scan_network
from .tasks import keep_alive, run_task

log = get_logger("scan")


class ScanThread(QThread):
    status = Signal(str)
    progress = Signal(int, int)
    found = Signal(str, int, str)   # ip, port, kind
    finished_scan = Signal(int)     # number of phones found

    def __init__(self, deep: bool, stop_at_first: bool):
        super().__init__()
        self.cancel = threading.Event()
        self._deep = deep
        self._stop_at_first = stop_at_first

    def run(self) -> None:
        try:
            results = scan_network(
                self.cancel,
                on_status=self.status.emit,
                on_progress=self.progress.emit,
                on_found=lambda f: self.found.emit(f.ip, f.port, f.kind),
                deep=self._deep,
                stop_at_first=self._stop_at_first,
            )
        except Exception as e:  # noqa: BLE001 - never let a scan crash the app
            log.warning("scan failed: %s", e, exc_info=True)
            self.status.emit(f"Scan failed: {e}")
            results = []
        self.finished_scan.emit(len(results))


class ResultRow(QFrame):
    connect_clicked = Signal(str)

    def __init__(self, found: Found):
        super().__init__()
        self.address = found.address
        self.setObjectName("deviceRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel(found.address)
        title.setObjectName("sectionTitle")
        kind = "Wireless debugging" if found.kind == "wireless" else "ADB over TCP (adb tcpip)"
        sub = QLabel(f"{kind} is on")
        sub.setObjectName("muted")
        text.addWidget(title)
        text.addWidget(sub)
        lay.addLayout(text, 1)
        self.button = QPushButton("Connect")
        self.button.setObjectName("primary")
        self.button.clicked.connect(lambda: self.connect_clicked.emit(self.address))
        lay.addWidget(self.button)


class ScanDialog(QDialog):
    connected = Signal(str)  # address that was connected

    def __init__(self, adb: Adb, parent: QWidget | None = None):
        super().__init__(parent)
        self.adb = adb
        self.settings = QSettings(APP_ID, APP_ID)
        self._thread: ScanThread | None = None
        self._connecting = False
        self._rows: dict[str, ResultRow] = {}
        self.setWindowTitle("Scan for phones")
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        title = QLabel("Scan the network for wireless debugging")
        title.setObjectName("sectionTitle")
        hint = QLabel("Turn on <b>Wireless debugging</b> on the phone (Settings › System › Developer options) and "
                      "keep it on the same Wi-Fi as this PC. Mirror Shark looks for it without needing the IP or port.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        hint.setTextFormat(Qt.RichText)
        lay.addWidget(title)
        lay.addWidget(hint)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(f"QProgressBar {{ background: {theme.SURFACE_2}; border: none; border-radius: 4px; }}"
                               f"QProgressBar::chunk {{ background: {theme.ACCENT}; border-radius: 4px; }}")
        lay.addWidget(self.bar)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.results = QVBoxLayout()
        self.results.setSpacing(8)
        lay.addLayout(self.results)

        self.auto = QCheckBox("Connect automatically when a phone is found")
        self.auto.setChecked(self.settings.value("scan_auto_connect", "true") == "true")
        lay.addWidget(self.auto)

        row = QHBoxLayout()
        self.scan_btn = QPushButton("Scan again")
        self.scan_btn.clicked.connect(lambda: self.start_scan())
        self.all_btn = QPushButton("Scan all devices")
        self.all_btn.setToolTip("Do not stop at the first phone found; also check routers and PCs.")
        self.all_btn.clicked.connect(lambda: self.start_scan(stop_at_first=False))
        self.deep_btn = QPushButton("Deep scan")
        self.deep_btn.setToolTip("Check every port (slow, a few minutes). Use if the normal scan finds nothing.")
        self.deep_btn.clicked.connect(lambda: self.start_scan(deep=True))
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_scan)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for b in (self.scan_btn, self.all_btn, self.deep_btn, self.stop_btn):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)

        self.start_scan()

    # -- scanning ---------------------------------------------------------------------
    def start_scan(self, deep: bool = False, stop_at_first: bool = True) -> None:
        if self._thread and self._thread.isRunning():
            return
        while self.results.count():
            w = self.results.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._rows.clear()
        self.bar.setRange(0, 0)  # busy while hosts are discovered
        self.status.setText("Starting…")
        self.status.setStyleSheet(f"color: {theme.MUTED};")
        self._set_running(True)
        self._thread = ScanThread(deep, stop_at_first)
        keep_alive(self._thread)
        self._thread.status.connect(self._on_status)
        self._thread.progress.connect(self._on_progress)
        self._thread.found.connect(self._on_found)
        self._thread.finished_scan.connect(self._on_done)
        self._thread.start()

    def stop_scan(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel.set()
            self.status.setText("Stopping…")

    def _set_running(self, running: bool) -> None:
        self.stop_btn.setEnabled(running)
        for b in (self.scan_btn, self.all_btn, self.deep_btn):
            b.setEnabled(not running)

    def _on_status(self, text: str) -> None:
        self.status.setText(text)

    def _on_progress(self, done: int, total: int) -> None:
        if total > 1:
            self.bar.setRange(0, total)
            self.bar.setValue(done)

    def _on_found(self, ip: str, port: int, kind: str) -> None:
        f = Found(ip, port, kind)
        if f.address in self._rows:
            return
        row = ResultRow(f)
        row.connect_clicked.connect(self.connect_to)
        self.results.addWidget(row)
        self._rows[f.address] = row
        if self.auto.isChecked() and not self._connecting:
            self.connect_to(f.address)

    def _on_done(self, count: int) -> None:
        self._set_running(False)
        self.bar.setRange(0, 1)
        self.bar.setValue(1 if count else 0)
        if count == 0 and "stopped" not in self.status.text().lower():
            self.status.setText(
                "No phone with Wireless debugging was found. Check that it is switched ON (open its screen, not just the "
                "toggle), that the phone and PC share the same Wi-Fi and that the router does not isolate devices "
                "(guest networks often do). You can also try Deep scan, or enter the IP:port by hand.")
            self.status.setStyleSheet(f"color: {theme.WARN};")

    # -- connecting -------------------------------------------------------------------
    def connect_to(self, address: str) -> None:
        if self._connecting:
            return
        self._connecting = True
        row = self._rows.get(address)
        if row:
            row.button.setEnabled(False)
            row.button.setText("Connecting…")
        self.status.setStyleSheet(f"color: {theme.MUTED};")
        self.status.setText(f"Connecting to {address}…")

        def ok(_):
            self._connecting = False
            self.settings.setValue("scan_auto_connect", "true" if self.auto.isChecked() else "false")
            self.status.setStyleSheet(f"color: {theme.GOOD};")
            self.status.setText(f"Connected to {address}.")
            self.connected.emit(address)
            self.accept()

        def bad(msg):
            self._connecting = False
            if row:
                row.button.setEnabled(True)
                row.button.setText("Connect")
            text = friendly(msg)
            if "authenticate" in msg.lower() or "unauthorized" in msg.lower():
                text = ("This phone has not been paired with this PC yet. Close this window, open Connect a new phone > "
                        "Step 1 and pair using the code on the phone (Wireless debugging > Pair device with pairing code).")
            self.status.setStyleSheet(f"color: {theme.BAD};")
            self.status.setText(text.split("\n\nDetails")[0])

        run_task(lambda: self.adb.connect(address), ok, bad)

    # -- shutdown ---------------------------------------------------------------------
    def done(self, result: int) -> None:
        self.stop_scan()
        self.settings.setValue("scan_auto_connect", "true" if self.auto.isChecked() else "false")
        super().done(result)
