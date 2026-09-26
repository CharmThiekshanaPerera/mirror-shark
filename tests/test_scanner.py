import asyncio
import ipaddress
import struct
import threading

from mirrorshark import scanner


def test_cnxn_packet_is_valid_adb_header():
    pkt = scanner.cnxn_packet()
    cmd, version, maxdata, length, check, magic = struct.unpack("<6I", pkt[:24])
    assert pkt[:4] == b"CNXN" and cmd ^ 0xFFFFFFFF == magic
    assert length == len(pkt) - 24 and check == sum(pkt[24:]) & 0xFFFFFFFF


def test_classify_reply():
    assert scanner.classify_reply(b"STLS" + b"\0" * 20) == "wireless"
    assert scanner.classify_reply(b"AUTH" + b"\0" * 20) == "tcpip"
    assert scanner.classify_reply(b"HTTP/1.1 400") is None


ARP = """
Interface: 192.168.8.143 --- 0xb
  Internet Address      Physical Address      Type
  192.168.8.1           a4-2b-b0-11-22-33     dynamic
  192.168.8.185         ba-f1-7b-19-3e-f6     dynamic
  192.168.8.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.22            01-00-5e-00-00-16     static
"""


def test_parse_arp_skips_broadcast_and_multicast():
    assert scanner.parse_arp(ARP) == [("192.168.8.1", "a4-2b-b0-11-22-33"), ("192.168.8.185", "ba-f1-7b-19-3e-f6")]


def test_randomized_mac_detection():
    assert scanner.is_randomized_mac("ba-f1-7b-19-3e-f6")      # locally administered (phone)
    assert not scanner.is_randomized_mac("a4-2b-b0-11-22-33")  # vendor-assigned (router)


def _fake_adb_server(reply: bytes):
    async def handle(reader, writer):
        try:
            await reader.readexactly(24)
            writer.write(reply)
            await writer.drain()
        finally:
            writer.close()
    return handle


def test_scan_finds_adb_port_and_ignores_other_services():
    async def run():
        adb = await asyncio.start_server(_fake_adb_server(b"STLS" + b"\0" * 20), "127.0.0.1", 0)
        other = await asyncio.start_server(_fake_adb_server(b"HTTP" + b"\0" * 20), "127.0.0.1", 0)
        adb_port = adb.sockets[0].getsockname()[1]
        other_port = other.sockets[0].getsockname()[1]
        found = await scanner.scan_host("127.0.0.1", sorted({adb_port, other_port, 1}), threading.Event(), timeout=0.5)
        adb.close()
        other.close()
        return adb_port, found

    adb_port, found = asyncio.run(run())
    assert [(f.port, f.kind) for f in found] == [(adb_port, "wireless")]


def test_scan_can_be_cancelled():
    cancel = threading.Event()
    cancel.set()
    try:
        asyncio.run(scanner.scan_host("127.0.0.1", [1, 2, 3], cancel))
    except scanner.Cancelled:
        return
    raise AssertionError("expected Cancelled")


def test_found_address():
    assert scanner.Found("192.168.8.185", 34305, "wireless").address == "192.168.8.185:34305"
    assert ipaddress.ip_address("192.168.8.185") in ipaddress.ip_network("192.168.8.0/24")
