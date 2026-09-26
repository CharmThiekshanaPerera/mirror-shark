"""Video thread: reads framed packets from the server, decodes them with PyAV, hands QImages to the UI."""
import struct
import threading

import av
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from . import protocol as p
from .server import ServerSession


class VideoThread(QThread):
    frame_ready = Signal()          # a new frame is available via take_frame()
    size_changed = Signal(int, int)  # device (session) size
    stopped = Signal(str)            # reason, "" for clean stop

    def __init__(self, session: ServerSession, parent=None):
        super().__init__(parent)
        self._session = session
        self._lock = threading.Lock()
        self._latest: QImage | None = None
        self._pending = False
        self.frames_decoded = 0
        self.recorder = None  # set to a recorder.Recorder to capture the raw stream

    def take_frame(self) -> QImage | None:
        with self._lock:
            self._pending = False
            return self._latest

    def run(self) -> None:
        reason = ""
        try:
            codec = av.CodecContext.create(self._session.codec or "h264", "r")
            codec.options = {"flags": "low_delay"}
            config = b""
            while True:
                hdr = p.parse_video_header(self._session.read_exact_video(12))
                if isinstance(hdr, p.SessionHeader):
                    self.size_changed.emit(hdr.width, hdr.height)
                    continue
                data = self._session.read_exact_video(hdr.size)
                rec = self.recorder
                if rec is not None:
                    rec.feed(hdr, data)
                if hdr.config:  # SPS/PPS: glue onto the next frame, like scrcpy does
                    config = data
                    continue
                if config:
                    data, config = config + data, b""
                # every scrcpy packet is one complete access unit, so skip the parser (it would hold
                # the last packet back until the next one arrives, adding a frame of latency)
                for frame in codec.decode(av.Packet(data)):
                    self._publish(frame)
        except Exception as e:  # noqa: BLE001 - surface any stream failure to the UI
            reason = str(e) or e.__class__.__name__
        self.stopped.emit(reason)

    def _publish(self, frame: "av.VideoFrame") -> None:
        arr = np.ascontiguousarray(frame.to_ndarray(format="rgb24"))
        h, w, _ = arr.shape
        img = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        with self._lock:
            self._latest = img
            notify = not self._pending
            self._pending = True
        self.frames_decoded += 1
        if notify:
            self.frame_ready.emit()
