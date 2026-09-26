"""Thin wrapper around adb.exe."""
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


BUNDLED_FILES = ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll", "scrcpy-server")


def _install_bundle() -> Path | None:
    """When frozen into a single exe, copy the bundled tools to a permanent folder.

    adb keeps running as a background server after the app exits; running it straight from the exe's temporary
    extraction folder would lock that folder and leave junk behind on every launch.
    """
    if not getattr(sys, "frozen", False):
        return None
    src = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    from .log import data_dir
    dest = data_dir() / "bin"
    dest.mkdir(parents=True, exist_ok=True)
    for name in BUNDLED_FILES:
        s, d = src / name, dest / name
        if s.exists() and (not d.exists() or d.stat().st_size != s.stat().st_size):
            try:
                import shutil
                shutil.copy2(s, d)
            except OSError:
                pass  # file in use (adb already running from this folder): keep the existing copy
    return dest


def find_tool(name: str) -> Path:
    """Locate a bundled tool (adb.exe, scrcpy-server): installed bundle, platform-tools dir, then PATH."""
    candidates = []
    installed = _install_bundle()
    if installed:
        candidates.append(installed)
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        candidates.append(Path(sys.executable).parent)
    here = Path(__file__).resolve().parent
    candidates += [here.parent.parent, here.parent, Path.cwd()]  # platform-tools, project root, cwd
    for d in candidates:
        p = d / name
        if p.exists():
            return p
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d) / name
        if p.exists():
            return p
    raise FileNotFoundError(f"{name} not found (looked in {[str(c) for c in candidates]})")


@dataclass
class Device:
    serial: str
    state: str
    description: str = ""


@dataclass
class MdnsService:
    name: str
    kind: str  # "connect" or "pairing"
    address: str  # ip:port


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, exe: Path | str | None = None):
        self.exe = str(exe or find_tool("adb.exe" if os.name == "nt" else "adb"))

    def run(self, *args: str, serial: str | None = None, timeout: float = 30) -> str:
        cmd = [self.exe] + (["-s", serial] if serial else []) + list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb {' '.join(args)} timed out after {timeout}s") from e
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode != 0:
            raise AdbError(out.strip() or f"adb exited with {r.returncode}")
        return out

    def popen(self, *args: str, serial: str | None = None) -> subprocess.Popen:
        cmd = [self.exe] + (["-s", serial] if serial else []) + list(args)
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                creationflags=CREATE_NO_WINDOW)

    # --- devices ---------------------------------------------------------
    def devices(self) -> list[Device]:
        out = self.run("devices", "-l")
        result = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and not line.startswith("*"):
                result.append(Device(parts[0], parts[1], " ".join(parts[2:])))
        return result

    def connect(self, address: str) -> str:
        out = self.run("connect", address, timeout=20).strip()
        if "connected" not in out.lower() or "cannot" in out.lower() or "failed" in out.lower():
            raise AdbError(out)
        return out

    def disconnect(self, address: str) -> str:
        return self.run("disconnect", address).strip()

    def pair(self, address: str, code: str) -> str:
        out = self.run("pair", address, code.strip(), timeout=30).strip()
        if "successfully paired" not in out.lower():
            raise AdbError(out)
        return out

    def mdns_services(self) -> list[MdnsService]:
        """Phones with Wireless debugging on advertise themselves via mDNS."""
        out = self.run("mdns", "services", timeout=10)
        services = []
        for line in out.splitlines():
            m = re.match(r"(\S+)\s+_adb-tls-(connect|pairing)\._tcp\.?\s+(\S+:\d+)", line)
            if m:
                services.append(MdnsService(m.group(1), m.group(2), m.group(3)))
        return services

    # --- files / tunnels -------------------------------------------------
    def push(self, serial: str, local: str, remote: str) -> None:
        self.run("push", local, remote, serial=serial, timeout=60)

    def forward_abstract(self, serial: str, abstract_name: str) -> int:
        """Forward an ephemeral local TCP port to a device abstract socket; returns the local port."""
        out = self.run("forward", "tcp:0", f"localabstract:{abstract_name}", serial=serial).strip()
        return int(out.splitlines()[-1])

    def forward_remove(self, serial: str, port: int) -> None:
        try:
            self.run("forward", "--remove", f"tcp:{port}", serial=serial)
        except AdbError:
            pass

    def shell(self, serial: str, command: str, timeout: float = 30) -> str:
        return self.run("shell", command, serial=serial, timeout=timeout)

    def model_name(self, serial: str) -> str:
        """Human-friendly phone name, e.g. 'Google Pixel 7 Pro'."""
        try:
            brand = self.shell(serial, "getprop ro.product.manufacturer", timeout=8).strip()
            model = self.shell(serial, "getprop ro.product.model", timeout=8).strip()
        except AdbError:
            return serial
        if model.lower().startswith(brand.lower()):
            return model
        return f"{brand.capitalize()} {model}".strip() or serial

    def device_info(self, serial: str) -> dict:
        """Battery level/charging state; cheap enough to poll."""
        info = {}
        try:
            out = self.shell(serial, "dumpsys battery", timeout=8)
        except AdbError:
            return info
        for line in out.splitlines():
            k, _, v = line.strip().partition(":")
            v = v.strip()
            if k == "level" and v.isdigit():
                info["battery"] = int(v)
            elif k == "AC powered" and v == "true" or k == "USB powered" and v == "true" or k == "Wireless powered" and v == "true":
                info["charging"] = True
        return info

    def android_version(self, serial: str) -> str:
        try:
            return self.shell(serial, "getprop ro.build.version.release", timeout=8).strip()
        except AdbError:
            return ""

    def install(self, serial: str, apk: str) -> str:
        return self.run("install", "-r", apk, serial=serial, timeout=300).strip()

    def push_file(self, serial: str, local: str, remote_dir: str = "/sdcard/Download/") -> str:
        return self.run("push", local, remote_dir, serial=serial, timeout=600).strip()

    def version(self) -> str:
        first = self.run("version", timeout=10).splitlines()
        return first[0] if first else ""

    def kill_server(self) -> None:
        try:
            self.run("kill-server", timeout=10)
        except AdbError:
            pass
