# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/), versions follow [SemVer](https://semver.org/).

## [1.1.1] - 2026-09-26

### Fixed
- Main window: a phone card with long details (Android version, battery) made the content wider than the window, clipping the Refresh and More buttons. Details now wrap and horizontal scrolling is off.

### Added
- GitHub project setup: README with screenshots, license, contributing guide, security policy, issue and pull request templates, CI (tests) and a release workflow that builds the exe.

## [1.1.0] - 2026-09-26

### Added
- Phone sound on the PC (Android 11+), mute button (Ctrl+M), optional "keep sound on the phone too" (Android 13+).
- MP4 screen recording without re-encoding (Ctrl+Shift+R), with a REC timer.
- Phone card shows Android version and battery level.
- "More" menu on each phone card: send files, install APK, disconnect.
- Reconnect to the last phone when PhoneLink starts.
- `--selftest` now checks audio playback.

### Fixed
- Late audio data arriving after the player was stopped raised an error at shutdown.

## [1.0.0] - 2026-09-26

### Added
- Wireless ADB mirroring and control for Windows: own client for the scrcpy 4.1 server (video, touch, keyboard, clipboard, scroll).
- Automatic phone discovery (mDNS), pairing and connect from the UI, friendly error messages.
- Redesigned dark UI, quality presets, desktop mode, screenshots, full screen, drag-and-drop APK install and file transfer.
- Reconnect button after connection loss, logging, single-instance guard.
- Single-file `PhoneLink.exe` build, user guide.
