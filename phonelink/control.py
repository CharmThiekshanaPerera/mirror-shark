"""Control channel: sends input events to the phone and receives device messages (clipboard)."""
import socket
import struct
import threading
from typing import Callable

from . import protocol as p


class ControlClient:
    def __init__(self, sock: socket.socket | None, on_clipboard: Callable[[str], None] | None = None):
        self._sock = sock
        self._lock = threading.Lock()
        self._on_clipboard = on_clipboard
        self._clip_seq = 0
        if sock is not None:
            threading.Thread(target=self._reader, daemon=True).start()

    @property
    def enabled(self) -> bool:
        return self._sock is not None

    def send(self, data: bytes) -> None:
        if self._sock is None:
            return
        with self._lock:
            try:
                self._sock.sendall(data)
            except OSError:
                self._sock = None

    # -- touch / mouse ---------------------------------------------------------
    def touch(self, action: int, x: int, y: int, w: int, h: int, buttons: int = p.BUTTON_PRIMARY) -> None:
        pressure = 0.0 if action == p.ACTION_UP else 1.0
        self.send(p.encode_touch(action, p.POINTER_ID_MOUSE, x, y, w, h, pressure,
                                 buttons if action != p.ACTION_MOVE else 0, buttons if action != p.ACTION_UP else 0))

    def scroll(self, x: int, y: int, w: int, h: int, hscroll: float, vscroll: float) -> None:
        self.send(p.encode_scroll(x, y, w, h, hscroll, vscroll))

    # -- keys ------------------------------------------------------------------
    def key(self, keycode: int, repeat: int = 0, meta: int = 0) -> None:
        self.send(p.encode_keycode(p.ACTION_DOWN, keycode, repeat, meta))
        self.send(p.encode_keycode(p.ACTION_UP, keycode, 0, meta))

    def text(self, text: str) -> None:
        if text:
            self.send(p.encode_text(text))

    def back(self) -> None:
        self.send(p.encode_back_or_screen_on(p.ACTION_DOWN))
        self.send(p.encode_back_or_screen_on(p.ACTION_UP))

    def home(self) -> None:
        self.key(p.KEYCODE_HOME)

    def recents(self) -> None:
        self.key(p.KEYCODE_APP_SWITCH)

    def power(self) -> None:
        self.key(p.KEYCODE_POWER)

    def set_display_power(self, on: bool) -> None:
        self.send(p.encode_set_display_power(on))

    def expand_notifications(self) -> None:
        self.send(p.encode_simple(p.TYPE_EXPAND_NOTIFICATION_PANEL))

    def rotate_device(self) -> None:
        self.send(p.encode_simple(p.TYPE_ROTATE_DEVICE))

    def reset_video(self) -> None:
        self.send(p.encode_simple(p.TYPE_RESET_VIDEO))

    # -- clipboard -------------------------------------------------------------
    def set_clipboard(self, text: str, paste: bool = False) -> None:
        self._clip_seq += 1
        self.send(p.encode_set_clipboard(self._clip_seq, text, paste))

    def get_clipboard(self) -> None:
        self.send(p.encode_get_clipboard())

    def _reader(self) -> None:
        sock = self._sock
        try:
            while sock is not None:
                t = self._read(sock, 1)[0]
                if t == p.DEVMSG_CLIPBOARD:
                    n = struct.unpack(">I", self._read(sock, 4))[0]
                    text = self._read(sock, n).decode("utf-8", "replace")
                    if self._on_clipboard:
                        self._on_clipboard(text)
                elif t == p.DEVMSG_ACK_CLIPBOARD:
                    self._read(sock, 8)
                elif t == p.DEVMSG_UHID_OUTPUT:
                    self._read(sock, 2)
                    n = struct.unpack(">H", self._read(sock, 2))[0]
                    self._read(sock, n)
                else:
                    return  # unknown message: stop parsing rather than desync
        except (OSError, EOFError):
            pass

    @staticmethod
    def _read(sock: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return bytes(buf)
