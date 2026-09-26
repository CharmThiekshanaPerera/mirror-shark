"""Find phones with Wireless debugging turned on, without relying on mDNS.

1. Discover live hosts on the local subnets (ping sweep, then the ARP table, which also lists hosts that ignore ping).
2. Probe Android's ephemeral port range on each host (adbd picks a random port there).
3. Confirm each open port really is ADB by sending an ADB CONNECT packet: a wireless-debugging port answers
   with an "STLS" (start TLS) request, a legacy `adb tcpip` port answers with "AUTH"/"CNXN".
"""
import asyncio
import ipaddress
import concurrent.futures
import re
import socket
import struct
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from .log import get_logger

log = get_logger("scanner")

CREATE_NO_WINDOW = 0x08000000
ADB_PORTS = (32768, 60999)      # Android's default ephemeral port range; adbd binds a random port in it
DEEP_PORTS = (1024, 65535)
LEGACY_PORTS = (5555,)          # `adb tcpip 5555`
MAX_HOSTS = 1024


@dataclass
class Found:
    ip: str
    port: int
    kind: str  # "wireless" (Wireless debugging, TLS) or "tcpip" (legacy adb tcpip)

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"


class Cancelled(Exception):
    pass


# --- ADB port identification ----------------------------------------------------------
def cnxn_packet() -> bytes:
    payload = b"host::features=shell_v2,cmd\x00"
    cmd = 0x4E584E43  # "CNXN"
    header = struct.pack("<6I", cmd, 0x01000001, 0x100000, len(payload), sum(payload) & 0xFFFFFFFF, cmd ^ 0xFFFFFFFF)
    return header + payload


def classify_reply(reply: bytes) -> str | None:
    """Map the first bytes an ADB endpoint sends back to a port kind."""
    if reply[:4] == b"STLS":
        return "wireless"
    if reply[:4] in (b"AUTH", b"CNXN"):
        return "tcpip"
    return None


async def verify_adb(ip: str, port: int, timeout: float = 1.5) -> str | None:
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
        writer.write(cnxn_packet())
        await writer.drain()
        reply = await asyncio.wait_for(reader.readexactly(24), timeout)
        return classify_reply(reply)
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
        return None
    finally:
        if writer is not None:
            writer.close()


async def _port_open(ip: str, port: int, sem: asyncio.Semaphore, timeout: float) -> bool:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
        except (OSError, asyncio.TimeoutError):
            return False
        writer.close()
        return True


async def scan_host(ip: str, ports: list[int], cancel: threading.Event,
                    progress: Callable[[int], None] = lambda n: None,
                    concurrency: int = 1200, timeout: float = 0.5, batch: int = 2400) -> list[Found]:
    """Probe `ports` on one host and return the ADB endpoints found (stops at the first batch that has one)."""
    sem = asyncio.Semaphore(concurrency)
    found: list[Found] = []
    for i in range(0, len(ports), batch):
        if cancel.is_set():
            raise Cancelled()
        chunk = ports[i:i + batch]
        results = await asyncio.gather(*(_port_open(ip, p, sem, timeout) for p in chunk))
        progress(len(chunk))
        for port, is_open in zip(chunk, results):
            if is_open:
                kind = await verify_adb(ip, port)
                if kind:
                    found.append(Found(ip, port, kind))
        if found:
            progress(len(ports) - i - len(chunk))  # skip the rest of this host
            break
    return found


# --- host discovery ---------------------------------------------------------------------
def parse_arp(text: str) -> list[tuple[str, str]]:
    """Parse `arp -a` output into (ip, mac) pairs, ignoring broadcast/multicast entries."""
    hosts = []
    for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})", text):
        ip, mac = m.group(1), m.group(2).lower()
        addr = ipaddress.ip_address(ip)
        if mac == "ff-ff-ff-ff-ff-ff" or addr.is_multicast or ip.endswith(".255"):
            continue
        hosts.append((ip, mac))
    return hosts


def is_randomized_mac(mac: str) -> bool:
    """Phones use private (locally administered) MAC addresses on Wi-Fi: bit 1 of the first byte is set."""
    return bool(int(mac.split("-")[0], 16) & 0b10)


def local_subnets() -> list[tuple[ipaddress.IPv4Address, ipaddress.IPv4Network]]:
    """Active physical IPv4 networks (skips loopback and virtual adapters such as Hyper-V/WSL/VMware)."""
    from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface

    skip = ("vethernet", "vmware", "virtualbox", "loopback", "bluetooth", "hyper-v", "wsl", "pseudo", "vpn", "tap")
    result = []
    for iface in QNetworkInterface.allInterfaces():
        flags = iface.flags()
        if not (flags & QNetworkInterface.IsUp and flags & QNetworkInterface.IsRunning) or flags & QNetworkInterface.IsLoopBack:
            continue
        if any(s in iface.humanReadableName().lower() for s in skip):
            continue
        for entry in iface.addressEntries():
            ip = entry.ip()
            if ip.protocol() != QAbstractSocket.IPv4Protocol or ip.isLoopback():
                continue
            addr = ipaddress.IPv4Address(ip.toString())
            if addr.is_link_local:
                continue
            prefix = entry.prefixLength()
            if prefix < 22:  # never sweep a huge network: limit to the /24 around us
                prefix = 24
            result.append((addr, ipaddress.ip_network(f"{addr}/{prefix}", strict=False)))
    return result


def _ping(ip: str) -> None:
    try:
        subprocess.run(["ping", "-n", "1", "-w", "400", ip], capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=3)
    except (subprocess.SubprocessError, OSError):
        pass


def sweep_hosts(addr: ipaddress.IPv4Address, net: ipaddress.IPv4Network, cancel: threading.Event) -> list[tuple[str, str]]:
    """Ping sweep the subnet (this also fills the ARP table), then read the live hosts from ARP as (ip, mac)."""
    targets = [str(h) for h in net.hosts() if h != addr][:MAX_HOSTS]
    with ThreadPoolExecutor(max_workers=128) as pool:
        futures = [pool.submit(_ping, ip) for ip in targets]
        for f in futures:
            if cancel.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
                raise Cancelled()
            f.result()
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
                             timeout=10, encoding="utf-8", errors="replace").stdout
    except (subprocess.SubprocessError, OSError):
        out = ""
    hosts = [(ip, mac) for ip, mac in parse_arp(out) if ipaddress.ip_address(ip) in net and ip != str(addr)]
    hosts.sort(key=lambda h: (not is_randomized_mac(h[1]), ipaddress.ip_address(h[0])))  # phones first
    return hosts


def discover_hosts(addr: ipaddress.IPv4Address, net: ipaddress.IPv4Network,
                   cancel: threading.Event) -> list[tuple[str, bool]]:
    """Returns (ip, looks_like_a_phone) pairs, phone-like devices first."""
    return [(ip, is_randomized_mac(mac)) for ip, mac in sweep_hosts(addr, net, cancel)]


# --- device list for the UI ---------------------------------------------------------------------
ANDROID_HINTS = ("android", "pixel", "galaxy", "sm-", "oneplus", "redmi", "xiaomi", "poco", "huawei", "honor", "oppo",
                 "vivo", "realme", "moto", "nokia", "samsung", "sony", "xperia", "tecno", "infinix", "lenovo-tab")
APPLE_HINTS = ("iphone", "ipad", "macbook", "imac", "apple")
TV_HINTS = ("tv", "roku", "chromecast", "bravia", "firestick", "fire-tv", "shield")
PC_HINTS = ("desktop-", "laptop-", "-pc", "pc-", "win", "thinkpad", "dell", "hp-")
PRINTER_HINTS = ("printer", "epson", "canon", "brother", "laserjet")


@dataclass
class NetDevice:
    ip: str
    mac: str
    hostname: str
    label: str
    icon: str
    phone_like: bool            # worth checking automatically for wireless debugging
    is_gateway: bool = False
    is_this_pc: bool = False

    @property
    def title(self) -> str:
        return self.hostname or self.ip


def classify(hostname: str, mac: str, is_gateway: bool) -> tuple[str, str, bool]:
    """Guess what a device is from its name and MAC address: (label, icon, worth_checking_for_adb)."""
    name = (hostname or "").lower()
    if is_gateway:
        return "Router / gateway", "📡", False
    if any(h in name for h in ANDROID_HINTS):
        return "Android phone or tablet", "📱", True
    if any(h in name for h in APPLE_HINTS):
        return "Apple device (no ADB)", "🍎", False
    if any(h in name for h in PRINTER_HINTS):
        return "Printer", "🖨", False
    if any(h in name for h in TV_HINTS):
        return "TV / streaming device", "📺", False
    if any(h in name for h in PC_HINTS):
        return "Computer", "💻", False
    if mac and is_randomized_mac(mac):
        return "Phone or tablet (private Wi-Fi address)", "📱", True
    return "Device", "❓", False


def default_gateways() -> set[str]:
    """Default gateway addresses from the routing table (numeric output, works in any Windows language)."""
    try:
        out = subprocess.run(["route", "print", "-4"], capture_output=True, text=True, creationflags=CREATE_NO_WINDOW,
                             timeout=10, encoding="utf-8", errors="replace").stdout
    except (subprocess.SubprocessError, OSError):
        return set()
    return set(re.findall(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s", out, re.MULTILINE))


def resolve_hostnames(ips: list[str], wait: float = 4.0) -> dict[str, str]:
    """Reverse-lookup names (the router usually knows DHCP clients by name, e.g. 'Pixel-7-Pro')."""
    names: dict[str, str] = {}

    def look(ip: str) -> None:
        try:
            names[ip] = socket.gethostbyaddr(ip)[0].split(".")[0]
        except OSError:
            pass

    pool = ThreadPoolExecutor(max_workers=32)
    futures = [pool.submit(look, ip) for ip in ips]
    concurrent.futures.wait(futures, timeout=wait)
    pool.shutdown(wait=False, cancel_futures=True)
    return dict(names)


def discover_devices(cancel: threading.Event, on_status: Callable[[str], None] = lambda s: None) -> list[NetDevice]:
    """Every device currently on the local network(s), with a best-guess type. Blocking; run it in a thread."""
    devices: list[NetDevice] = []
    gateways = default_gateways()
    for addr, net in local_subnets():
        on_status(f"Looking for devices on {net} \u2026")
        hosts = sweep_hosts(addr, net, cancel)
        on_status("Reading device names \u2026")
        names = resolve_hostnames([ip for ip, _ in hosts])
        me = NetDevice(str(addr), "", socket.gethostname(), "This PC", "\U0001F4BB", False, is_this_pc=True)
        found = []
        for ip, mac in hosts:
            is_gw = ip in gateways
            label, icon, phone_like = classify(names.get(ip, ""), mac, is_gw)
            found.append(NetDevice(ip, mac.replace("-", ":"), names.get(ip, ""), label, icon, phone_like, is_gw))
        # phones first, then the rest by address; this PC last
        found.sort(key=lambda d: (not d.phone_like, d.is_gateway, ipaddress.ip_address(d.ip)))
        devices += found + [me]
    return devices


# --- full scan --------------------------------------------------------------------------------
def scan_network(cancel: threading.Event,
                 on_status: Callable[[str], None] = lambda s: None,
                 on_progress: Callable[[int, int], None] = lambda done, total: None,
                 on_found: Callable[[Found], None] = lambda f: None,
                 deep: bool = False, stop_at_first: bool = True) -> list[Found]:
    """Scan every local network for phones with wireless debugging. Blocking; run it in a thread.

    With stop_at_first the scan ends as soon as a phone-like device turns out to have wireless debugging on;
    other devices (routers, PCs) are only checked when no phone-like device was found.
    """
    nets = local_subnets()
    if not nets:
        on_status("No active network connection found.")
        return []
    port_range = DEEP_PORTS if deep else ADB_PORTS
    ports = [p for p in LEGACY_PORTS] + [p for p in range(port_range[0], port_range[1] + 1) if p not in LEGACY_PORTS]
    results: list[Found] = []
    try:
        hosts: dict[str, bool] = {}
        for addr, net in nets:
            on_status(f"Looking for devices on {net} …")
            for ip, phone_like in discover_hosts(addr, net, cancel):
                hosts.setdefault(ip, phone_like)
        if not hosts:
            on_status("No other devices found on the network.")
            return []
        ordered = sorted(hosts, key=lambda ip: not hosts[ip])  # phone-like devices first
        on_status(f"Found {len(ordered)} device{'s' if len(ordered) != 1 else ''}. Checking for wireless debugging …")
        total = len(ordered) * len(ports)
        done = 0

        def progress(n: int) -> None:
            nonlocal done
            done += n
            on_progress(min(done, total), total)

        for index, ip in enumerate(ordered, 1):
            if cancel.is_set():
                raise Cancelled()
            if stop_at_first and results and not hosts[ip]:
                break  # a phone was found; no need to probe routers and PCs
            on_status(f"Checking {ip} ({index}/{len(ordered)}) …")
            for f in asyncio.run(scan_host(ip, ports, cancel, progress)):
                results.append(f)
                on_found(f)
    except Cancelled:
        on_status("Scan stopped.")
        return results
    on_progress(1, 1)
    on_status(f"Scan finished: {len(results)} phone{'s' if len(results) != 1 else ''} found." if results
              else "Scan finished: no phone with Wireless debugging found.")
    return results
