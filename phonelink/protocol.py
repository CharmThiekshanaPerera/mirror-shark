"""scrcpy 4.1 wire protocol: pure encode/decode helpers (no I/O)."""
import struct
from dataclasses import dataclass

SERVER_VERSION = "4.1"

# --- video stream -----------------------------------------------------------
# After the 1-byte dummy and 64-byte device name, the stream is:
#   codec id (4 bytes), then a sequence of 12-byte headers:
#     session header : [u32 with MSB set][u32 width][u32 height]
#     packet header  : [u64 pts/flags][u32 size] followed by `size` bytes
PACKET_FLAG_CONFIG = 1 << 62
PACKET_FLAG_KEY_FRAME = 1 << 61
PTS_MASK = PACKET_FLAG_KEY_FRAME - 1


@dataclass
class SessionHeader:
    width: int
    height: int


@dataclass
class PacketHeader:
    pts: int
    size: int
    config: bool
    key_frame: bool


def parse_video_header(header: bytes):
    """Parse a 12-byte header into a SessionHeader or PacketHeader."""
    if len(header) != 12:
        raise ValueError("video header must be 12 bytes")
    if header[0] & 0x80:
        _, w, h = struct.unpack(">III", header)
        return SessionHeader(w, h)
    pts_flags, size = struct.unpack(">QI", header)
    return PacketHeader(
        pts=pts_flags & PTS_MASK,
        size=size,
        config=bool(pts_flags & PACKET_FLAG_CONFIG),
        key_frame=bool(pts_flags & PACKET_FLAG_KEY_FRAME),
    )


def parse_device_name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


# --- control messages (client -> device) -----------------------------------
TYPE_KEYCODE = 0
TYPE_TEXT = 1
TYPE_TOUCH = 2
TYPE_SCROLL = 3
TYPE_BACK_OR_SCREEN_ON = 4
TYPE_EXPAND_NOTIFICATION_PANEL = 5
TYPE_EXPAND_SETTINGS_PANEL = 6
TYPE_COLLAPSE_PANELS = 7
TYPE_GET_CLIPBOARD = 8
TYPE_SET_CLIPBOARD = 9
TYPE_SET_DISPLAY_POWER = 10
TYPE_ROTATE_DEVICE = 11
TYPE_RESET_VIDEO = 17  # ask the server for a fresh config + key frame

ACTION_DOWN = 0
ACTION_UP = 1
ACTION_MOVE = 2

POINTER_ID_MOUSE = 0xFFFFFFFFFFFFFFFF
BUTTON_PRIMARY = 1
BUTTON_SECONDARY = 2
BUTTON_TERTIARY = 4

MAX_TEXT_BYTES = 300
MAX_CLIPBOARD_BYTES = (1 << 18) - 14

# Android keycodes
KEYCODE_HOME = 3
KEYCODE_BACK = 4
KEYCODE_DPAD_UP = 19
KEYCODE_DPAD_DOWN = 20
KEYCODE_DPAD_LEFT = 21
KEYCODE_DPAD_RIGHT = 22
KEYCODE_VOLUME_UP = 24
KEYCODE_VOLUME_DOWN = 25
KEYCODE_POWER = 26
KEYCODE_TAB = 61
KEYCODE_SPACE = 62
KEYCODE_ENTER = 66
KEYCODE_DEL = 67
KEYCODE_PAGE_UP = 92
KEYCODE_PAGE_DOWN = 93
KEYCODE_ESCAPE = 111
KEYCODE_FORWARD_DEL = 112
KEYCODE_MOVE_HOME = 122
KEYCODE_MOVE_END = 123
KEYCODE_APP_SWITCH = 187


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def encode_keycode(action: int, keycode: int, repeat: int = 0, meta: int = 0) -> bytes:
    return struct.pack(">BBiii", TYPE_KEYCODE, action, keycode, repeat, meta)


def encode_text(text: str) -> bytes:
    data = text.encode("utf-8")[:MAX_TEXT_BYTES]
    # do not cut a multi-byte character in half
    data = data.decode("utf-8", "ignore").encode("utf-8")
    return struct.pack(">BI", TYPE_TEXT, len(data)) + data


def encode_touch(action: int, pointer_id: int, x: int, y: int, width: int, height: int,
                 pressure: float = 1.0, action_button: int = 0, buttons: int = 0) -> bytes:
    p = int(_clamp(pressure, 0.0, 1.0) * 0xFFFF)
    return struct.pack(">BBQiiHHHii", TYPE_TOUCH, action, pointer_id, x, y,
                       width, height, p, action_button, buttons)


def encode_scroll(x: int, y: int, width: int, height: int,
                  hscroll: float, vscroll: float, buttons: int = 0) -> bytes:
    def fp(v):  # float in [-1, 1] -> signed 16-bit fixed point
        return int(_clamp(v, -1.0, 1.0) * 0x7FFF)
    return struct.pack(">BiiHHhhi", TYPE_SCROLL, x, y, width, height, fp(hscroll), fp(vscroll), buttons)


def encode_back_or_screen_on(action: int) -> bytes:
    return struct.pack(">BB", TYPE_BACK_OR_SCREEN_ON, action)


def encode_simple(msg_type: int) -> bytes:
    return struct.pack(">B", msg_type)


def encode_set_display_power(on: bool) -> bytes:
    return struct.pack(">BB", TYPE_SET_DISPLAY_POWER, 1 if on else 0)


def encode_get_clipboard(copy_key: int = 0) -> bytes:
    return struct.pack(">BB", TYPE_GET_CLIPBOARD, copy_key)


def encode_set_clipboard(sequence: int, text: str, paste: bool = False) -> bytes:
    data = text.encode("utf-8")[:MAX_CLIPBOARD_BYTES]
    data = data.decode("utf-8", "ignore").encode("utf-8")
    return struct.pack(">BQBI", TYPE_SET_CLIPBOARD, sequence, 1 if paste else 0, len(data)) + data


# --- device messages (device -> client) ------------------------------------
DEVMSG_CLIPBOARD = 0
DEVMSG_ACK_CLIPBOARD = 1
DEVMSG_UHID_OUTPUT = 2
