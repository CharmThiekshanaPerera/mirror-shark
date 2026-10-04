"""Remembers devices the user has saved, so Mirror Shark recognises them again across restarts and IP changes.

Keyed by MAC address (stable even when DHCP hands out a new IP, unlike the IP:port Android shows, which also
changes every time Wireless debugging is toggled off and on). This only tracks *which devices to prioritise and
auto-connect to* - it cannot make Android remember the pairing itself. Android keeps that trust on the phone, and
only the phone's owner can grant it (once, via the pairing code); if the phone's own trust list forgets this PC
(a reboot or network change does not normally cause this, but an OS update or "forget network" sometimes does),
one re-pair is unavoidable. Saving a device means that after that one pairing, nothing needs to be typed again.
"""
import json
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .log import data_dir, get_logger

log = get_logger("devices_store")

_LOCK = threading.Lock()


@dataclass
class SavedDevice:
    mac: str
    name: str = ""
    last_ip: str = ""
    last_port: int = 0
    saved_at: float = 0.0
    last_seen_at: float = 0.0


def _path() -> Path:
    return data_dir() / "devices.json"


def load() -> dict[str, SavedDevice]:
    """All saved devices, keyed by lowercase MAC address."""
    p = _path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("could not read %s: %s", p, e)
        return {}
    out: dict[str, SavedDevice] = {}
    for mac, fields in raw.items():
        try:
            out[mac] = SavedDevice(**{**fields, "mac": mac})
        except TypeError:
            continue
    return out


def _write(devices: dict[str, SavedDevice]) -> None:
    try:
        _path().write_text(json.dumps({m: asdict(d) for m, d in devices.items()}, indent=2), encoding="utf-8")
    except OSError as e:
        log.warning("could not save devices: %s", e)


def upsert(mac: str, **fields) -> SavedDevice | None:
    """Add or update a saved device by MAC. Call this when the user stars a device, or whenever it connects.

    Empty/falsy values in `fields` do not overwrite what is already stored (a reconnect that could not resolve
    a hostname should not erase a name learned earlier).
    """
    mac = (mac or "").lower()
    if not mac:
        return None
    with _LOCK:
        devices = load()
        d = devices.get(mac) or SavedDevice(mac=mac, saved_at=time.time())
        for k, v in fields.items():
            if v:
                setattr(d, k, v)
        d.last_seen_at = time.time()
        devices[mac] = d
        _write(devices)
        return d


def remove(mac: str) -> None:
    mac = (mac or "").lower()
    if not mac:
        return
    with _LOCK:
        devices = load()
        if mac in devices:
            del devices[mac]
            _write(devices)


def is_saved(mac: str) -> bool:
    return bool(mac) and mac.lower() in load()


def format_age(seconds: float | None) -> str:
    """Render a span of seconds as "just now" / "5 min ago" / "3 h ago" / "2 d ago", for a saved device's last-seen time."""
    if seconds is None:
        return "never"
    if seconds < 90:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    return f"{int(seconds // 86400)} d ago"
