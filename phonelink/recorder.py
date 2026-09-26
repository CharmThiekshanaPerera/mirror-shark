"""Screen recorder: stores the phone's H.264 stream unchanged (no re-encoding) and remuxes it to MP4."""
import os
import threading
import time
from fractions import Fraction
from pathlib import Path

import av

from . import protocol as p
from .log import get_logger

log = get_logger("recorder")


class Recorder:
    """Feed every video packet via feed(). Starts on the first key frame after a config packet."""

    def __init__(self, mp4_path: Path):
        self.mp4_path = Path(mp4_path)
        self.raw_path = self.mp4_path.with_suffix(".h264.part")
        self._raw = open(self.raw_path, "wb")
        self._config = b""
        self._pts: list[int] = []
        self._started = False
        self.frames = 0
        self.started_at = time.monotonic()

    @property
    def started(self) -> bool:
        return self._started

    def feed(self, hdr: p.PacketHeader, data: bytes) -> None:
        if hdr.config:
            self._config = data
            return
        if not self._started:
            if not hdr.key_frame:
                return  # wait for a clean starting point
            self._started = True
            self._raw.write(self._config)
        self._raw.write(data)
        self._pts.append(hdr.pts)
        self.frames += 1

    def finish(self, on_done=None) -> None:
        """Close the raw dump and remux it to MP4 in the background."""
        self._raw.close()
        threading.Thread(target=self._remux, args=(on_done,), daemon=True).start()

    def _remux(self, on_done) -> None:
        err = ""
        try:
            if self.frames == 0:
                raise RuntimeError("nothing was recorded")
            inp = av.open(str(self.raw_path), format="h264")
            istream = inp.streams.video[0]
            out = av.open(str(self.mp4_path), "w")
            ostream = out.add_stream_from_template(istream)
            base = self._pts[0]
            tb = Fraction(1, 1_000_000)
            last = -1
            i = 0
            for pkt in inp.demux(istream):
                if pkt.size == 0 or i >= len(self._pts):
                    continue
                ts = max(self._pts[i] - base, last + 1)
                last = ts
                i += 1
                pkt.stream = ostream
                pkt.time_base = tb
                pkt.pts = pkt.dts = ts
                out.mux(pkt)
            out.close()
            inp.close()
            log.info("recording saved: %s (%d frames)", self.mp4_path, i)
        except Exception as e:  # noqa: BLE001
            err = str(e) or e.__class__.__name__
            log.warning("recording failed: %s", err)
        finally:
            try:
                if not err:
                    os.remove(self.raw_path)
            except OSError:
                pass
        if on_done:
            on_done(self.mp4_path, err)
