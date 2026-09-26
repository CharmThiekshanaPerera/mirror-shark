"""Application logging to %LOCALAPPDATA%\\PhoneLink\\logs and a crash handler."""
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import APP_NAME, __version__


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_file() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "phonelink.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("phonelink")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file(), maxBytes=512_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.info("=== %s %s starting (python %s) ===", APP_NAME, __version__, sys.version.split()[0])

    def hook(exc_type, exc, tb):
        logger.error("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"phonelink.{name}")
