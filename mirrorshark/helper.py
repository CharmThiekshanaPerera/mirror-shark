"""Client for Mirror Shark Helper, the small app that lets a phone's owner accept a request to turn on Wireless debugging.

Android does not let a computer switch Wireless debugging on by itself. Instead the helper app on the phone listens on
the local network; this module asks it, the phone shows an Accept / Decline notification, and only when the owner taps
Accept does the helper switch the setting on (it holds the WRITE_SECURE_SETTINGS permission, granted once over ADB).
"""
import json
import socket
from dataclasses import dataclass
from pathlib import Path

from .adb import Adb, AdbError
from .log import get_logger
from .resources import find_resource

log = get_logger("helper")

HELPER_PORT = 47620
HELPER_PACKAGE = "com.mirrorshark.helper"
REQUEST_WAIT = 75.0   # the phone waits 60 s for the owner; leave a little slack

STATUS_TEXT = {
    "enabled": "Wireless debugging was turned on.",
    "declined": "The request was declined on the phone.",
    "timeout": "Nobody answered the request on the phone in time.",
    "busy": "The phone is already showing a request. Answer it first.",
    "cooldown": "The phone recently declined a request and is waiting before it asks again. Try in a few minutes.",
    "needs_manual": ("The request was accepted, but the helper does not have permission to switch it on itself. "
                     "Open Developer options on the phone and turn on Wireless debugging (or use More › Set up phone "
                     "helper while the phone is connected)."),
    "failed": "The phone accepted, but Android did not turn Wireless debugging on. Turn it on in Developer options.",
    "unreachable": "Could not reach the helper app on the phone (is it running and on the same Wi-Fi?).",
}


@dataclass
class HelperInfo:
    name: str
    adb_wifi: bool      # Wireless debugging currently on
    can_enable: bool    # helper holds the permission to switch it on
    version: int


def _exchange(host: str, request: dict, port: int, connect_timeout: float, read_timeout: float) -> tuple[dict | None, bool]:
    """Send one request line, read one reply line. Returns (reply or None, whether the connection was made)."""
    try:
        s = socket.create_connection((host, port), timeout=connect_timeout)
    except OSError:
        return None, False
    try:
        with s:
            s.settimeout(read_timeout)
            s.sendall((json.dumps(request) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n") and len(buf) < 4096:
                chunk = s.recv(1024)
                if not chunk:
                    break
                buf += chunk
        return (json.loads(buf.decode("utf-8")) if buf.strip() else None), True
    except (OSError, ValueError):
        return None, True


def probe(host: str, port: int = HELPER_PORT, timeout: float = 0.8) -> HelperInfo | None:
    """Is the helper app running on this host? Returns its info, or None."""
    r, _ = _exchange(host, {"cmd": "hello"}, port, timeout, timeout * 2)
    if not r or r.get("app") != "MirrorSharkHelper":
        return None
    return HelperInfo(str(r.get("name", "")), bool(r.get("adb_wifi")), bool(r.get("can_enable")), int(r.get("v", 1)))


def request_enable(host: str, pc_name: str | None = None, port: int = HELPER_PORT, wait: float = REQUEST_WAIT) -> str:
    """Ask the phone to turn on Wireless debugging. Blocks until the owner answers (or `wait` seconds pass).

    Returns one of the keys of STATUS_TEXT.
    """
    pc = pc_name or socket.gethostname()
    reply, connected = _exchange(host, {"cmd": "enable", "pc": pc}, port, 3.0, wait)
    if not connected:
        status = "unreachable"
    elif reply is None:
        status = "timeout"
    else:
        status = reply.get("status") if reply.get("status") in STATUS_TEXT else "failed"
    log.info("enable request to %s -> %s", host, status)
    return status


def apk_path() -> Path | None:
    return find_resource("assets/MirrorSharkHelper.apk")


def install_helper(adb: Adb, serial: str, log_fn=lambda s: None) -> str:
    """Install the helper on a connected phone and give it the permission to switch on Wireless debugging.

    Returns a short summary. Raises AdbError if the APK cannot be installed.
    """
    apk = apk_path()
    if apk is None:
        raise AdbError("The helper app file (MirrorSharkHelper.apk) was not found next to Mirror Shark.")
    log_fn("Installing Mirror Shark Helper…")
    adb.run("install", "-r", str(apk), serial=serial, timeout=120)
    granted = True
    log_fn("Giving it permission to switch on Wireless debugging…")
    try:
        adb.shell(serial, f"pm grant {HELPER_PACKAGE} android.permission.WRITE_SECURE_SETTINGS")
    except AdbError as e:
        granted = False
        log.warning("could not grant WRITE_SECURE_SETTINGS: %s", e)
    try:
        adb.shell(serial, f"pm grant {HELPER_PACKAGE} android.permission.POST_NOTIFICATIONS")  # Android 13+
    except AdbError:
        pass
    log_fn("Starting the helper…")
    adb.shell(serial, f"am start -n {HELPER_PACKAGE}/.MainActivity")
    return ("Helper installed and ready." if granted else
            "Helper installed, but Android would not let Mirror Shark grant the permission, so requests will only "
            "open Developer options on the phone.")
