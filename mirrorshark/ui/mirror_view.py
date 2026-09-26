"""Window that shows the phone screen and forwards mouse/keyboard input to it."""
import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from .. import protocol as p
from .. import theme
from ..adb import Adb
from ..audio import AudioPlayer
from ..control import ControlClient
from ..errors import friendly
from ..log import get_logger
from ..recorder import Recorder
from ..server import ServerSession
from ..video import VideoThread
from .tasks import keep_alive, run_task
from .widgets import Toast

log = get_logger("mirror")

SPECIAL_KEYS = {
    Qt.Key_Return: p.KEYCODE_ENTER, Qt.Key_Enter: p.KEYCODE_ENTER,
    Qt.Key_Backspace: p.KEYCODE_DEL, Qt.Key_Delete: p.KEYCODE_FORWARD_DEL,
    Qt.Key_Tab: p.KEYCODE_TAB, Qt.Key_Escape: p.KEYCODE_BACK,
    Qt.Key_Up: p.KEYCODE_DPAD_UP, Qt.Key_Down: p.KEYCODE_DPAD_DOWN,
    Qt.Key_Left: p.KEYCODE_DPAD_LEFT, Qt.Key_Right: p.KEYCODE_DPAD_RIGHT,
    Qt.Key_PageUp: p.KEYCODE_PAGE_UP, Qt.Key_PageDown: p.KEYCODE_PAGE_DOWN,
    Qt.Key_Home: p.KEYCODE_MOVE_HOME, Qt.Key_End: p.KEYCODE_MOVE_END,
}

SHORTCUTS_HELP = """<table cellpadding="4">
<tr><td><b>Left-click / drag</b></td><td>Tap / swipe</td></tr>
<tr><td><b>Right-click</b></td><td>Back</td></tr>
<tr><td><b>Middle-click</b></td><td>Home</td></tr>
<tr><td><b>Mouse wheel</b></td><td>Scroll</td></tr>
<tr><td><b>Keyboard</b></td><td>Types into the phone (Esc = Back)</td></tr>
<tr><td><b>Ctrl+H / B / S</b></td><td>Home / Back / Recent apps</td></tr>
<tr><td><b>Ctrl+P</b></td><td>Power button</td></tr>
<tr><td><b>Ctrl+O</b></td><td>Turn phone screen off / on</td></tr>
<tr><td><b>Ctrl+N</b></td><td>Open notifications</td></tr>
<tr><td><b>Ctrl+R</b></td><td>Rotate</td></tr>
<tr><td><b>Ctrl+V</b></td><td>Paste PC clipboard into the phone</td></tr>
<tr><td><b>Ctrl+Shift+S</b></td><td>Save a screenshot</td></tr>
<tr><td><b>Ctrl+Shift+R</b></td><td>Start / stop screen recording (MP4)</td></tr>
<tr><td><b>Ctrl+M</b></td><td>Mute / unmute phone sound on the PC</td></tr>
<tr><td><b>F11</b></td><td>Full screen</td></tr>
<tr><td><b>Drop files</b></td><td>.apk = install, other files = send to phone's Download folder</td></tr>
</table>"""


class VideoWidget(QWidget):
    """Paints the latest frame letterboxed, and maps mouse events to device coordinates."""
    reconnect_requested = Signal()

    def __init__(self, control: ControlClient, parent=None):
        super().__init__(parent)
        self.control = control
        self.image: QImage | None = None
        self.device_size = (0, 0)
        self.message = "Waiting for video…"
        self._pressed = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(180, 320)
        self.reconnect_btn = QPushButton("Reconnect", self)
        self.reconnect_btn.setObjectName("primary")
        self.reconnect_btn.clicked.connect(self.reconnect_requested.emit)
        self.reconnect_btn.hide()

    def set_image(self, img: QImage) -> None:
        self.image = img
        self.message = ""
        self.reconnect_btn.hide()
        if self.device_size == (0, 0):
            self.device_size = (img.width(), img.height())
        self.update()

    def show_lost(self, message: str) -> None:
        self.message = message
        self.reconnect_btn.show()
        self._place_button()
        self.update()

    def _place_button(self) -> None:
        self.reconnect_btn.adjustSize()
        self.reconnect_btn.move((self.width() - self.reconnect_btn.width()) // 2, self.height() // 2 + 50)

    def resizeEvent(self, e) -> None:
        self._place_button()
        super().resizeEvent(e)

    def _target_rect(self) -> QRect:
        if not self.image:
            return QRect()
        iw, ih = self.image.width(), self.image.height()
        scale = min(self.width() / iw, self.height() / ih)
        w, h = int(iw * scale), int(ih * scale)
        return QRect((self.width() - w) // 2, (self.height() - h) // 2, w, h)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)
        if self.image:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawImage(self._target_rect(), self.image)
        if self.message:
            if self.image:  # dim the last frame under the message
                painter.fillRect(self.rect(), QColor(0, 0, 0, 170))
            painter.setPen(Qt.white)
            f = QFont("Segoe UI", 11)
            painter.setFont(f)
            painter.drawText(self.rect().adjusted(24, 0, -24, 0), Qt.AlignCenter | Qt.TextWordWrap, self.message)

    def _to_device(self, pos: QPoint, clamp: bool = False):
        r = self._target_rect()
        if r.isEmpty():
            return None
        if not clamp and not r.contains(pos):
            return None
        dw, dh = self.device_size
        x = min(max((pos.x() - r.x()) * dw // r.width(), 0), dw - 1)
        y = min(max((pos.y() - r.y()) * dh // r.height(), 0), dh - 1)
        return int(x), int(y)

    def mousePressEvent(self, e) -> None:
        self.setFocus()
        pt = self._to_device(e.position().toPoint())
        if pt is None:
            return
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.control.touch(p.ACTION_DOWN, *pt, *self.device_size)
        elif e.button() == Qt.RightButton:
            self.control.back()
        elif e.button() == Qt.MiddleButton:
            self.control.home()

    def mouseMoveEvent(self, e) -> None:
        if self._pressed:
            pt = self._to_device(e.position().toPoint(), clamp=True)
            if pt:
                self.control.touch(p.ACTION_MOVE, *pt, *self.device_size)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            pt = self._to_device(e.position().toPoint(), clamp=True)
            if pt:
                self.control.touch(p.ACTION_UP, *pt, *self.device_size)

    def wheelEvent(self, e) -> None:
        pt = self._to_device(e.position().toPoint())
        if pt is None:
            return
        d = e.angleDelta()
        self.control.scroll(*pt, *self.device_size, d.x() / 120.0, d.y() / 120.0)


class MirrorWindow(QWidget):
    closed = Signal()
    _clipboard_from_device = Signal(str)
    _recording_done = Signal(str, str)  # path, error

    def __init__(self, session: ServerSession, adb: Adb, session_factory, always_on_top: bool = False,
                 turn_screen_off: bool = False):
        super().__init__()
        self.session = session
        self.adb = adb
        self._factory = session_factory
        self._screen_on = True
        self._closing = False
        self._reconnecting = False
        self._sized = False
        self._last_frames = 0
        self.audio: AudioPlayer | None = None
        self.recorder: Recorder | None = None
        self.setWindowTitle(f"Mirror Shark - {session.device_name}")
        self.setAcceptDrops(True)
        if always_on_top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._clipboard_from_device.connect(self._set_local_clipboard)
        self._recording_done.connect(self._on_recording_done)
        self.control = ControlClient(session.control, on_clipboard=self._clipboard_from_device.emit)
        self.view = VideoWidget(self.control)
        self.view.reconnect_requested.connect(self.reconnect)

        # side toolbar
        bar = QVBoxLayout()
        bar.setContentsMargins(4, 6, 4, 6)
        bar.setSpacing(4)
        self._tool_buttons = {}
        for label, tip, fn in [
            ("◀", "Back  (right-click / Esc)", lambda: self.control.back()),
            ("⬤", "Home  (middle-click / Ctrl+H)", lambda: self.control.home()),
            ("▣", "Recent apps  (Ctrl+S)", lambda: self.control.recents()),
            ("⏻", "Power  (Ctrl+P)", lambda: self.control.power()),
            ("🔊", "Volume up", lambda: self.control.key(p.KEYCODE_VOLUME_UP)),
            ("🔉", "Volume down", lambda: self.control.key(p.KEYCODE_VOLUME_DOWN)),
            ("⟳", "Rotate  (Ctrl+R)", lambda: self.control.rotate_device()),
            ("🔔", "Notifications  (Ctrl+N)", lambda: self.control.expand_notifications()),
            ("☾", "Turn phone screen off/on  (Ctrl+O)", self.toggle_screen),
            ("📷", "Screenshot  (Ctrl+Shift+S)", self.screenshot),
            ("⏺", "Record screen  (Ctrl+Shift+R)", self.toggle_recording),
            ("🔈", "Mute / unmute phone sound  (Ctrl+M)", self.toggle_mute),
            ("⛶", "Full screen  (F11)", self.toggle_fullscreen),
            ("?", "Shortcuts", self.show_help),
        ]:
            b = QPushButton(label)
            b.setObjectName("tool")
            b.setToolTip(tip)
            b.setFixedSize(34, 34)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, f=fn: f())
            self._tool_buttons[label] = b
            bar.addWidget(b)
        bar.addStretch()
        self.rec_label = QLabel("")
        self.rec_label.setAlignment(Qt.AlignCenter)
        self.rec_label.setStyleSheet(f"color: {theme.BAD}; font-size: 10px; font-weight: 600;")
        bar.addWidget(self.rec_label)
        self.fps_label = QLabel("")
        self.fps_label.setObjectName("muted")
        self.fps_label.setAlignment(Qt.AlignCenter)
        self.fps_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px;")
        bar.addWidget(self.fps_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.side = QWidget()
        self.side.setLayout(bar)
        self.side.setFixedWidth(44)
        layout.addWidget(self.side)
        layout.addWidget(self.view, 1)
        self.toast = Toast(self)

        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)
        self.video: VideoThread | None = None
        self._start_video()
        if turn_screen_off:
            QTimer.singleShot(800, self.toggle_screen)

    # -- session wiring -----------------------------------------------------------
    def _start_video(self) -> None:
        self.video = VideoThread(self.session)
        keep_alive(self.video)
        self.video.frame_ready.connect(self._on_frame)
        self.video.size_changed.connect(self._on_size)
        self.video.stopped.connect(self._on_stopped)
        self._last_frames = 0
        self.video.start()
        self._start_audio()

    def _start_audio(self) -> None:
        muted = self.audio.muted if self.audio else False
        if self.session.audio is None:
            self.audio = None
            self._tool_buttons["🔈"].setEnabled(False)
            self._tool_buttons["🔈"].setToolTip("Phone sound is off or not supported (needs Android 11+)")
            return
        self.audio = AudioPlayer(self.session)
        self.audio.set_muted(muted)
        self._tool_buttons["🔈"].setEnabled(self.audio.available)

    def toggle_mute(self) -> None:
        if not self.audio:
            self.toast.show_message("Phone sound is not available (enable it in Settings; needs Android 11+)")
            return
        self.audio.set_muted(not self.audio.muted)
        self._tool_buttons["🔈"].setText("🔇" if self.audio.muted else "🔈")
        self.toast.show_message("Phone sound muted" if self.audio.muted else "Phone sound on")

    # -- recording -------------------------------------------------------------
    def toggle_recording(self) -> None:
        if self.recorder is not None:
            self._stop_recording()
            return
        if self.video is None or self.video.frames_decoded == 0:
            self.toast.show_message("Nothing to record yet")
            return
        movies = QStandardPaths.writableLocation(QStandardPaths.MoviesLocation) or str(Path.home())
        folder = Path(movies) / "MirrorShark"
        folder.mkdir(parents=True, exist_ok=True)
        self.recorder = Recorder(folder / time.strftime("phone_%Y%m%d_%H%M%S.mp4"))
        self.video.recorder = self.recorder
        self.control.reset_video()  # fresh key frame so the recording starts immediately
        self._tool_buttons["⏺"].setText("⏹")
        self._tool_buttons["⏺"].setStyleSheet(f"color: {theme.BAD};")
        self._rec_started = time.monotonic()
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._tick_recording)
        self._rec_timer.start(500)
        self._tick_recording()
        self.toast.show_message("Recording started (screen only, no sound)")

    def _tick_recording(self) -> None:
        s = int(time.monotonic() - self._rec_started)
        self.rec_label.setText(f"● REC\n{s // 60:02d}:{s % 60:02d}")

    def _stop_recording(self) -> None:
        rec, self.recorder = self.recorder, None
        if self.video:
            self.video.recorder = None
        self._rec_timer.stop()
        self.rec_label.setText("")
        self._tool_buttons["⏺"].setText("⏺")
        self._tool_buttons["⏺"].setStyleSheet("")
        if rec is not None:
            self.toast.show_message("Saving recording…", 8000)
            rec.finish(lambda path, err: self._recording_done.emit(str(path), err))

    def _on_recording_done(self, path: str, err: str) -> None:
        if err:
            self.toast.show_message(f"Recording failed: {err}", 6000)
        else:
            self.toast.show_message(f"Saved {Path(path).name} in Videos\\MirrorShark", 4500)

    def reconnect(self) -> None:
        if self._reconnecting or self._closing:
            return
        self._reconnecting = True
        self.view.reconnect_btn.hide()
        self.view.message = "Reconnecting…"
        self.view.update()
        old = self.session
        if self.recorder is not None:
            self._stop_recording()
        if self.audio:
            self.audio.stop()
        threading.Thread(target=old.stop, daemon=True).start()
        new_session = self._factory()

        def ok(_):
            self._reconnecting = False
            if self._closing:
                threading.Thread(target=new_session.stop, daemon=True).start()
                return
            self.session = new_session
            self.control = ControlClient(new_session.control, on_clipboard=self._clipboard_from_device.emit)
            self.view.control = self.control
            self.view.device_size = (0, 0)
            self.view.image = None
            self.view.message = "Waiting for video…"
            self._start_video()
            self.toast.show_message("Reconnected")

        def fail(msg):
            self._reconnecting = False
            log.warning("reconnect failed: %s", msg)
            self.view.show_lost(friendly(msg).split("\n\nDetails")[0])

        run_task(new_session.start, ok, fail)

    # -- video ---------------------------------------------------------------
    def _on_size(self, w: int, h: int) -> None:
        self.view.device_size = (w, h)

    def _on_frame(self) -> None:
        if self.video is None:
            return
        img = self.video.take_frame()
        if img is None:
            return
        self.view.set_image(img)
        if not self._sized:
            self._sized = True
            screen = QGuiApplication.primaryScreen().availableGeometry()
            scale = min(1.0, (screen.height() - 120) / img.height(), (screen.width() - 120) / img.width())
            self.resize(int(img.width() * scale) + 44, int(img.height() * scale))

    def _on_stopped(self, reason: str) -> None:
        if self._closing or self.sender() is not self.video:
            return
        log.info("video stopped: %s", reason)
        if self.recorder is not None:
            self._stop_recording()
        self.setWindowTitle(f"Mirror Shark - {self.session.device_name} (disconnected)")
        self.view.show_lost("Connection to the phone was lost.\nCheck that the phone is awake, on the same "
                            "network and Wireless debugging is on.")

    def _update_fps(self) -> None:
        if self.video is None:
            return
        n = self.video.frames_decoded
        self.fps_label.setText(f"{n - self._last_frames}\nfps")
        self._last_frames = n

    # -- actions ----------------------------------------------------------------
    def toggle_screen(self) -> None:
        self._screen_on = not self._screen_on
        self.control.set_display_power(self._screen_on)
        self.toast.show_message("Phone screen on" if self._screen_on else "Phone screen off (mirroring continues)")

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.side.show()
        else:
            self.showFullScreen()
            self.side.hide()
            self.toast.show_message("Press F11 to exit full screen")

    def screenshot(self) -> None:
        img = self.view.image
        if img is None:
            self.toast.show_message("Nothing to capture yet")
            return
        pics = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation) or str(Path.home())
        folder = Path(pics) / "MirrorShark"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / time.strftime("phone_%Y%m%d_%H%M%S.png")
        if img.save(str(path)):
            self.toast.show_message(f"Saved {path.name} to Pictures\\MirrorShark", 3200)
        else:
            self.toast.show_message("Could not save screenshot")

    def show_help(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Mirror shortcuts")
        box.setText(SHORTCUTS_HELP)
        box.exec()

    # -- input ----------------------------------------------------------------
    def keyPressEvent(self, e) -> None:
        mods = e.modifiers()
        if e.key() == Qt.Key_F11:
            self.toggle_fullscreen()
            return
        if mods & Qt.ControlModifier:
            if mods & Qt.ShiftModifier and e.key() == Qt.Key_S:
                self.screenshot()
                return
            if mods & Qt.ShiftModifier and e.key() == Qt.Key_R:
                self.toggle_recording()
                return
            shortcuts = {
                Qt.Key_H: lambda: self.control.home(), Qt.Key_B: lambda: self.control.back(),
                Qt.Key_S: lambda: self.control.recents(), Qt.Key_P: lambda: self.control.power(),
                Qt.Key_O: self.toggle_screen, Qt.Key_N: lambda: self.control.expand_notifications(),
                Qt.Key_R: lambda: self.control.rotate_device(), Qt.Key_V: self._paste,
                Qt.Key_M: self.toggle_mute,
            }
            fn = shortcuts.get(e.key())
            if fn:
                fn()
            return
        if e.key() in SPECIAL_KEYS:
            self.control.key(SPECIAL_KEYS[e.key()])
        elif e.text() and e.text().isprintable():
            self.control.text(e.text())

    def _paste(self) -> None:
        self.control.set_clipboard(QGuiApplication.clipboard().text(), paste=True)

    def focusInEvent(self, e) -> None:
        # keep the phone clipboard in sync with the PC when returning to the window
        text = QGuiApplication.clipboard().text()
        if text and self.control.enabled:
            self.control.set_clipboard(text)
        super().focusInEvent(e)

    def _set_local_clipboard(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)

    # -- drag & drop: APK install / file transfer --------------------------------
    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        serial = self.session.serial
        for f in files:
            name = os.path.basename(f)
            is_apk = f.lower().endswith(".apk")
            self.toast.show_message(f"{'Installing' if is_apk else 'Sending'} {name}…", 60000)
            fn = (lambda f=f: self.adb.install(serial, f)) if is_apk else (lambda f=f: self.adb.push_file(serial, f))
            run_task(fn,
                     lambda r, n=name, a=is_apk: self.toast.show_message(
                         f"Installed {n}" if a else f"Sent {n} to Download folder", 3500),
                     lambda m, n=name: self.toast.show_message(f"Failed: {n} - {friendly(m)[:120]}", 6000))

    # -- shutdown -------------------------------------------------------------
    def closeEvent(self, e) -> None:
        self._closing = True
        self._fps_timer.stop()
        if self.recorder is not None:
            self._stop_recording()
        if self.audio:
            self.audio.stop()
        # stopping the session runs adb (blocking); keep the UI responsive
        threading.Thread(target=self.session.stop, daemon=True).start()
        self.closed.emit()
        super().closeEvent(e)
