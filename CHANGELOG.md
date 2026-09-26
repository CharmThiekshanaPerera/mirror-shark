# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/), versions follow [SemVer](https://semver.org/).

## [1.4.0] - 2026-09-26

### Added
- **Devices on my Wi-Fi**: the scan window now lists *every* device on your network, not only phones with wireless debugging on. Each shows its name, IP and MAC address, a guess at its type (phone, router, computer, TV, printer) and whether wireless debugging is on. Phone-like devices are checked automatically, any device can be checked with one click, and already-connected phones are marked. Devices with debugging off show how to turn it on.
- Devices that announce themselves (mDNS) are shown as ready instantly, without a port scan.

### Changed
- The buttons are now "Devices on Wi-Fi" and "Show devices on my Wi-Fi".

## [1.3.0] - 2026-09-26

### Added
- **Scan network**: finds phones with Wireless debugging turned on without needing the IP or port, and connects to them. Useful when automatic discovery (mDNS) is blocked, for example on hotspots and some routers. It sweeps the local network, probes Android's port range on each device (phone-like devices first) and confirms the port with the ADB handshake. Options: connect automatically, scan all devices, deep scan (all ports).
- Scan buttons in *Connect a new phone* and in the empty "no phone found" state.

## [1.2.0] - 2026-09-26

### Changed
- The app is now called **Mirror Shark** (formerly PhoneLink), with a new shark-fin-and-mirror logo. The exe is `MirrorShark.exe`, and settings, logs and screenshots use `MirrorShark` folders. Old `PhoneLink` settings are not migrated (paired phones are unaffected).

## [1.1.2] - 2026-09-26

### Fixed
- Release zip now includes the Apache-2.0 license text (scrcpy, Platform-Tools) alongside the notices.

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
- Reconnect to the last phone when Mirror Shark starts.
- `--selftest` now checks audio playback.

### Fixed
- Late audio data arriving after the player was stopped raised an error at shutdown.

## [1.0.0] - 2026-09-26

### Added
- Wireless ADB mirroring and control for Windows: own client for the scrcpy 4.1 server (video, touch, keyboard, clipboard, scroll).
- Automatic phone discovery (mDNS), pairing and connect from the UI, friendly error messages.
- Redesigned dark UI, quality presets, desktop mode, screenshots, full screen, drag-and-drop APK install and file transfer.
- Reconnect button after connection loss, logging, single-instance guard.
- Single-file `MirrorShark.exe` build, user guide.
