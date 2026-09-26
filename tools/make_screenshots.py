"""Render README screenshots of the main window using demo data (no phone needed, nothing personal)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from phonelink.adb import Adb, Device, MdnsService  # noqa: E402
from phonelink.theme import apply_theme  # noqa: E402
from phonelink.ui.main_window import MainWindow  # noqa: E402

MainWindow.refresh = lambda self: None  # never touch a real adb during screenshots
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
    QTimer.singleShot(400, lambda: (shot("empty.png"), app.quit()))


QTimer.singleShot(500, step1)
app.exec()
