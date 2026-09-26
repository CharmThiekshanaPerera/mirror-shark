"""Run blocking work (adb calls) off the UI thread."""
from PySide6.QtCore import QThread, Signal

from ..log import get_logger

log = get_logger("tasks")
_ALIVE: set = set()  # keep references so a running QThread is never garbage-collected


class Task(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as e:  # noqa: BLE001 - reported to the UI
            log.warning("task failed: %s", e)
            self.failed.emit(str(e) or e.__class__.__name__)


def run_task(fn, on_ok=None, on_fail=None) -> Task:
    t = Task(fn)
    _ALIVE.add(t)
    if on_ok:
        t.finished_ok.connect(on_ok)
    if on_fail:
        t.failed.connect(on_fail)
    t.finished.connect(lambda: _ALIVE.discard(t))
    t.start()
    return t


def keep_alive(thread: QThread) -> None:
    """Hold a reference to `thread` until it finishes (its owner window may close first)."""
    _ALIVE.add(thread)
    thread.finished.connect(lambda: _ALIVE.discard(thread))
