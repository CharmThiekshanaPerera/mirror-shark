"""Main window: find/pair/connect phones and start mirroring."""
import os

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QMenu, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .. import APP_ID, APP_NAME, __version__, theme
from ..adb import Adb
from ..errors import friendly
from ..log import get_logger, log_file
from ..server import ServerOptions, ServerSession
from .help_dialog import HelpDialog
from .mirror_view import MirrorWindow
from .scan_dialog import ScanDialog
from .tasks import run_task
from .widgets import Collapsible, DeviceRow

log = get_logger("main")

PRESETS = [
    # label, max_size, Mbps, fps
    ("Balanced (recommended)", 1280, 8, 60),
    ("Sharp", 1920, 16, 60),
    ("Smooth / low latency", 1024, 6, 60),
    ("Data saver", 800, 3, 30),
    ("Custom…", None, None, None),
]


def card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(8)
    return f, lay


class MainWindow(QWidget):
    def __init__(self, adb: Adb):
        super().__init__()
        self.adb = adb
        self.settings = QSettings(APP_ID, APP_ID)
        self._mirrors: dict[str, MirrorWindow] = {}
        self._names: dict[str, str] = {}
        self._versions: dict[str, str] = {}
        self._info: dict[str, dict] = {}
        self._auto_tried = False
        self._starting: set[str] = set()
        self._refreshing = False
        self._last_devices = None
        self.setWindowTitle(f"{APP_NAME}")
        self.resize(660, 780)
        self.setMinimumSize(560, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 12)
        root.setSpacing(12)
        root.addLayout(self._build_header())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 8, 0)
        self.body_layout.setSpacing(14)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self.body_layout.addWidget(self._build_devices())
        self.connect_section = Collapsible("Connect a new phone", self._build_connect(), expanded=False)
        self.body_layout.addWidget(self.connect_section)
        self.body_layout.addWidget(Collapsible("Settings", self._build_settings(), expanded=False))
        self.body_layout.addStretch()

        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self._load_settings()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        QTimer.singleShot(150, self.refresh)

    # -- construction ---------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(theme.make_pixmap(96).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(APP_NAME)
        t.setObjectName("title")
        s = QLabel("Mirror and control your Android phone over Wi-Fi")
        s.setObjectName("subtitle")
        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col, 1)
        help_btn = QPushButton("Help")
        menu = QMenu(self)
        menu.addAction("User guide", self.show_guide)
        menu.addAction("Open log folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_file().parent))))
        menu.addSeparator()
        menu.addAction("About", self.show_about)
        help_btn.setMenu(menu)
        row.addWidget(help_btn)
        return row

    def _build_devices(self) -> QWidget:
        box, lay = card()
        head = QHBoxLayout()
        title = QLabel("Your phones")
        title.setObjectName("sectionTitle")
        head.addWidget(title)
        head.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        lay.addLayout(head)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        lay.addLayout(self.rows_layout)
        self.empty = QLabel(
            "<b>No phone found yet.</b><br><br>"
            "1. On the phone open <i>Settings › System › Developer options › Wireless debugging</i> and turn it on.<br>"
            "2. Make sure the phone and this PC use the same Wi-Fi (or the phone's hotspot).<br>"
            "3. First time? Open <i>Connect a new phone</i> below and pair with the code shown on the phone.")
        self.empty.setWordWrap(True)
        self.empty.setObjectName("muted")
        self.empty.setTextFormat(Qt.RichText)
        lay.addWidget(self.empty)
        self.empty_scan = QPushButton("Scan network for my phone")
        self.empty_scan.setObjectName("primary")
        self.empty_scan.clicked.connect(self.open_scan)
        lay.addWidget(self.empty_scan)
        return box

    def _build_connect(self) -> QWidget:
        box, lay = card()
        # pair
        lay.addWidget(self._label("Step 1 - Pair (first time only)", "sectionTitle"))
        lay.addWidget(self._label("On the phone: Wireless debugging › <b>Pair device with pairing code</b>. "
                                  "Enter the IP:port and 6-digit code it shows. They change each time that screen opens.",
                                  "muted"))
        self.pair_chips = QHBoxLayout()
        lay.addLayout(self.pair_chips)
        prow = QHBoxLayout()
        self.pair_addr = QLineEdit()
        self.pair_addr.setPlaceholderText("Pairing IP:port  e.g. 192.168.1.20:41234")
        self.pair_code = QLineEdit()
        self.pair_code.setPlaceholderText("6-digit code")
        self.pair_code.setMaxLength(6)
        self.pair_code.setMaximumWidth(120)
        self.pair_btn = QPushButton("Pair")
        self.pair_btn.clicked.connect(self.do_pair)
        prow.addWidget(self.pair_addr, 1)
        prow.addWidget(self.pair_code)
        prow.addWidget(self.pair_btn)
        lay.addLayout(prow)
        lay.addSpacing(6)
        # connect
        lay.addWidget(self._label("Step 2 - Connect", "sectionTitle"))
        lay.addWidget(self._label("Use the IP:port shown on the main <b>Wireless debugging</b> screen "
                                  "(a different port from pairing).", "muted"))
        self.connect_chips = QHBoxLayout()
        lay.addLayout(self.connect_chips)
        crow = QHBoxLayout()
        self.connect_addr = QLineEdit()
        self.connect_addr.setPlaceholderText("Connect IP:port  e.g. 192.168.1.20:37361")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.clicked.connect(self.do_connect)
        self.connect_addr.returnPressed.connect(self.do_connect)
        self.pair_code.returnPressed.connect(self.do_pair)
        self.scan_btn = QPushButton("Scan network")
        self.scan_btn.setToolTip("Find phones with Wireless debugging on automatically")
        self.scan_btn.clicked.connect(self.open_scan)
        crow.addWidget(self.connect_addr, 1)
        crow.addWidget(self.scan_btn)
        crow.addWidget(self.connect_btn)
        lay.addLayout(crow)
        return box

    def _build_settings(self) -> QWidget:
        box, lay = card()
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        self.preset = QComboBox()
        for label, *_ in PRESETS:
            self.preset.addItem(label)
        self.preset.currentIndexChanged.connect(self._preset_changed)
        form.addRow("Quality", self.preset)
        self.max_size = QComboBox()
        for label, v in [("Native", 0), ("1920", 1920), ("1280", 1280), ("1024", 1024), ("800", 800), ("640", 640)]:
            self.max_size.addItem(label, v)
        self.bitrate = QSpinBox()
        self.bitrate.setRange(1, 100)
        self.bitrate.setSuffix(" Mbps")
        self.fps = QSpinBox()
        self.fps.setRange(0, 120)
        self.fps.setSpecialValueText("unlimited")
        self.adv_rows = [("Max resolution", self.max_size), ("Bitrate", self.bitrate), ("Max FPS", self.fps)]
        for label, w in self.adv_rows:
            form.addRow(label, w)
        lay.addLayout(form)
        self.screen_off = QCheckBox("Turn the phone screen off while mirroring")
        self.stay_awake = QCheckBox("Keep the phone awake")
        self.on_top = QCheckBox("Keep the mirror window on top")
        self.audio = QCheckBox("Play the phone's sound on this PC (Android 11+)")
        self.audio_dup = QCheckBox("Keep the sound playing on the phone as well (Android 13+)")
        self.auto_reconnect = QCheckBox("Reconnect to the last phone when Mirror Shark starts")
        self.desktop = QCheckBox("Desktop mode - open a separate virtual desktop on the phone (Android 14+)")
        self.desktop_size = QLineEdit()
        self.desktop_size.setPlaceholderText("Width x height / dpi, e.g. 1920x1080/240")
        self.desktop_size.setEnabled(False)
        self.desktop.toggled.connect(self.desktop_size.setEnabled)
        for w in (self.audio, self.audio_dup, self.screen_off, self.stay_awake, self.on_top, self.auto_reconnect,
                  self.desktop, self.desktop_size):
            lay.addWidget(w)
        return box

    @staticmethod
    def _label(text: str, name: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName(name)
        l.setWordWrap(True)
        l.setTextFormat(Qt.RichText)
        return l

    # -- settings ---------------------------------------------------------------------
    def _load_settings(self) -> None:
        s = self.settings
        self.preset.setCurrentIndex(int(s.value("preset", 0)))
        self.max_size.setCurrentIndex(max(0, self.max_size.findData(int(s.value("max_size", 1280)))))
        self.bitrate.setValue(int(s.value("bitrate", 8)))
        self.fps.setValue(int(s.value("fps", 60)))
        self.screen_off.setChecked(s.value("screen_off", "false") == "true")
        self.stay_awake.setChecked(s.value("stay_awake", "false") == "true")
        self.on_top.setChecked(s.value("on_top", "false") == "true")
        self.audio.setChecked(s.value("audio", "true") == "true")
        self.audio_dup.setChecked(s.value("audio_dup", "false") == "true")
        self.auto_reconnect.setChecked(s.value("auto_reconnect", "true") == "true")
        self.desktop_size.setText(s.value("desktop_size", "1920x1080/240"))
        self.connect_addr.setText(s.value("connect_addr", ""))
        self._preset_changed()

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("preset", self.preset.currentIndex())
        s.setValue("max_size", self.max_size.currentData())
        s.setValue("bitrate", self.bitrate.value())
        s.setValue("fps", self.fps.value())
        for k, w in (("screen_off", self.screen_off), ("stay_awake", self.stay_awake), ("on_top", self.on_top),
                     ("audio", self.audio), ("audio_dup", self.audio_dup), ("auto_reconnect", self.auto_reconnect)):
            s.setValue(k, "true" if w.isChecked() else "false")
        s.setValue("desktop_size", self.desktop_size.text())
        s.setValue("connect_addr", self.connect_addr.text())

    def _preset_changed(self) -> None:
        _, size, mbps, fps = PRESETS[self.preset.currentIndex()]
        custom = size is None
        if not custom:
            self.max_size.setCurrentIndex(max(0, self.max_size.findData(size)))
            self.bitrate.setValue(mbps)
            self.fps.setValue(fps)
        for _, w in self.adv_rows:
            w.setEnabled(custom)

    def _options(self) -> ServerOptions:
        return ServerOptions(
            max_size=self.max_size.currentData(),
            video_bit_rate=self.bitrate.value() * 1_000_000,
            max_fps=self.fps.value(),
            stay_awake=self.stay_awake.isChecked(),
            audio=self.audio.isChecked(),
            audio_dup=self.audio_dup.isChecked(),
            new_display=self.desktop_size.text().strip() if self.desktop.isChecked() else "",
        )

    # -- helpers -----------------------------------------------------------------------
    def say(self, msg: str, error: bool = False) -> None:
        self.status.setStyleSheet(f"color: {theme.BAD if error else theme.MUTED};")
        self.status.setText(msg)
        (log.warning if error else log.info)(msg.replace("\n", " "))

    def fail(self, msg: str, title: str = "Something went wrong") -> None:
        text = friendly(msg)
        self.say(text.split("\n\nDetails")[0], error=True)
        QMessageBox.warning(self, APP_NAME, text)

    def show_guide(self) -> None:
        HelpDialog(self).exec()

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"<b>{APP_NAME} {__version__}</b><br>Wireless Android screen mirroring and control.<br><br>"
                          "Uses the scrcpy server (Apache-2.0) and Android platform-tools (adb).")

    # -- device list ---------------------------------------------------------------------
    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True

        def work():
            devices = self.adb.devices()
            services = self.adb.mdns_services()
            for d in devices:
                if d.state == "device":
                    if d.serial not in self._names:
                        self._names[d.serial] = self.adb.model_name(d.serial)
                        self._versions[d.serial] = self.adb.android_version(d.serial)
                    self._info[d.serial] = self.adb.device_info(d.serial)
            return devices, services

        def done(result):
            self._refreshing = False
            self._show_devices(*result)

        def failed(msg):
            self._refreshing = False
            self.say(friendly(msg).split("\n\nDetails")[0], error=True)

        run_task(work, done, failed)

    def _show_devices(self, devices, services) -> None:
        addr_by_name = {s.name: s.address for s in services if s.kind == "connect"}
        key = ([(d.serial, d.state) for d in devices], [(s.name, s.kind, s.address) for s in services],
               set(self._starting), sorted((k, v.get("battery"), v.get("charging")) for k, v in self._info.items()))
        if key == self._last_devices:
            return
        self._last_devices = key

        while self.rows_layout.count():
            w = self.rows_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        seen = set()
        for d in devices:
            base = d.serial.split("._adb")[0]
            addr = addr_by_name.get(base)
            ident = addr or d.serial
            if ident in seen:
                continue
            seen.add(ident)
            name = self._names.get(d.serial, d.serial)
            how = "Wi-Fi" if (addr or ":" in d.serial or d.serial.startswith("adb-")) else ("USB" if not d.serial.startswith("emulator") else "Emulator")
            extra = []
            if self._versions.get(d.serial):
                extra.append(f"Android {self._versions[d.serial]}")
            batt = self._info.get(d.serial, {}).get("battery")
            if batt is not None:
                extra.append(f"🔋 {batt}%" + (" ⚡" if self._info[d.serial].get("charging") else ""))
            sub = " · ".join([f"{how} · {addr or d.serial}"] + extra)
            row = DeviceRow(d.serial, name, sub, "connecting" if d.serial in self._starting else d.state)
            row.mirror_clicked.connect(self.start_mirroring)
            row.action_requested.connect(self.device_action)
            if d.serial in self._starting:
                row.mirror_btn.setEnabled(False)
            self.rows_layout.addWidget(row)
        self.empty.setVisible(not devices)
        self.empty_scan.setVisible(not devices)
        if not devices:
            self.connect_section.set_expanded(True)
            self._try_auto_reconnect()

        self._fill_chips(self.connect_chips, [s for s in services if s.kind == "connect"], self.connect_addr)
        self._fill_chips(self.pair_chips, [s for s in services if s.kind == "pairing"], self.pair_addr)
        pairing = [s for s in services if s.kind == "pairing"]
        if pairing and not self.pair_addr.text():
            self.pair_addr.setText(pairing[0].address)
            self.connect_section.set_expanded(True)
        n = sum(1 for d in devices if d.state == "device")
        self.say(f"{n} phone{'s' if n != 1 else ''} ready." if n else "Waiting for a phone…")

    def _fill_chips(self, layout: QHBoxLayout, services, target: QLineEdit) -> None:
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        for s in services:
            chip = QPushButton(f"Found on network: {s.address}")
            chip.setObjectName("chip")
            chip.clicked.connect(lambda _=False, a=s.address: target.setText(a))
            layout.addWidget(chip)
        layout.addStretch()

    # -- actions ---------------------------------------------------------------------------
    def do_connect(self) -> None:
        addr = self.connect_addr.text().strip()
        if not addr:
            self.say("Enter the IP:port from the Wireless debugging screen.", error=True)
            return
        self._save_settings()
        self.connect_btn.setEnabled(False)
        self.say(f"Connecting to {addr}…")

        def ok(r):
            self.connect_btn.setEnabled(True)
            self.say(r)
            self._last_devices = None
            self.refresh()

        def bad(m):
            self.connect_btn.setEnabled(True)
            self.fail(m)

        run_task(lambda: self.adb.connect(addr), ok, bad)

    def do_pair(self) -> None:
        addr, code = self.pair_addr.text().strip(), self.pair_code.text().strip()
        if not addr or len(code) != 6 or not code.isdigit():
            self.say("Enter the pairing IP:port and the 6-digit code shown on the phone.", error=True)
            return
        self.pair_btn.setEnabled(False)
        self.say(f"Pairing with {addr}…")

        def ok(r):
            self.pair_btn.setEnabled(True)
            self.pair_code.clear()
            self.say("Paired successfully. Now use Step 2 to connect.")
            QMessageBox.information(self, APP_NAME, "Paired successfully!\n\nNow connect using the IP:port from the "
                                    "main Wireless debugging screen (Step 2).")

        def bad(m):
            self.pair_btn.setEnabled(True)
            self.fail(m)

        run_task(lambda: self.adb.pair(addr, code), ok, bad)

    def open_scan(self) -> None:
        dlg = ScanDialog(self.adb, self)

        def connected(address: str) -> None:
            self.connect_addr.setText(address)
            self._save_settings()
            self.say(f"Connected to {address}")
            self._last_devices = None
            self.refresh()

        dlg.connected.connect(connected)
        dlg.exec()

    def _try_auto_reconnect(self) -> None:
        """Once per launch, quietly try the last address that worked (phone may still have Wireless debugging on)."""
        addr = self.connect_addr.text().strip()
        if self._auto_tried or not addr or not self.auto_reconnect.isChecked():
            return
        self._auto_tried = True
        self.say(f"Trying to reconnect to {addr}…")

        def done(_):
            self._last_devices = None
            self.refresh()

        run_task(lambda: self.adb.connect(addr), done,
                 lambda m: self.say("Last phone not reachable. Use Connect a new phone."))

    def device_action(self, serial: str, action: str) -> None:
        if action == "disconnect":
            self.do_disconnect(serial)
        elif action == "send":
            files, _ = QFileDialog.getOpenFileNames(self, "Choose files to send to the phone")
            self._transfer(serial, files, install=False)
        elif action == "install":
            files, _ = QFileDialog.getOpenFileNames(self, "Choose APK files to install", "", "Android packages (*.apk)")
            self._transfer(serial, files, install=True)

    def _transfer(self, serial: str, files: list[str], install: bool) -> None:
        for f in files:
            name = os.path.basename(f)
            self.say(f"{'Installing' if install else 'Sending'} {name}…")
            fn = (lambda f=f: self.adb.install(serial, f)) if install else (lambda f=f: self.adb.push_file(serial, f))
            done = f"Installed {name}" if install else f"Sent {name} to the phone's Download folder"
            run_task(fn, lambda _, d=done: self.say(d), lambda m, n=name: self.fail(f"{n}: {m}"))

    def do_disconnect(self, serial: str) -> None:
        win = self._mirrors.pop(serial, None)
        if win:
            win.close()
        addr = serial if ":" in serial else None
        run_task(lambda: self.adb.disconnect(addr or serial), lambda _: (setattr(self, "_last_devices", None), self.refresh()),
                 lambda m: self.say(friendly(m), error=True))

    def start_mirroring(self, serial: str) -> None:
        existing = self._mirrors.get(serial)
        if existing:
            existing.showNormal()
            existing.raise_()
            existing.activateWindow()
            return
        if serial in self._starting:
            return
        self._save_settings()
        opts = self._options()
        name = self._names.get(serial, serial)
        self._starting.add(serial)
        self._last_devices = None
        self.say(f"Starting mirroring on {name}…")
        self.refresh()

        def make_session():
            return ServerSession(self.adb, serial, opts)

        session = make_session()

        def opened(_):
            self._starting.discard(serial)
            win = MirrorWindow(session, self.adb, make_session, always_on_top=self.on_top.isChecked(),
                               turn_screen_off=self.screen_off.isChecked())
            self._mirrors[serial] = win
            win.closed.connect(lambda s=serial: self._mirrors.pop(s, None))
            win.show()
            self._last_devices = None
            self.say(f"Mirroring {session.device_name}. Tip: press the ? button in the mirror window for shortcuts.")
            self.refresh()

        def failed(msg):
            self._starting.discard(serial)
            self._last_devices = None
            self.refresh()
            self.fail(msg)

        run_task(session.start, opened, failed)

    def closeEvent(self, e) -> None:
        self._save_settings()
        for w in list(self._mirrors.values()):
            w.close()
        super().closeEvent(e)
