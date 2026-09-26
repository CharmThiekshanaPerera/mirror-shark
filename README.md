# PhoneLink

Windows desktop app that mirrors and controls an Android phone over wireless ADB (Wi-Fi). Python + PySide6 (Qt) + PyAV; it drives the scrcpy 4.1 server on the phone and implements the client side itself (`phonelink/protocol.py`, `server.py`, `video.py`, `control.py`).

- **Users:** see [docs/USER_GUIDE.md](docs/USER_GUIDE.md). Run `PhoneLink.exe`.
- **Build:** first put `adb.exe`, `AdbWinApi.dll`, `AdbWinUsbApi.dll`, `LICENSE.txt`, `NOTICE.txt` (Android platform-tools) and `scrcpy-server` (scrcpy 4.1) in the folder above this one - they are not stored in this repo. Then `build.bat` runs the tests, generates the icon and writes `dist\PhoneLink.exe` (single file) plus `release\PhoneLink-<version>-win64.zip`. It bundles `adb.exe`, its DLLs and `scrcpy-server` from the parent platform-tools folder. The scrcpy server version must match `protocol.SERVER_VERSION` (currently 4.1).
- **Run from source:** `run.bat` (creates `.venv` on first run) or `.venv\Scripts\python main.py`.
- **Tests:** `.venv\Scripts\python -m pytest`.
- **Smoke test a build:** `dist\PhoneLink.exe --selftest` connects to the first device, decodes a frame and writes `%LOCALAPPDATA%\PhoneLink\selftest.txt`.

## Layout

| Path | Purpose |
|---|---|
| `phonelink/adb.py` | adb wrapper, bundled tool installer, mDNS discovery |
| `phonelink/server.py` | pushes/starts the scrcpy server, opens video + control sockets |
| `phonelink/protocol.py` | wire format encode/decode (unit tested) |
| `phonelink/video.py` | packet reader + H.264 decode |
| `phonelink/control.py` | touch/key/clipboard messages |
| `phonelink/ui/` | main window, mirror window, help dialog, widgets |
| `phonelink/theme.py`, `errors.py`, `log.py` | styling + icon, friendly error text, logging |
| `docs/USER_GUIDE.md` | end-user guide (also shown in-app under Help) |
