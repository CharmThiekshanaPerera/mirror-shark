"""Phone audio playback: reads raw PCM (48 kHz, 16-bit, stereo) from the server and plays it on the PC."""
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

from . import protocol as p
from .log import get_logger
from .server import ServerSession

log = get_logger("audio")

SAMPLE_RATE = 48000
CHANNELS = 2
BYTES_PER_FRAME = CHANNELS * 2
BUFFER_MS = 120  # small buffer keeps sound in sync with the picture


class _Reader(QThread):
    chunk = Signal(bytes)
    stopped = Signal(str)

    def __init__(self, session: ServerSession):
        super().__init__()
        self._session = session

    def run(self) -> None:
        reason = ""
        try:
            while True:
                hdr = p.parse_video_header(self._session.read_exact_audio(12))  # same 12-byte header as video
                data = self._session.read_exact_audio(hdr.size)
                if not hdr.config:
                    self.chunk.emit(data)
        except Exception as e:  # noqa: BLE001
            reason = str(e) or e.__class__.__name__
        self.stopped.emit(reason)


class AudioPlayer(QObject):
    """Create and use from the UI thread. Plays whatever the reader thread delivers."""

    def __init__(self, session: ServerSession, parent=None):
        super().__init__(parent)
        self.muted = False
        self.bytes_played = 0
        self._sink: QAudioSink | None = None
        self._io = None
        self._reader = _Reader(session)
        try:
            fmt = QAudioFormat()
            fmt.setSampleRate(SAMPLE_RATE)
            fmt.setChannelCount(CHANNELS)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                raise RuntimeError("no audio output device")
            self._sink = QAudioSink(device, fmt, self)
            self._sink.setBufferSize(SAMPLE_RATE * BYTES_PER_FRAME * BUFFER_MS // 1000)
            self._io = self._sink.start()
        except Exception as e:  # noqa: BLE001 - audio is optional; never break mirroring because of it
            log.warning("audio output unavailable: %s", e)
            self._sink = None
        self._reader.chunk.connect(self._on_chunk)
        from .ui.tasks import keep_alive
        keep_alive(self._reader)
        self._reader.start()

    @property
    def available(self) -> bool:
        return self._sink is not None

    def _on_chunk(self, data: bytes) -> None:
        if self.muted or self._io is None or self._sink is None:  # stopped, muted, or no output device
            return
        # push mode: if the device buffer is full, drop rather than let latency grow
        if self._sink.bytesFree() >= len(data):
            self.bytes_played += self._io.write(data)

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    def stop(self) -> None:
        try:
            self._reader.chunk.disconnect(self._on_chunk)
        except (TypeError, RuntimeError):
            pass
        self._io = None
        if self._sink is not None:
            sink, self._sink = self._sink, None
            sink.stop()
