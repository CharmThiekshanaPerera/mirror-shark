import struct

from phonelink import protocol as p


def test_session_header():
    h = p.parse_video_header(struct.pack(">III", 0x80000000, 360, 800))
    assert isinstance(h, p.SessionHeader) and (h.width, h.height) == (360, 800)


def test_packet_header_flags():
    raw = struct.pack(">QI", p.PACKET_FLAG_CONFIG | 5, 32)
    h = p.parse_video_header(raw)
    assert h.config and not h.key_frame and h.pts == 5 and h.size == 32
    raw = struct.pack(">QI", p.PACKET_FLAG_KEY_FRAME | 1704372962, 14820)
    h = p.parse_video_header(raw)
    assert h.key_frame and not h.config and h.pts == 1704372962


def test_device_name():
    assert p.parse_device_name(b"Pixel 7 Pro" + b"\0" * 53) == "Pixel 7 Pro"


def test_touch_layout():
    m = p.encode_touch(p.ACTION_DOWN, p.POINTER_ID_MOUSE, 10, 20, 360, 800, 1.0, 0, p.BUTTON_PRIMARY)
    assert len(m) == 32 and m[0] == p.TYPE_TOUCH and m[1] == p.ACTION_DOWN
    assert m[2:10] == b"\xff" * 8
    assert struct.unpack(">ii", m[10:18]) == (10, 20)
    assert struct.unpack(">HHH", m[18:24]) == (360, 800, 0xFFFF)


def test_keycode_and_text():
    assert p.encode_keycode(p.ACTION_DOWN, p.KEYCODE_HOME) == struct.pack(">BBiii", 0, 0, 3, 0, 0)
    m = p.encode_text("héllo")
    assert m[0] == p.TYPE_TEXT and struct.unpack(">I", m[1:5])[0] == len("héllo".encode())


def test_text_not_cut_mid_character():
    m = p.encode_text("é" * 400)
    n = struct.unpack(">I", m[1:5])[0]
    assert n <= p.MAX_TEXT_BYTES and m[5:].decode("utf-8") == "é" * (n // 2)


def test_scroll_clamped():
    m = p.encode_scroll(1, 2, 3, 4, 5.0, -5.0)
    assert len(m) == 21
    h, v = struct.unpack(">hh", m[13:17])
    assert (h, v) == (0x7FFF, -0x7FFF)


def test_clipboard():
    m = p.encode_set_clipboard(7, "abc", paste=True)
    assert m[0] == p.TYPE_SET_CLIPBOARD and struct.unpack(">QBI", m[1:14]) == (7, 1, 3) and m[14:] == b"abc"
