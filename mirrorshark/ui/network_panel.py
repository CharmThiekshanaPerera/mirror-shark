"""Dashboard panel: every device on the Wi-Fi, which phones can be connected, and one-click Connect / Mirror."""
import asyncio
import queue
import threading
import time

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from .. import helper as helper_mod
from .. import theme
from ..adb import Adb
from ..errors import friendly
from ..log import get_logger
from ..scanner import ADB_PORTS, DEEP_PORTS, LEGACY_PORTS, NetDevice, discover_devices, scan_host
from .tasks import keep_alive, run_task
from .widgets import Badge

log = get_logger("network")

HINT_OFF_HELPER = ("Press “Request screen share”: the phone shows a request, and when its owner taps Accept, Mirror Shark "
                   "turns on Wireless debugging, connects and opens the screen.")
HINT_OFF_PHONE = ("Wireless debugging is off and Mirror Shark Helper is not on this phone yet, so it cannot be asked "
                  "remotely. Turn Wireless debugging on by hand (Settings › System › Developer options), then press Check "
                  "again. To use “Request screen share” next time, set up the helper once with More › Set up phone helper.")
HINT_UNPAIRED = ("Wireless debugging is on, but this phone has not been paired with this PC yet (or its port changed). On the "
                 "phone open Wireless debugging › Pair device with pairing code, then press Pair… here and enter the code.")
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
    result = Signal(str, list, object)   # ip, [(port, kind)], HelperInfo or None
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
            self.result.emit(ip, [(f.port, f.kind) for f in found], helper_mod.probe(ip))


class NetRow(QFrame):
    check_clicked = Signal(str)     # ip
    connect_clicked = Signal(str)   # ip
    mirror_clicked = Signal(str)    # ip
    request_clicked = Signal(str)   # ip
    pair_clicked = Signal(str)      # ip

    def __init__(self, dev: NetDevice):
        super().__init__()
        self.dev = dev
        self.helper = None
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
        self.helper_badge = Badge("Helper ready", theme.GOOD)
        self.helper_badge.setToolTip("Mirror Shark Helper is running on this phone, so you can send it a screen-share request.")
        self.helper_badge.hide()
        top.addWidget(self.helper_badge)
        self.badge = Badge("", theme.MUTED)
        top.addWidget(self.badge)
        self.request_btn = QPushButton("Request screen share")
        self.request_btn.setObjectName("primary")
        self.request_btn.clicked.connect(lambda: self.request_clicked.emit(self.dev.ip))
        self.pair_btn = QPushButton("Pair…")
        self.pair_btn.setObjectName("primary")
        self.pair_btn.clicked.connect(lambda: self.pair_clicked.emit(self.dev.ip))
        self.check_btn = QPushButton("Check")
        self.check_btn.clicked.connect(lambda: self.check_clicked.emit(self.dev.ip))
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.clicked.connect(lambda: self.connect_clicked.emit(self.dev.ip))
        self.mirror_btn = QPushButton("Mirror")
        self.mirror_btn.setObjectName("primary")
        self.mirror_btn.clicked.connect(lambda: self.mirror_clicked.emit(self.dev.ip))
        # buttons sit on their own line so a row always fits, however narrow the window is
        actions = QHBoxLayout()
        actions.addStretch()
        for b in (self.request_btn, self.pair_btn, self.check_btn, self.connect_btn, self.mirror_btn):
            b.hide()
            actions.addWidget(b)
        outer.addLayout(top)
        outer.addLayout(actions)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        self.hint.hide()
        outer.addWidget(self.hint)
        self.set_state("self" if dev.is_this_pc else "unchecked")

    def set_helper(self, info) -> None:
        self.helper = info
        self.helper_badge.setVisible(info is not None)
        self.set_state(self.state, self.port)

    def set_state(self, state: str, port: int | None = None) -> None:
        self.state = state
        if port is not None or state in ("unchecked", "off", "self"):
            self.port = port
        self.hint.hide()
        self.check_btn.setVisible(state in ("unchecked", "off", "unpaired"))
        self.pair_btn.setVisible(state == "unpaired")
        self.check_btn.setText("Check again" if state == "off" else "Check")
        self.connect_btn.setVisible(state in ("on", "connecting"))
        self.connect_btn.setEnabled(state == "on")
        self.connect_btn.setText("Connecting…" if state == "connecting" else "Connect")
        self.mirror_btn.setVisible(state == "connected")
        self.request_btn.setVisible(self.dev.phone_like and state in ("unchecked", "off"))
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
        elif state == "unpaired":
            self.badge.set("Not paired", theme.WARN)
            self.hint.setText(HINT_UNPAIRED)
            self.hint.show()
        elif state == "requesting":
            self.badge.set("Waiting for the phone…", theme.ACCENT)
        elif state == "off":
            self.badge.set("Debugging off", theme.WARN)
            self.hint.setText(HINT_OFF_HELPER if self.helper else HINT_OFF_PHONE if self.dev.phone_like else HINT_OFF_OTHER)
            self.hint.show()


class PairDialog(QDialog):
    """Pair this PC with a phone: the pairing address and 6-digit code come from the phone's pairing screen."""

    def __init__(self, adb: Adb, ip: str, name: str, address: str, parent=None):
        super().__init__(parent)
        self.adb = adb
        self.setWindowTitle(f"Pair with {name}")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        intro = QLabel(f"On <b>{name}</b> open <i>Settings › System › Developer options › Wireless debugging</i> and tap "
                       "<b>Pair device with pairing code</b>. Keep that screen open, then enter what it shows. The address "
                       "(and code) change every time that screen is opened.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)
        self.addr = QLineEdit(address or f"{ip}:")
        self.addr.setPlaceholderText(f"Pairing address, e.g. {ip}:41234")
        self.code = QLineEdit()
        self.code.setPlaceholderText("6-digit pairing code")
        self.code.setMaxLength(6)
        lay.addWidget(self.addr)
        lay.addWidget(self.code)
        self.status = QLabel("Found the pairing address automatically." if address else "")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.go = QPushButton("Pair")
        self.go.setObjectName("primary")
        self.go.clicked.connect(self._pair)
        self.code.returnPressed.connect(self._pair)
        row.addWidget(cancel)
        row.addWidget(self.go)
        lay.addLayout(row)

    def _pair(self) -> None:
        addr, code = self.addr.text().strip(), self.code.text().strip()
        if ":" not in addr or len(code) != 6 or not code.isdigit():
            self._say("Enter the pairing address (ip:port) and the 6-digit code shown on the phone.", error=True)
            return
        self.go.setEnabled(False)
        self._say("Pairing…")

        def ok(_):
            self.accept()

        def bad(msg):
            self.go.setEnabled(True)
            self._say(friendly(msg).split("\n\nDetails")[0], error=True)

        run_task(lambda: self.adb.pair(addr, code), ok, bad)

    def _say(self, text: str, error: bool = False) -> None:
        self.status.setStyleSheet(f"color: {theme.BAD if error else theme.MUTED};")
        self.status.setText(text)


class NetworkPanel(QFrame):
    connected = Signal(str)          # address that was connected with adb connect
    mirror_requested = Signal(str)   # ip of a connected phone
    share_connected = Signal(str)    # ip of a phone that just accepted a screen-share request and is now connected

    def __init__(self, adb: Adb, parent: QWidget | None = None):
        super().__init__(parent)
        self.adb = adb
        self.setObjectName("card")
        self.rows: dict[str, NetRow] = {}
        self._mdns: dict[str, int] = {}
        self._pairing: dict[str, int] = {}     # ip -> pairing port, while the phone's pairing screen is open
        self._connected: set[str] = set()
        self._memory: dict[str, tuple[str, int | None]] = {}   # ip -> ("off"|"on", port) from earlier checks
        self._auto_tried: set[str] = set()
        self._connecting = False
        self._share_after: set[str] = set()   # phones we sent a screen-share request to: connect + mirror when ready
        self._retry: set[str] = set()      # phones we just asked to enable: look again once if the port is not open yet
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
    def set_adb_state(self, connected_ips: set[str], mdns: dict[str, int], pairing: dict[str, int] | None = None) -> None:
        self._connected, self._mdns = set(connected_ips), dict(mdns)
        self._pairing = dict(pairing or {})
        for ip, row in self.rows.items():
            if row.dev.is_this_pc or row.state in ("checking", "connecting"):
                continue
            if ip in self._connected:
                row.set_state("connected")
            elif row.state == "connected":  # was connected, now gone
                row.set_state("on", self._mdns[ip]) if ip in self._mdns else row.set_state("unchecked")
            elif ip in self._mdns and row.state in ("unchecked", "off", "unpaired"):
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
            row.request_clicked.connect(self.request_enable)
            row.pair_clicked.connect(self.pair_ip)
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

    def _on_result(self, ip: str, found: list, info=None) -> None:
        row = self.rows.get(ip)
        if row:
            row.set_helper(info)
        if row and row.state != "checking":
            return
        if row:
            if not found and ip in self._retry:       # adbd needs a few seconds to open the port after being enabled
                self._retry.discard(ip)
                QTimer.singleShot(3000, lambda: self.check_one(ip))
                return
            self._retry.discard(ip)
            if found:
                row.set_state("on", found[0][0])
                self._memory[ip] = ("on", found[0][0])
                self._set_status(f"Wireless debugging is ON at {ip}:{found[0][0]}.", good=True)
                if ip in self._share_after:
                    self.connect_ip(ip)                 # the owner accepted a screen-share request: go straight on
                else:
                    self._maybe_auto_connect()
            else:
                if ip in self._share_after:
                    self._share_after.discard(ip)
                    self._set_status("Accepted, but Mirror Shark could not find the phone yet. Press Check again, then Connect.",
                                     error=True)
                row.set_state("off")
                self._memory[ip] = ("off", None)
                self._set_status(f"No wireless debugging found at {ip}.")
        if self._probe and self._probe.idle:
            self.bar.setRange(0, 1)
            self.bar.setValue(1)
            self.stop_btn.setEnabled(False)

    # -- asking a phone to share its screen -------------------------------------------------------------------
    def request_enable(self, ip: str) -> None:
        """Send a screen-share request: on Accept the phone turns on Wireless debugging, then we connect and mirror."""
        row = self.rows.get(ip)
        if not row or row.state == "requesting":
            return
        if row.helper is not None:
            self._send_request(ip)
            return
        row.request_btn.setEnabled(False)
        self._set_status(f"Looking for Mirror Shark Helper on {row.dev.title}…")

        def probed(info) -> None:
            row.request_btn.setEnabled(True)
            if info is not None:
                row.set_helper(info)
                self._send_request(ip)
                return
            self._set_status("Mirror Shark Helper is not on this phone yet.", error=True)
            QMessageBox.information(
                self, "Mirror Shark Helper needed",
                f"{row.dev.title} does not have Mirror Shark Helper yet, so it cannot receive a screen-share request.\n\n"
                "One-time setup:\n"
                "1. Connect the phone once: USB cable with USB debugging on, or Wireless debugging turned on by hand.\n"
                "2. In Your phones, open More on the phone's card and choose Set up phone helper.\n\n"
                "After that, Request screen share works from here whenever Wireless debugging is off.")

        run_task(lambda: helper_mod.probe(ip, timeout=1.5), probed)

    def _send_request(self, ip: str) -> None:
        row = self.rows.get(ip)
        if not row:
            return
        row.set_state("requesting")
        self._share_after.add(ip)
        name = row.dev.title
        self._set_status(f"Screen-share request sent to {name}. Ask its owner to tap Accept on the phone (waiting up to "
                         f"{int(helper_mod.REQUEST_WAIT)} seconds)…")
        self.bar.setRange(0, 0)

        def done(status: str) -> None:
            self.bar.setRange(0, 1)
            self.bar.setValue(1 if status == "enabled" else 0)
            text = helper_mod.STATUS_TEXT.get(status, status)
            if status == "enabled":
                self._set_status("Accepted. Turning on and connecting… (If the phone asks “Allow wireless debugging on this "
                                 "network?”, tap Allow.)", good=True)
                self._retry.add(ip)
                QTimer.singleShot(2500, lambda: (row.set_state("unchecked"), self.check_one(ip)))
            else:
                self._share_after.discard(ip)
                row.set_state("off")
                self._set_status(text, error=status in ("unreachable", "failed", "needs_manual"))

        def failed(msg: str) -> None:
            self._share_after.discard(ip)
            row.set_state("off")
            self.bar.setRange(0, 1)
            self._set_status(f"Request failed: {msg}", error=True)

        run_task(lambda: helper_mod.request_enable(ip), done, failed)

    # -- pairing ---------------------------------------------------------------------------------------------
    def pair_ip(self, ip: str) -> None:
        row = self.rows.get(ip)
        if not row:
            return
        port = self._pairing.get(ip)
        dlg = PairDialog(self.adb, ip, row.dev.title, f"{ip}:{port}" if port else "", self)
        if dlg.exec() == QDialog.Accepted:
            self._set_status("Paired. Connecting…", good=True)
            if row.port:
                row.set_state("on", row.port)
                self.connect_ip(ip)
            else:
                self.check_one(ip)

    def probe_helper(self, ip: str) -> None:
        """Look for the helper app on one device (used after installing it on a connected phone)."""
        row = self.rows.get(ip)
        if row:
            run_task(lambda: helper_mod.probe(ip, timeout=2.0), row.set_helper)

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
            if ip in self._share_after:
                self._share_after.discard(ip)
                self.share_connected.emit(ip)

        def bad(msg):
            self._connecting = False
            self._share_after.discard(ip)
            low = msg.lower()
            unpaired = ("authenticate" in low or "unauthorized" in low
                        or ("failed to connect to" in low and "cannot connect" not in low))
            row.set_state("unpaired" if unpaired else "on", port)
            self._set_status(friendly(msg).split("\n\nDetails")[0], error=True)

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
