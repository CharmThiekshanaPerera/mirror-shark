"""Dashboard panel: every device on the Wi-Fi, which phones can be connected, and one-click Connect / Mirror."""
import asyncio
import queue
import threading
import time

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .. import theme
from ..adb import Adb
from ..errors import friendly
from ..log import get_logger
from ..scanner import ADB_PORTS, DEEP_PORTS, LEGACY_PORTS, NetDevice, discover_devices, scan_host
from .tasks import keep_alive, run_task
from .widgets import Badge

log = get_logger("network")

HINT_OFF_PHONE = ("Wireless debugging is off or not reachable. On the phone: Settings › System › Developer options › "
                  "Wireless debugging, turn it on and keep that screen open, then press Check again.")
HINT_OFF_OTHER = "No wireless debugging found on this device."
AUTO_REFRESH_MS = 90_000


class DiscoverThread(QThread):
    status = Signal(str)
    devices = Signal(list)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.cancel = threading.Event()

    def run(self) -> None:
        try:
            self.devices.emit(discover_devices(self.cancel, self.status.emit))
        except Exception as e:  # noqa: BLE001 - includes Cancelled
            if not self.cancel.is_set():
                log.warning("discovery failed: %s", e, exc_info=True)
                self.failed.emit(str(e) or e.__class__.__name__)
            else:
                self.failed.emit("")


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

    @property
    def idle(self) -> bool:
        return self._jobs.empty()

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
            done, total = 0, len(ports)

            def progress(n: int) -> None:
                nonlocal done
                done += n
                self.progress.emit(min(done, total), total)

            try:
                found = asyncio.run(scan_host(ip, ports, self.cancel, progress))
            except Exception as e:  # noqa: BLE001 - includes Cancelled
                if self.cancel.is_set():
                    break
                log.warning("probe of %s failed: %s", ip, e)
                found = []
            self.result.emit(ip, [(f.port, f.kind) for f in found])


class NetRow(QFrame):
    check_clicked = Signal(str)     # ip
    connect_clicked = Signal(str)   # ip
    mirror_clicked = Signal(str)    # ip

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
        sub = QLabel(" · ".join(x for x in (dev.ip, dev.mac, dev.label) if x))
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        sub.setMinimumWidth(0)
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
        self.mirror_btn = QPushButton("Mirror")
        self.mirror_btn.setObjectName("primary")
        self.mirror_btn.clicked.connect(lambda: self.mirror_clicked.emit(self.dev.ip))
        for b in (self.check_btn, self.connect_btn, self.mirror_btn):
            top.addWidget(b)
        outer.addLayout(top)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        self.hint.hide()
        outer.addWidget(self.hint)
        self.set_state("self" if dev.is_this_pc else "unchecked")

    def set_state(self, state: str, port: int | None = None) -> None:
        self.state = state
        if port is not None or state in ("unchecked", "off", "self"):
            self.port = port
        self.hint.hide()
        self.check_btn.setVisible(state in ("unchecked", "off"))
        self.check_btn.setText("Check again" if state == "off" else "Check")
        self.connect_btn.setVisible(state in ("on", "connecting"))
        self.connect_btn.setEnabled(state == "on")
        self.connect_btn.setText("Connecting…" if state == "connecting" else "Connect")
        self.mirror_btn.setVisible(state == "connected")
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
        elif state == "connected":
            self.badge.set("Connected", theme.GOOD)
        elif state == "off":
            self.badge.set("Debugging off", theme.WARN)
            self.hint.setText(HINT_OFF_PHONE if self.dev.phone_like else HINT_OFF_OTHER)
            self.hint.show()


class NetworkPanel(QFrame):
    connected = Signal(str)          # address that was connected with adb connect
    mirror_requested = Signal(str)   # ip of a connected phone

    def __init__(self, adb: Adb, parent: QWidget | None = None):
        super().__init__(parent)
        self.adb = adb
        self.setObjectName("card")
        self.rows: dict[str, NetRow] = {}
        self._mdns: dict[str, int] = {}
        self._connected: set[str] = set()
        self._memory: dict[str, tuple[str, int | None]] = {}   # ip -> ("off"|"on", port) from earlier checks
        self._auto_tried: set[str] = set()
        self._connecting = False
        self._probe: ProbeThread | None = None
        self._discover: DiscoverThread | None = None
        self._last_discovery = 0.0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("Devices on your Wi-Fi")
        title.setObjectName("sectionTitle")
        head.addWidget(title)
        head.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(lambda: self.start_discovery())
        self.all_btn = QPushButton("Check all")
        self.all_btn.setToolTip("Check every listed device for wireless debugging (about 20 s each).")
        self.all_btn.clicked.connect(self.check_all)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_all)
        for b in (self.refresh_btn, self.all_btn, self.stop_btn):
            head.addWidget(b)
        lay.addLayout(head)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet(f"QProgressBar {{ background: {theme.SURFACE_2}; border: none; border-radius: 3px; }}"
                               f"QProgressBar::chunk {{ background: {theme.ACCENT}; border-radius: 3px; }}")
        self.bar.setRange(0, 1)
        lay.addWidget(self.bar)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(8)
        lay.addLayout(self.list_layout)

        opts = QHBoxLayout()
        self.auto = QCheckBox("Connect automatically to a phone with wireless debugging")
        self.auto.setChecked(True)
        self.deep = QCheckBox("Check every port (slow)")
        opts.addWidget(self.auto)
        opts.addWidget(self.deep)
        opts.addStretch()
        lay.addLayout(opts)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(AUTO_REFRESH_MS)
        self.stop_btn.setEnabled(False)

    # -- state pushed in by the main window (adb knows what is connected / advertised) ----------------------
    def set_adb_state(self, connected_ips: set[str], mdns: dict[str, int]) -> None:
        self._connected, self._mdns = set(connected_ips), dict(mdns)
        for ip, row in self.rows.items():
            if row.dev.is_this_pc or row.state in ("checking", "connecting"):
                continue
            if ip in self._connected:
                row.set_state("connected")
            elif row.state == "connected":  # was connected, now gone
                row.set_state("on", self._mdns[ip]) if ip in self._mdns else row.set_state("unchecked")
            elif ip in self._mdns and row.state in ("unchecked", "off"):
                row.set_state("on", self._mdns[ip])
        self._maybe_auto_connect()

    # -- discovery ------------------------------------------------------------------------------------
    def start_discovery(self) -> None:
        if self._discover and self._discover.isRunning():
            return
        self._last_discovery = time.monotonic()
        self.bar.setRange(0, 0)
        self._set_status("Looking for devices on your Wi-Fi…")
        self.refresh_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._discover = DiscoverThread()
        keep_alive(self._discover)
        self._discover.status.connect(self._set_status)
        self._discover.devices.connect(self._on_devices)
        self._discover.failed.connect(self._on_failed)
        self._discover.start()

    def _auto_refresh(self) -> None:
        busy = (self._discover and self._discover.isRunning()) or (self._probe and not self._probe.idle)
        if not busy and not self._connecting and self.isVisible():
            self.start_discovery()

    def _on_failed(self, msg: str) -> None:
        self.bar.setRange(0, 1)
        self.refresh_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_status(f"Could not scan the network: {msg}" if msg else "Stopped.", error=bool(msg))

    def _on_devices(self, devices: list) -> None:
        self._stop_probe()
        self._probe = self._new_probe()
        old = self.rows
        self.rows = {}
        while self.list_layout.count():
            w = self.list_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        for dev in devices:
            row = NetRow(dev)
            row.check_clicked.connect(self.check_one)
            row.connect_clicked.connect(self.connect_ip)
            row.mirror_clicked.connect(self.mirror_requested)
            self.rows[dev.ip] = row
            self.list_layout.addWidget(row)
            if dev.is_this_pc:
                continue
            if dev.ip in self._connected:
                row.set_state("connected")
            elif dev.ip in self._mdns:
                row.set_state("on", self._mdns[dev.ip])         # announced itself: no port scan needed
            elif dev.ip in self._memory:
                state, port = self._memory[dev.ip]
                row.set_state(state, port)
            elif dev.phone_like:
                self._enqueue(dev.ip)
        del old
        others = [d for d in devices if not d.is_this_pc]
        n = len(others)
        self._set_status(f"{n} device{'s' if n != 1 else ''} on your Wi-Fi.")
        self.bar.setRange(0, 1)
        self.bar.setValue(1 if not self._probe.idle else 0)
        self.refresh_btn.setEnabled(True)
        self.stop_btn.setEnabled(not self._probe.idle)
        self._maybe_auto_connect()

    # -- probing --------------------------------------------------------------------------------------------
    def _new_probe(self) -> ProbeThread:
        p = ProbeThread()
        keep_alive(p)
        p.checking.connect(self._on_checking)
        p.result.connect(self._on_result)
        p.progress.connect(self._on_progress)
        p.start()
        return p

    def _stop_probe(self) -> None:
        if self._probe:
            self._probe.stop()
            self._probe = None

    def _enqueue(self, ip: str) -> None:
        row = self.rows.get(ip)
        if not row or not self._probe or row.state in ("checking", "connecting", "connected"):
            return
        self._probe.deep = self.deep.isChecked()
        row.set_state("checking")
        self.stop_btn.setEnabled(True)
        self._probe.enqueue(ip)

    def check_one(self, ip: str) -> None:
        self._memory.pop(ip, None)
        self._enqueue(ip)

    def check_all(self) -> None:
        for ip, row in self.rows.items():
            if row.state in ("unchecked", "off"):
                self._memory.pop(ip, None)
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
        if row and row.state != "checking":
            return
        if row:
            if found:
                row.set_state("on", found[0][0])
                self._memory[ip] = ("on", found[0][0])
                self._set_status(f"Wireless debugging is ON at {ip}:{found[0][0]}.", good=True)
                self._maybe_auto_connect()
            else:
                row.set_state("off")
                self._memory[ip] = ("off", None)
                self._set_status(f"No wireless debugging found at {ip}.")
        if self._probe and self._probe.idle:
            self.bar.setRange(0, 1)
            self.bar.setValue(1)
            self.stop_btn.setEnabled(False)

    # -- connecting ----------------------------------------------------------------------------------------
    def _maybe_auto_connect(self) -> None:
        if self._connecting or not self.auto.isChecked() or self._connected:
            return
        ready = [r for r in self.rows.values() if r.state == "on" and r.dev.ip not in self._auto_tried]
        if len(ready) == 1:
            self._auto_tried.add(ready[0].dev.ip)
            self.connect_ip(ready[0].dev.ip)

    def connect_ip(self, ip: str) -> None:
        row = self.rows.get(ip)
        if self._connecting or not row or row.port is None:
            return
        address, port = f"{ip}:{row.port}", row.port
        self._connecting = True
        row.set_state("connecting", port)
        self._set_status(f"Connecting to {address}…")

        def ok(_):
            self._connecting = False
            row.set_state("connected")
            self._connected.add(ip)
            self._set_status(f"Connected to {address}.", good=True)
            self.connected.emit(address)

        def bad(msg):
            self._connecting = False
            row.set_state("on", port)
            text = friendly(msg)
            if "authenticate" in msg.lower() or "unauthorized" in msg.lower():
                text = ("This phone has not been paired with this PC yet. Open Connect a new phone > Step 1 and pair "
                        "using the code shown on the phone (Wireless debugging > Pair device with pairing code).")
            self._set_status(text.split("\n\nDetails")[0], error=True)

        run_task(lambda: self.adb.connect(address), ok, bad)

    # -- helpers -----------------------------------------------------------------------------------------------
    def _set_status(self, text: str, error: bool = False, good: bool = False) -> None:
        color = theme.BAD if error else theme.GOOD if good else theme.MUTED
        self.status.setStyleSheet(f"color: {color};")
        self.status.setText(text)

    def stop_all(self) -> None:
        if self._discover and self._discover.isRunning():
            self._discover.cancel.set()
        if self._probe:
            self._stop_probe()
            self._probe = self._new_probe()
            for row in self.rows.values():
                if row.state == "checking":
                    row.set_state("unchecked")
        self._set_status("Stopped.")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.stop_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)

    def shutdown(self) -> None:
        self._timer.stop()
        if self._discover and self._discover.isRunning():
            self._discover.cancel.set()
        self._stop_probe()
