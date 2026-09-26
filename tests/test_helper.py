import json
import socket
import threading

import pytest

from mirrorshark import helper
from mirrorshark.adb import Adb, AdbError


class FakePhone:
    """A tiny stand-in for the Mirror Shark Helper app: one JSON line in, one JSON line out."""

    def __init__(self, replies: dict, delay: float = 0.0):
        self.replies = replies
        self.delay = delay
        self.requests: list[dict] = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                line = conn.makefile("rb").readline()
                req = json.loads(line)
                self.requests.append(req)
                if self.delay:
                    threading.Event().wait(self.delay)
                reply = self.replies.get(req["cmd"])
                if reply is not None:
                    conn.sendall((json.dumps(reply) + "\n").encode())

    def close(self):
        self.sock.close()


@pytest.fixture
def phone():
    made = []

    def make(replies, delay=0.0):
        p = FakePhone(replies, delay)
        made.append(p)
        return p

    yield make
    for p in made:
        p.close()


def test_probe_reads_hello(phone):
    p = phone({"hello": {"app": "MirrorSharkHelper", "v": 1, "name": "Google Pixel 7 Pro", "adb_wifi": 0, "can_enable": True}})
    info = helper.probe("127.0.0.1", port=p.port)
    assert info == helper.HelperInfo("Google Pixel 7 Pro", False, True, 1)


def test_probe_rejects_other_services(phone):
    p = phone({"hello": {"app": "SomethingElse"}})
    assert helper.probe("127.0.0.1", port=p.port) is None
    assert helper.probe("127.0.0.1", port=1, timeout=0.2) is None   # nothing listening


@pytest.mark.parametrize("status", ["enabled", "declined", "busy", "cooldown", "needs_manual", "timeout", "failed"])
def test_request_enable_passes_status_through(phone, status):
    p = phone({"enable": {"status": status}})
    assert helper.request_enable("127.0.0.1", "TEST-PC", port=p.port, wait=5) == status
    assert p.requests == [{"cmd": "enable", "pc": "TEST-PC"}]


def test_request_enable_unknown_status_is_failed(phone):
    p = phone({"enable": {"status": "surprise"}})
    assert helper.request_enable("127.0.0.1", port=p.port, wait=5) == "failed"


def test_request_enable_unreachable_and_timeout(phone):
    assert helper.request_enable("127.0.0.1", port=1, wait=1) == "unreachable"
    silent = phone({}, delay=0)          # accepts the connection but never answers
    assert helper.request_enable("127.0.0.1", port=silent.port, wait=0.5) == "timeout"


def test_every_status_has_user_text():
    for status in ("enabled", "declined", "timeout", "busy", "cooldown", "needs_manual", "failed", "unreachable"):
        assert helper.STATUS_TEXT[status]


class FakeAdb(Adb):
    def __init__(self, fail_grant=False):
        self.exe = "adb"
        self.calls = []
        self.fail_grant = fail_grant

    def run(self, *args, serial=None, timeout=30):
        self.calls.append(("run",) + args)
        return "Success"

    def shell(self, serial, command, timeout=30):
        self.calls.append(("shell", command))
        if self.fail_grant and "WRITE_SECURE_SETTINGS" in command:
            raise AdbError("Operation not allowed")
        return ""


def test_install_helper_installs_grants_and_starts(monkeypatch, tmp_path):
    apk = tmp_path / "h.apk"
    apk.write_bytes(b"x")
    monkeypatch.setattr(helper, "apk_path", lambda: apk)
    a = FakeAdb()
    assert "ready" in helper.install_helper(a, "S")
    cmds = [c[1] if c[0] == "shell" else " ".join(c[1:]) for c in a.calls]
    assert cmds[0].startswith("install -r") and any("pm grant" in c and "WRITE_SECURE_SETTINGS" in c for c in cmds)
    assert any("am start" in c for c in cmds)


def test_install_helper_reports_missing_permission(monkeypatch, tmp_path):
    apk = tmp_path / "h.apk"
    apk.write_bytes(b"x")
    monkeypatch.setattr(helper, "apk_path", lambda: apk)
    assert "only open Developer options" in helper.install_helper(FakeAdb(fail_grant=True), "S")


def test_install_helper_without_apk(monkeypatch):
    monkeypatch.setattr(helper, "apk_path", lambda: None)
    with pytest.raises(AdbError):
        helper.install_helper(FakeAdb(), "S")
