"""Render README screenshots of the main window using demo data (no phone needed, nothing personal)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mirrorshark.adb import Adb, Device, MdnsService  # noqa: E402
from mirrorshark.theme import apply_theme  # noqa: E402
from mirrorshark.ui.main_window import MainWindow  # noqa: E402
from mirrorshark.scanner import NetDevice  # noqa: E402
from mirrorshark.ui.network_panel import NetworkPanel  # noqa: E402

MainWindow.refresh = lambda self: None  # never touch a real adb during screenshots
NetworkPanel.start_discovery = lambda self: None  # ... or scan a real network
NetworkPanel._enqueue = lambda self, ip: None
app = QApplication([])
apply_theme(app)
w = MainWindow(Adb.__new__(Adb))
w.resize(660, 640)
w._names["192.168.1.20:37361"] = "Google Pixel 7 Pro"
w._versions["192.168.1.20:37361"] = "15"
w._info["192.168.1.20:37361"] = {"battery": 82, "charging": True}
w.show()
out = ROOT / "docs" / "images"
out.mkdir(parents=True, exist_ok=True)


def shot(name):
    w.grab().save(str(out / name))
    print("wrote", name)


def step1():
    w._show_devices([Device("192.168.1.20:37361", "device", "")],
                    [MdnsService("adb-DEMO-abc", "connect", "192.168.1.20:37361")])
    devices = [
        NetDevice("192.168.1.20", "c6:c3:ce:4e:10:f6", "Pixel-7-Pro", "Android phone or tablet", "\U0001F4F1", True),
        NetDevice("192.168.1.31", "ec:10:7b:d6:03:5d", "Galaxy-Tab-A8", "Android phone or tablet", "\U0001F4F1", True),
        NetDevice("192.168.1.42", "9e:5b:14:97:dd:95", "Redmi-Note-9", "Android phone or tablet", "\U0001F4F1", True),
        NetDevice("192.168.1.15", "3c:5a:b4:22:91:0e", "Living-Room-TV", "TV / streaming device", "\U0001F4FA", False),
        NetDevice("192.168.1.1", "d8:d8:66:4d:34:05", "", "Router / gateway", "\U0001F4E1", False, is_gateway=True),
        NetDevice("192.168.1.10", "", "MY-PC", "This PC", "\U0001F4BB", False, is_this_pc=True),
    ]
    w.network.set_adb_state({"192.168.1.20"}, {"192.168.1.20": 37361})
    w.network._on_devices(devices)
    from mirrorshark.helper import HelperInfo
    w.network.rows["192.168.1.31"].set_helper(HelperInfo("Samsung Galaxy Tab A8", False, True, 1))
    w.network.rows["192.168.1.31"].set_state("off")
    w.network.rows["192.168.1.42"].set_state("off")
    w.network._set_status("5 devices on your Wi-Fi.")
    w.resize(660, 1080)
    QTimer.singleShot(300, lambda: (shot("main.png"), step2()))


def step2():
    w.connect_section.set_expanded(True)
    w.body_layout.itemAt(2).widget().set_expanded(True)
    w.resize(660, 900)
    QTimer.singleShot(400, lambda: (shot("settings.png"), step3()))


def step3():
    w.connect_section.set_expanded(False)
    w.body_layout.itemAt(2).widget().set_expanded(False)
    w.resize(660, 640)
    w._last_devices = None
    w._show_devices([], [])
    QTimer.singleShot(400, lambda: (shot("empty.png"), w.close(), app.quit()))


QTimer.singleShot(500, step1)
app.exec()
