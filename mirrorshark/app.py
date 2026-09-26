"""Entry point: python -m mirrorshark.app"""
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_ID, APP_NAME
from .adb import Adb
from .log import data_dir, get_logger, setup_logging
from .theme import apply_theme


def selftest() -> int:
    """Headless check used to verify a packaged build: connect, decode one frame, write the result to a file."""
    import time

    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    from .server import ServerOptions, ServerSession
    from .video import VideoThread

    report = data_dir() / "selftest.txt"
    app = QCoreApplication(sys.argv)
    lines: list[str] = []
    code = 1
    session = None
    try:
        adb = Adb()
        devices = [d for d in adb.devices() if d.state == "device"]
        lines.append(f"adb: {adb.exe}")
        lines.append(f"devices: {[d.serial for d in devices]}")
        if not devices:
            raise RuntimeError("no device connected")
        session = ServerSession(adb, devices[0].serial, ServerOptions(max_size=800, audio=True))
        session.start()
        lines.append(f"server started: {session.device_name} {session.codec}")
        video = VideoThread(session)
        video.start()
        t0 = time.time()
        first = QEventLoop()
        QTimer.singleShot(6000, first.quit)
        video.frame_ready.connect(first.quit)
        first.exec()
        video.frame_ready.disconnect(first.quit)
        img = video.take_frame()
        lines.append(f"decoded frames: {video.frames_decoded} after {time.time() - t0:.1f}s")
        if img is None:
            raise RuntimeError("no frame decoded")
        lines.append(f"frame size: {img.width()}x{img.height()}")
        if session.audio is None:
            lines.append("audio: not available on this phone (optional)")
        else:
            from .audio import AudioPlayer
            player = AudioPlayer(session)
            second = QEventLoop()
            QTimer.singleShot(2500, second.quit)
            second.exec()
            available, played = player.available, player.bytes_played
            lines.append(f"audio output available: {available}, bytes played: {played}")
            player.stop()
            if not available or played == 0:
                raise RuntimeError("audio pipeline did not deliver sound")
        code = 0
    except Exception as e:  # noqa: BLE001
        lines.append(f"ERROR: {e}")
    finally:
        if session:
            session.stop()
    lines.append("RESULT: " + ("PASS" if code == 0 else "FAIL"))
    report.write_text("\n".join(lines), encoding="utf-8")
    return code


def scantest() -> int:
    """Headless check of the network scanner: writes what it found to %LOCALAPPDATA%\\MirrorShark\\scantest.txt."""
    import threading
    import time

    from PySide6.QtCore import QCoreApplication

    from .scanner import scan_network

    app = QCoreApplication(sys.argv)  # noqa: F841 - Qt needs an application object
    lines: list[str] = []
    t0 = time.time()
    try:
        found = scan_network(threading.Event(), on_status=lines.append)
        lines.append(f"found: {[(f.address, f.kind) for f in found]} in {time.time() - t0:.1f}s")
        lines.append("RESULT: " + ("PASS" if found else "NONE FOUND"))
        code = 0 if found else 1
    except Exception as e:  # noqa: BLE001
        lines.append(f"ERROR: {e}")
        lines.append("RESULT: FAIL")
        code = 1
    (data_dir() / "scantest.txt").write_text("\n".join(lines), encoding="utf-8")
    return code


def main() -> int:
    setup_logging()
    log = get_logger("app")
    if "--selftest" in sys.argv:
        return selftest()
    if "--scantest" in sys.argv:
        return scantest()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    apply_theme(app)

    lock = QLockFile(str(data_dir() / "mirrorshark.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, f"{APP_NAME} is already running.")
        return 0

    try:
        adb = Adb()
        log.info("using %s", adb.exe)
    except FileNotFoundError as e:
        log.error("adb missing: %s", e)
        QMessageBox.critical(None, APP_NAME, f"Could not find the bundled adb tool.\n\n{e}")
        return 1

    from .ui.main_window import MainWindow  # imported late so a startup error is logged and shown
    win = MainWindow(adb)
    win.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
