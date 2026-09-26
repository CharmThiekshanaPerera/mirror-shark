"""Deploys and talks to the scrcpy server running on the phone."""
import random
import socket
import threading
import time
from dataclasses import dataclass, field

from . import protocol
from .adb import Adb, AdbError, find_tool

REMOTE_JAR = "/data/local/tmp/scrcpy-server.jar"


@dataclass
class ServerOptions:
    max_size: int = 0            # 0 = device native
    video_bit_rate: int = 8_000_000
    max_fps: int = 0             # 0 = unlimited
    video_codec: str = "h264"
    control: bool = True
    stay_awake: bool = False
    turn_screen_off: bool = False
    power_off_on_close: bool = False
    new_display: str = ""        # e.g. "1920x1080/240" -> desktop-style virtual display; "" = mirror main display
    show_touches: bool = False
    audio: bool = False          # forward phone audio (Android 11+) as raw PCM
    audio_dup: bool = False      # keep playing on the phone too (Android 13+)

    def to_args(self) -> list[str]:
        a = [
            "log_level=info",
            "tunnel_forward=true",
            f"audio={'true' if self.audio else 'false'}",
            "audio_codec=raw",
            f"audio_dup={'true' if self.audio_dup else 'false'}",
            f"control={'true' if self.control else 'false'}",
            f"video_codec={self.video_codec}",
            f"video_bit_rate={self.video_bit_rate}",
            "send_frame_meta=true",
            "send_dummy_byte=true",
            "send_device_meta=true",
            f"stay_awake={'true' if self.stay_awake else 'false'}",
            f"power_off_on_close={'true' if self.power_off_on_close else 'false'}",
            f"show_touches={'true' if self.show_touches else 'false'}",
        ]
        if self.max_size:
            a.append(f"max_size={self.max_size}")
        if self.max_fps:
            a.append(f"max_fps={self.max_fps}")
        if self.new_display:
            a.append(f"new_display={self.new_display}")
        return a


class ServerError(RuntimeError):
    pass


class ServerSession:
    """One running server: video socket, control socket, device info."""

    def __init__(self, adb: Adb, serial: str, options: ServerOptions):
        self.adb = adb
        self.serial = serial
        self.options = options
        self.video: socket.socket | None = None
        self.audio: socket.socket | None = None
        self.control: socket.socket | None = None
        self.device_name = ""
        self.codec = ""
        self._proc = None
        self._port = 0
        self._log: list[str] = []
        self._log_lock = threading.Lock()

    # -- lifecycle -----------------------------------------------------------
    def start(self, connect_timeout: float = 15.0) -> None:
        scid = "%08x" % random.getrandbits(31)
        jar = find_tool("scrcpy-server")
        self.adb.push(self.serial, str(jar), REMOTE_JAR)
        self._port = self.adb.forward_abstract(self.serial, f"scrcpy_{scid}")
        cmd = (f"CLASSPATH={REMOTE_JAR} app_process / com.genymobile.scrcpy.Server "
               f"{protocol.SERVER_VERSION} scid={scid} " + " ".join(self.options.to_args()))
        self._proc = self.adb.popen("shell", cmd, serial=self.serial)
        threading.Thread(target=self._drain_log, daemon=True).start()
        try:
            self.video = self._connect_first(connect_timeout)
            if self.options.audio:
                self.audio = socket.create_connection(("127.0.0.1", self._port), timeout=5)
            if self.options.control:
                self.control = socket.create_connection(("127.0.0.1", self._port), timeout=5)
                self.control.settimeout(None)
            self.video.settimeout(10)
            self.device_name = protocol.parse_device_name(self._read_exact(self.video, 64))
            self.codec = self._read_exact(self.video, 4).decode("ascii", "replace")
            self.video.settimeout(None)
            if self.audio is not None:
                self.audio.settimeout(10)
                codec_id = self._read_exact(self.audio, 4)
                self.audio.settimeout(None)
                if codec_id != b"\x00raw":  # 0 = disabled by the device, 1 = capture error (e.g. Android < 11)
                    self.audio.close()
                    self.audio = None
        except Exception:
            self.stop()
            raise

    def _connect_first(self, timeout: float) -> socket.socket:
        """adb accepts the local TCP connection before the server listens, so retry until the dummy byte arrives."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise ServerError("scrcpy server exited early:\n" + self.log_text())
            s = socket.create_connection(("127.0.0.1", self._port), timeout=5)
            s.settimeout(2)
            try:
                if s.recv(1):
                    return s
            except (socket.timeout, OSError):
                pass
            s.close()
            time.sleep(0.2)
        raise ServerError("timed out waiting for the scrcpy server.\n" + self.log_text())

    @staticmethod
    def _read_exact(sock: socket.socket, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ServerError("connection closed by device")
            buf += chunk
        return bytes(buf)

    def read_exact_video(self, n: int) -> bytes:
        return self._read_exact(self.video, n)

    def read_exact_audio(self, n: int) -> bytes:
        return self._read_exact(self.audio, n)

    def stop(self) -> None:
        for s in (self.video, self.audio, self.control):
            if s is not None:
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                s.close()
        self.video = self.audio = self.control = None
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        if self._port:
            self.adb.forward_remove(self.serial, self._port)
            self._port = 0
        # make sure no orphan server keeps running on the phone
        try:
            self.adb.shell(self.serial, "pkill -f com.genymobile.scrcpy.Server", timeout=5)
        except AdbError:
            pass

    # -- logging ---------------------------------------------------------------
    def _drain_log(self) -> None:
        for raw in iter(self._proc.stdout.readline, b""):
            with self._log_lock:
                self._log.append(raw.decode("utf-8", "replace").rstrip())
                del self._log[:-200]

    def log_text(self) -> str:
        with self._log_lock:
            return "\n".join(self._log)

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
