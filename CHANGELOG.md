# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/), versions follow [SemVer](https://semver.org/).

## [1.7.0] - 2026-09-26

### Added
- **Request screen share**: one button on a phone that is not connected. It sends the phone a request ("<PC> wants to share your screen"); when the owner taps **Accept**, Wireless debugging is switched on, Mirror Shark connects to the phone and opens its mirror window with full control, all without further clicks (if the phone was paired before).
- The button is shown for every phone-like device whose wireless debugging is off. On a phone that does not have Mirror Shark Helper yet it explains the one-time setup instead of doing nothing.

### Changed
- The "Ask phone to turn on" button became **Request screen share**, and its texts and the phone's notification now speak about sharing the screen.
- Mirror Shark Helper 1.1: the request notification says what accepting does.

### Fixed
- **Connecting to a phone that was never paired** showed "Could not reach the phone" while the row kept saying "Wireless debugging ON". Mirror Shark now recognises this case (the phone answers but rejects this PC's key, which ADB only reports as "failed to connect"): the row shows **Not paired**, explains what to do, and has a **Pair…** button that asks for the pairing address (filled in automatically when the phone's pairing screen is open) and the 6-digit code, then connects.
- Phones that advertise an unreachable internal address over mDNS (for example `10.0.2.x`) no longer appear as a "Found on network" connect suggestion.
- The APK signature side file (`.idsig`) is no longer generated or tracked in the repository.

## [1.6.0] - 2026-09-26

### Added
- **Ask a phone to turn on Wireless debugging.** For phones that have the new **Mirror Shark Helper** app, the *Devices on your Wi-Fi* list shows a "Helper ready" tag and an **Ask phone to turn on** button. The phone shows a notification ("<PC> wants to turn on Wireless debugging: Accept / Decline"). Only when its owner taps **Accept** does Wireless debugging switch on; Mirror Shark then finds the phone and connects to it automatically (if it was paired before). Declines back off (30 s, then 5 min after three in a row), and unanswered requests time out after 60 s.
- **Mirror Shark Helper** Android app (source in `android-helper/`, built with `tools/build_helper.py`, bundled inside `MirrorShark.exe` and in the release zip). It runs a small listener on the local network and holds the permission to switch the setting on.
- **Set up phone helper** in the *More* menu of a connected phone: installs the helper over ADB, gives it the permission and starts it.

### Security notes
- Nothing is changed without a tap on the phone. The helper never accepts on its own, and unanswered requests time out.
- Android does not let a computer switch Wireless debugging on by itself, which is why the helper app and its one-time setup are needed.

## [1.5.0] - 2026-09-26

### Changed
- **Devices on your Wi-Fi is now part of the dashboard.** The main window shows every device on your network, always visible below *Your phones*. It scans on startup and refreshes itself every 90 seconds, checks phones for wireless debugging automatically, and lets you Connect, Check, or Mirror straight from a device's row. The separate scan window was removed.
- A phone that is connected already shows **Connected** with a **Mirror** button in the Wi-Fi list.
- Optional auto-connect: if exactly one phone has wireless debugging on and nothing is connected, Mirror Shark connects to it.

### Fixed
- The same phone could appear twice in *Your phones* (once by IP, once by its discovery name), and the "phones ready" count was wrong. It is now one card per physical phone.

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
