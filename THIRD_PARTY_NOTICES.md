# Third-party notices

PhoneLink's own code is MIT licensed (see `LICENSE`). The release build bundles or depends on the following. Each keeps its own license.

| Component | Use | License |
|---|---|---|
| [scrcpy](https://github.com/Genymobile/scrcpy) server (`scrcpy-server`, v4.1) | Runs on the phone to capture and encode the screen | Apache-2.0 |
| [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (`adb.exe` and DLLs) | Talks to the phone over ADB | Apache-2.0 and others, see the bundled `NOTICE.txt` |
| [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/) | User interface, audio output | LGPL-3.0 (or GPL / commercial) |
| [PyAV](https://github.com/PyAV-Org/PyAV) with FFmpeg | H.264 decoding and MP4 muxing | PyAV: BSD-3-Clause. FFmpeg: LGPL-2.1+ (see note) |
| [NumPy](https://numpy.org/) | Frame conversion | BSD-3-Clause |
| [PyInstaller](https://pyinstaller.org/) | Packaging into a single exe | GPL-2.0 with an exception that permits distributing the packaged app under any license |

## Notes for redistribution

- **FFmpeg build inside PyAV.** The FFmpeg libraries shipped in PyAV's Windows wheels can include GPL-licensed codecs such as libx264. PhoneLink only decodes video and copies the phone's H.264 stream into MP4 files; it does not use any of the GPL encoders. If you redistribute the exe outside your own use, review the licenses of the exact wheel you build with, or use a PyAV build with an LGPL-only FFmpeg.
- **Qt (LGPL-3.0).** Qt is dynamically linked inside the exe. Recipients must be able to replace it, which is possible by building PhoneLink from source with this repository.
- **scrcpy and Platform-Tools license texts** are included in the `licenses` folder of each release zip.
