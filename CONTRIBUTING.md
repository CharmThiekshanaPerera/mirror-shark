# Contributing to Mirror Shark

Thanks for helping. Bug reports, ideas and pull requests are all welcome.

## Reporting a bug

Open an issue with the **Bug report** template. The most useful details are your phone model and Android version, how the phone and PC are connected, the Mirror Shark version (Help > About) and the end of the log (Help > Open log folder > `mirrorshark.log`).

## Development setup

Windows, Python 3.12 or newer.

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py          # run from source
.venv\Scripts\python -m pytest        # unit tests
```

Running the app or building the exe needs `adb.exe`, its DLLs and `scrcpy-server` (v4.1) in the folder above the repository, see the README.

## Project notes

- The wire format lives in `mirrorshark/protocol.py` and is covered by unit tests. If you change it, add a test.
- Anything that blocks (adb calls, sockets) must stay off the UI thread: use `run_task` from `mirrorshark/ui/tasks.py`.
- User-facing errors go through `mirrorshark/errors.py` so messages stay in plain language.
- Real-device behavior (video, touch, audio, recording) cannot be unit tested. Please say in your pull request what you tried on which phone and Android version. `dist\MirrorShark.exe --selftest` is a quick check for a build.
- The bundled scrcpy server version must match `SERVER_VERSION`. If you upgrade the server, re-check the video/control/audio protocol.

## Android helper app

The phone-side helper lives in `android-helper/` (plain Java, no Gradle). Build it with `python tools/build_helper.py` (needs a JDK and the Android SDK with build-tools and the android-34 platform). It writes `assets/MirrorSharkHelper.apk`, which is committed so that builds and CI do not need the SDK. Rebuild and commit the APK when the helper's source changes, and keep the protocol in `mirrorshark/helper.py` and `HelperService.java` in sync.

## Pull requests

1. Keep changes focused and match the surrounding code style.
2. Run `python -m pytest`.
3. Update `CHANGELOG.md` and, for user-visible changes, `docs/USER_GUIDE.md`.
4. Describe what you tested.

By contributing you agree that your contribution is licensed under the MIT License.
