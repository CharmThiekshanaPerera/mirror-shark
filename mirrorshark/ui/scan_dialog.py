"""Devices on my Wi-Fi: lists every device on the network, checks which ones have Wireless debugging on, and connects."""
import asyncio
import queue
import threading

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import APP_ID, theme
from ..adb import Adb
from ..errors import friendly
from ..log import get_logger
from ..scanner import ADB_PORTS, DEEP_PORTS, LEGACY_PORTS, NetDevice, discover_devices, scan_host
from .tasks import keep_alive, run_task
from .widgets import Badge

log = get_logger("scan")

HINT_OFF_PHONE = ("Wireless debugging is off or not reachable. On the phone: Settings › System › Developer options › "
                  "Wireless debugging, turn it on and keep that screen open, then press Check.")
HINT_OFF_OTHER = "No wireless debugging found on this device."


class DiscoverThread(QThread):
    """Finds every device on the network, plus what adb already knows (connected phones, mDNS)."""
    status = Signal(str)
    devices = Signal(list, dict, set)   # NetDevice list, {ip: port} from mDNS, {ip} already connected in adb
    failed = Signal(str)

    def __init__(self, adb: Adb):
        super().__init__()
        self.cancel = threading.Event()
        self._adb = adb

    def run(self) -> None:
        try:
            devs = discover_devices(self.cancel, self.status.emit)
            mdns, connected = {}, set()
            try:
                for s in self._adb.mdns_services():
                    if s.kind == "connect":
                        ip, _, port = s.address.rpartition(":")
                        mdns[ip] = int(port)
                for d in self._adb.devices():
                    if d.state == "device":
                        ip = d.serial.rpartition(":")[0] if ":" in d.serial else ""
                        if ip:
                            connected.add(ip)
                        else:  # mDNS-named serial: match through the advertised name
                            base = d.serial.split("._adb")[0]
                            for s in self._adb.mdns_services():
                                if s.name == base:
                                    connected.add(s.address.rpartition(":")[0])
            except Exception as e:  # noqa: BLE001 - adb hiccups must not hide the device list
                log.warning("adb lookup failed: %s", e)
            self.devices.emit(devs, mdns, connected)
        except Exception as e:  # noqa: BLE001
            log.warning("discovery failed: %s", e, exc_info=True)
            self.failed.emit(str(e) or e.__class__.__name__)


class ProbeThread(QThread):
    """Checks devices one at a time for a wireless debugging port. Jobs arrive through enqueue()."""
    checking = Signal(str)
    result = Signal(str, list)      # ip, [(port, kind)]
    progress = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.cancel = threading.Event()
        self.deep = False
        self._jobs: queue.Queue = queue.Queue()

    def enqueue(self, ip: str) -> None:
        self._jobs.put(ip)

    def stop(self) -> None:
        self.cancel.set()
        self._jobs.put(None)

    def run(self) -> None:
        while not self.cancel.is_set():
            ip = self._jobs.get()
            if ip is None:
                break
            self.checking.emit(ip)
            lo, hi = DEEP_PORTS if self.deep else ADB_PORTS
            ports = list(LEGACY_PORTS) + [p for p in range(lo, hi + 1) if p not in LEGACY_PORTS]
            done = 0
            total = len(ports)

            def progress(n: int) -> None:
                nonlocal done
                done += n
                self.progress.emit(min(done, total), total)

            try:
                found = asyncio.run(scan_host(ip, ports, self.cancel, progress))
            except Exception as e:  # noqa: BLE001 - includes Cancelled
                if not self.cancel.is_set():
                    log.warning("probe of %s failed: %s", ip, e)
                found = []
                if self.cancel.is_set():
                    break
            self.result.emit(ip, [(f.port, f.kind) for f in found])


class NetRow(QFrame):
    check_clicked = Signal(str)     # ip
    connect_clicked = Signal(str)   # ip

    def __init__(self, dev: NetDevice):
        super().__init__()
        self.dev = dev
        self.port: int | None = None
        self.state = "unchecked"
        self.setObjectName("deviceRow")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(4)
        top = QHBoxLayout()
        icon = QLabel(dev.icon)
        icon.setStyleSheet("font-size: 22px; background: transparent;")
        top.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(0)
        title = QLabel(dev.title)
        title.setObjectName("sectionTitle")
        detail = " · ".join(x for x in (dev.ip, dev.mac, dev.label) if x)
        sub = QLabel(detail)
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(sub)
        top.addLayout(text, 1)
        self.badge = Badge("", theme.MUTED)
        top.addWidget(self.badge)
        self.check_btn = QPushButton("Check")
        self.check_btn.clicked.connect(lambda: self.check_clicked.emit(self.dev.ip))
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.clicked.connect(lambda: self.connect_clicked.emit(self.dev.ip))
        top.addWidget(self.check_btn)
        top.addWidget(self.connect_btn)
        outer.addLayout(top)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        self.hint.hide()
        outer.addWidget(self.hint)
        self.set_state("self" if dev.is_this_pc else "unchecked")

    def set_state(self, state: str, port: int | None = None) -> None:
        self.state = state
        self.port = port
        self.hint.hide()
        self.check_btn.setVisible(state in ("unchecked", "off"))
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check again" if state == "off" else "Check")
        self.connect_btn.setVisible(state == "on")
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("Connect")
        if state == "self":
            self.badge.set("This PC", theme.MUTED)
        elif state == "unchecked":
            self.badge.set("Not checked", theme.MUTED)
        elif state == "checking":
            self.badge.set("Checking…", theme.ACCENT)
        elif state == "on":
            self.badge.set("Wireless debugging ON", theme.GOOD)
        elif state == "connecting":
            self.badge.set("Connecting…", theme.ACCENT)
            self.connect_btn.setVisible(True)
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("Connecting…")
        elif state == "connected":
            self.badge.set("Connected", theme.GOOD)
        elif state == "off":
            self.badge.set("Debugging off", theme.WARN)
            self.hint.setText(HINT_OFF_PHONE if self.dev.phone_like else HINT_OFF_OTHER)
            self.hint.show()


class ScanDialog(QDialog):
    connected = Signal(str)  # address that was connected

    def __init__(self, adb: Adb, parent: QWidget | None = None):
        super().__init__(parent)
        self.adb = adb
        self.settings = QSettings(APP_ID, APP_ID)
        self.rows: dict[str, NetRow] = {}
        self._connecting = False
        self._probe: ProbeThread | None = None
        self._discover: DiscoverThread | None = None
        self.setWindowTitle("Devices on my Wi-Fi")
        self.setMinimumSize(600, 520)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        title = QLabel("Devices on my Wi-Fi")
        title.setObjectName("sectionTitle")
        hint = QLabel("Every device on your network is listed. Phones are checked automatically for <b>Wireless "
                      "debugging</b>; press <b>Connect</b> on the one you want. Other devices can be checked on demand.")
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        self.list_layout = QVBoxLayout(holder)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        scroll.setWidget(holder)
        lay.addWidget(scroll, 1)

        self.auto = QCheckBox("Connect automatically when a phone with wireless debugging is found")
        self.auto.setChecked(self.settings.value("scan_auto_connect", "true") == "true")
        self.deep = QCheckBox("Check every port (slow, use if a phone is not found)")
        lay.addWidget(self.auto)
        lay.addWidget(self.deep)

        row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh list")
        self.refresh_btn.clicked.connect(self.start_discovery)
        self.all_btn = QPushButton("Check all devices")
        self.all_btn.setToolTip("Check every listed device for wireless debugging (about 20 s each).")
        self.all_btn.clicked.connect(self.check_all)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_all)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        for b in (self.refresh_btn, self.all_btn, self.stop_btn):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)

        self.start_discovery()

    # -- discovery -----------------------------------------------------------------------------
    def start_discovery(self) -> None:
        if self._discover and self._discover.isRunning():
            return
        self._stop_probe()
        for r in self.rows.values():
            r.deleteLater()
        self.rows.clear()
        self.bar.setRange(0, 0)
        self._set_status("Looking for devices…")
        self.refresh_btn.setEnabled(False)
        self.all_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._discover = DiscoverThread(self.adb)
        keep_alive(self._discover)
        self._discover.status.connect(self._set_status)
        self._discover.devices.connect(self._on_devices)
        self._discover.failed.connect(lambda m: (self._set_status(f"Scan failed: {m}", error=True), self._idle()))
        self._discover.start()

    def _on_devices(self, devices: list, mdns: dict, connected: set) -> None:
        self._probe = ProbeThread()
        keep_alive(self._probe)
        self._probe.checking.connect(self._on_checking)
        self._probe.result.connect(self._on_result)
        self._probe.progress.connect(self._on_progress)
        self._probe.start()
        for dev in devices:
            row = NetRow(dev)
            row.check_clicked.connect(self.check_one)
            row.connect_clicked.connect(self.connect_ip)
            self.rows[dev.ip] = row
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            if dev.is_this_pc:
                continue
            if dev.ip in connected:
                row.set_state("connected")
            elif dev.ip in mdns:
                row.set_state("on", mdns[dev.ip])       # phone announced itself: no port scan needed
            elif dev.phone_like:
                self._enqueue(dev.ip)
        others = [d for d in devices if not d.is_this_pc]
        phones = sum(1 for d in others if d.phone_like)
        self._set_status(f"{len(others)} device{'s' if len(others) != 1 else ''} on your Wi-Fi"
                         f" ({phones} phone-like). Checking phones for wireless debugging…" if phones
                         else f"{len(others)} device{'s' if len(others) != 1 else ''} on your Wi-Fi. "
                              "No phone-like device found; use Check on any device.")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.refresh_btn.setEnabled(True)
        self.all_btn.setEnabled(True)
        self._maybe_auto_connect()

    # -- probing -------------------------------------------------------------------------------------
    def _enqueue(self, ip: str) -> None:
        row = self.rows.get(ip)
        if not row or not self._probe or row.state in ("checking", "connecting", "connected"):
            return  # already being checked / nothing to check
        self._probe.deep = self.deep.isChecked()
        row.set_state("checking")
        self._probe.enqueue(ip)

    def check_one(self, ip: str) -> None:
        self._enqueue(ip)

    def check_all(self) -> None:
        for ip, row in self.rows.items():
            if row.state in ("unchecked", "off"):
                self._enqueue(ip)

    def _on_checking(self, ip: str) -> None:
        self._set_status(f"Checking {ip} for wireless debugging…")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)

    def _on_progress(self, done: int, total: int) -> None:
        self.bar.setRange(0, total)
        self.bar.setValue(done)

    def _on_result(self, ip: str, found: list) -> None:
        row = self.rows.get(ip)
        if not row:
            return
        if found:
            row.set_state("on", found[0][0])
            self._set_status(f"Wireless debugging is ON at {ip}:{found[0][0]}.")
            self._maybe_auto_connect()
        else:
            row.set_state("off")
            self._set_status(f"No wireless debugging found at {ip}.")
        if self._probe and self._probe._jobs.empty():
            self.bar.setRange(0, 1)
            self.bar.setValue(1)

    # -- connecting --------------------------------------------------------------------------------------
    def _maybe_auto_connect(self) -> None:
        if self._connecting or not self.auto.isChecked():
            return
        ready = [r for r in self.rows.values() if r.state == "on"]
        if len(ready) == 1 and not any(r.state == "connected" for r in self.rows.values()):
            self.connect_ip(ready[0].dev.ip)

    def connect_ip(self, ip: str) -> None:
        row = self.rows.get(ip)
        if self._connecting or not row or row.port is None:
            return
        address = f"{ip}:{row.port}"
        self._connecting = True
        row.set_state("connecting", row.port)
        self._set_status(f"Connecting to {address}…")

        def ok(_):
            self._connecting = False
            row.set_state("connected")
            self.settings.setValue("scan_auto_connect", "true" if self.auto.isChecked() else "false")
            self._set_status(f"Connected to {address}.", good=True)
            self.connected.emit(address)
            self.accept()

        def bad(msg):
            self._connecting = False
            row.set_state("on", row.port)
            text = friendly(msg)
            if "authenticate" in msg.lower() or "unauthorized" in msg.lower():
                text = ("This phone has not been paired with this PC yet. Close this window, open Connect a new phone > "
                        "Step 1 and pair using the code shown on the phone (Wireless debugging > Pair device with "
                        "pairing code).")
            self._set_status(text.split("\n\nDetails")[0], error=True)

        run_task(lambda: self.adb.connect(address), ok, bad)

    # -- helpers -----------------------------------------------------------------------------------------------
    def _set_status(self, text: str, error: bool = False, good: bool = False) -> None:
        color = theme.BAD if error else theme.GOOD if good else theme.MUTED
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(text)

    def _idle(self) -> None:
        self.bar.setRange(0, 1)
        self.refresh_btn.setEnabled(True)
        self.all_btn.setEnabled(True)

    def _stop_probe(self) -> None:
        if self._probe:
            self._probe.stop()
            self._probe = None

    def stop_all(self) -> None:
        if self._discover and self._discover.isRunning():
            self._discover.cancel.set()
        if self._probe:
            self._probe.cancel.set()  # stops the running check; a fresh worker starts on the next check
            self._probe.stop()
            self._probe = ProbeThread()
            keep_alive(self._probe)
            self._probe.checking.connect(self._on_checking)
            self._probe.result.connect(self._on_result)
            self._probe.progress.connect(self._on_progress)
            self._probe.start()
            for row in self.rows.values():
                if row.state == "checking":
                    row.set_state("unchecked")
        self._set_status("Stopped.")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)

    def done(self, result: int) -> None:
        if self._discover and self._discover.isRunning():
            self._discover.cancel.set()
        self._stop_probe()
        self.settings.setValue("scan_auto_connect", "true" if self.auto.isChecked() else "false")
        super().done(result)
