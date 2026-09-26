# Mirror Shark User Guide

Mirror Shark shows your Android phone's screen on your Windows PC and lets you control it with the mouse and keyboard, over Wi-Fi. It also plays the phone's sound on the PC, records the screen, and moves files and apps to the phone. No cable is needed after the one-time pairing.

## What you need

- A Windows 10 or 11 PC (64-bit).
- An Android phone running **Android 11 or newer**. Wireless debugging was added in Android 11.
- The phone and the PC on the **same Wi-Fi network**. You can also connect the PC to the phone's hotspot.

Mirror Shark is a single file, `MirrorShark.exe`. There is nothing to install and you do not need to install ADB or any other tool.

## First-time setup (about 2 minutes)

### 1. Turn on Developer options on the phone

1. Open **Settings > About phone**.
2. Tap **Build number** 7 times. You will see "You are now a developer".

### 2. Turn on Wireless debugging

1. Open **Settings > System > Developer options**.
2. Turn on **Wireless debugging**. If Android asks "Allow wireless debugging on this network?", tap **Allow**.

### 3. Pair the phone with the PC (once)

1. On the phone, tap **Wireless debugging** to open its screen, then tap **Pair device with pairing code**. Keep this screen open. It shows an **IP address and port** and a **6-digit code**.
2. On the PC, open Mirror Shark. Under **Connect a new phone**, go to **Step 1 - Pair**.
   - If Mirror Shark finds the phone, a "Found on network" button fills in the address for you.
   - Otherwise type the IP address and port shown on the phone.
3. Type the 6-digit code and click **Pair**. You should see "Paired successfully".

> The pairing port and the code change every time the pairing screen is opened. If pairing fails, tap **Pair device with pairing code** again on the phone and use the new values.

### 4. Connect

1. Go back one screen on the phone so that you see the main **Wireless debugging** screen. It shows **IP address & Port**. This port is *different* from the pairing port.
2. In Mirror Shark, under **Step 2 - Connect**, click the "Found on network" button (or type the address) and click **Connect**. If nothing is found on its own, use the **Devices on your Wi-Fi** list in the dashboard instead (see below).
3. Your phone now appears under **Your phones** with a green **Connected** badge.

### Devices on your Wi-Fi (in the dashboard)

The main window always shows **Devices on your Wi-Fi** under *Your phones*. It lists every device on your network so you can see what is there and connect to a phone without knowing its IP address or port. It works even where automatic phone discovery is blocked (some routers and phone hotspots).

Each device shows its name, IP address, MAC address and a guess at what it is (📱 phone or tablet, 📡 router, 💻 computer, 📺 TV, 🖨 printer), plus your own PC. The list scans when Mirror Shark starts and refreshes every 90 seconds; press **Refresh** to scan right now. Phones are checked automatically. The badge tells you the result:

- **Wireless debugging ON**: press **Connect**. If it is the only such phone and *Connect automatically* is ticked, Mirror Shark connects for you.
- **Connected**: already connected. Press **Mirror** right there.
- **Debugging off**: the device is on your network but Wireless debugging is off or unreachable. Turn it on (Settings › System › Developer options › Wireless debugging, stay on that screen) and press **Check again**.
- **Not checked**: routers and other devices are only checked when you press **Check** (about 20 seconds each). **Check all** checks everything.

Tick **Check every port** if a phone that has Wireless debugging on is not found (slower).

If a phone shows **ON** but connecting fails with a message about pairing, it has not been paired with this PC yet. Do **Step 1 - Pair** once, then connect again.

Only your own local network is scanned, and only the ADB service is checked. Phones that use a private (random) Wi-Fi address may show without a name.

### Turning on Wireless debugging from the PC (Mirror Shark Helper)

Android does not allow a computer to switch Wireless debugging on by itself. To make it easy anyway, Mirror Shark has a small companion app for the phone, **Mirror Shark Helper**. With it you can ask a phone to turn Wireless debugging on, and the phone's owner just taps **Accept**.

**One-time setup per phone**
1. Connect the phone the normal way (Wireless debugging on, or by USB cable).
2. In *Your phones*, open **More** on the phone's card and choose **Set up phone helper...**. Mirror Shark installs the helper, gives it the permission to switch Wireless debugging on, and starts it.
3. On the phone, allow notifications if Android asks.

**Later, when Wireless debugging is off** (after a restart, or on a new Wi-Fi network)
1. Open Mirror Shark. In **Devices on your Wi-Fi** the phone shows a green **Helper ready** tag and a **Debugging off** badge.
2. Press **Ask phone to turn on**.
3. The phone shows a notification: *"<your PC> wants to turn on Wireless debugging"* with **Accept** and **Decline**. Tap **Accept**.
4. Wireless debugging switches on, Mirror Shark finds the phone and connects (if it was paired before). If Android asks "Allow wireless debugging on this network?", tap **Allow**. Then press **Mirror**.

**Good to know**
- The phone always asks. Nothing is switched on without a tap, and an unanswered request times out after 60 seconds.
- If a request is declined, the phone ignores new requests for 30 seconds (5 minutes after three declines in a row), so a stranger's device on the Wi-Fi cannot keep prompting you.
- Only accept requests from your own computer. The notification shows the computer's name and address.
- The helper shows a small "Mirror Shark Helper is on" notification while it waits. Open the app on the phone to switch it off, or uninstall it any time.
- A phone that has never had the helper installed cannot be asked remotely. Turn Wireless debugging on by hand once (or connect it by cable) and run **Set up phone helper**.
- The helper only listens on your local network. You need to pair the phone with this PC once, as usual, before Mirror Shark can connect to it.

## Everyday use

1. Make sure Wireless debugging is on and the phone is on the same network as the PC.
2. Open Mirror Shark. Your phone appears in **Your phones** automatically (this can take a few seconds).
3. Click **Mirror**. A window with your phone screen opens.

You only need to pair once per network. If the phone does not appear on its own after a reboot, use **Connect a new phone > Step 2 - Connect**.

## Controlling the phone

| Action | How |
|---|---|
| Tap | Left-click |
| Swipe / drag | Hold the left button and move |
| Scroll | Mouse wheel |
| Back | Right-click, **Esc**, or the ◀ button |
| Home | Middle-click, **Ctrl+H**, or the ⬤ button |
| Recent apps | **Ctrl+S** or the ▣ button |
| Type text | Just type on your keyboard while the mirror window is focused |
| Power button | **Ctrl+P** or the ⏻ button |
| Notifications | **Ctrl+N** or the 🔔 button |
| Rotate | **Ctrl+R** or the ⟳ button |
| Turn the phone screen off/on | **Ctrl+O** or the ☾ button (mirroring keeps working) |
| Screenshot | **Ctrl+Shift+S** or the 📷 button (saved in *Pictures\MirrorShark*) |
| Record the screen | **Ctrl+Shift+R** or the ⏺ button. Press again to stop. The MP4 is saved in *Videos\MirrorShark* |
| Mute the phone's sound on the PC | **Ctrl+M** or the 🔈 button |
| Full screen | **F11** or the ⛶ button |
| Paste PC clipboard on the phone | **Ctrl+V** |

Copying text on the phone puts it on your PC clipboard, and your PC clipboard is sent to the phone when you click into the mirror window.

**Sound:** the phone's audio plays on your PC (Android 11 or newer). While you mirror, the phone itself is silent unless you tick "Keep the sound playing on the phone as well" in Settings (Android 13 or newer). Some apps block audio capture, and they stay silent.

**Recording:** recordings contain the screen only (no sound) and are stored without re-encoding, so they cost almost no CPU. While recording, a red **REC** timer shows next to the buttons. Long recordings of a busy screen use roughly 5 to 10 MB per minute.

**Phone details:** each phone card shows the Android version and the battery level (with a ⚡ while charging).

**Drag and drop:** drop an `.apk` file on the window to install it, or any other file to send it to the phone's **Download** folder.

You can also use **More** on a phone card: **Send files to phone...** puts files in the phone's *Download* folder, **Install APK...** installs an app, and **Disconnect** releases the phone.

Click the **?** button in the mirror window at any time to see the shortcuts.

## Settings

Open **Settings** on the main window.

- **Quality**
  - *Balanced (recommended)*: good picture, works on most networks.
  - *Sharp*: higher resolution and bitrate. Best on a fast 5 GHz Wi-Fi.
  - *Smooth / low latency*: lower resolution for the quickest response.
  - *Data saver*: for slow or busy networks.
  - *Custom*: set maximum resolution, bitrate and frame rate yourself.
- **Play the phone's sound on this PC**: turn this off if you only want the picture.
- **Reconnect to the last phone when Mirror Shark starts**: Mirror Shark tries the last address you connected to.
- **Turn the phone screen off while mirroring**: saves battery and keeps the phone private while you use it from the PC.
- **Keep the phone awake**: prevents the phone from sleeping while it is charging.
- **Keep the mirror window on top**: the window stays above other windows.
- **Desktop mode**: opens a separate desktop-style display on the phone (for example `1920x1080/240` is width x height / screen density) instead of copying the phone screen. It works best on Android 14 or newer and depends on the phone maker.

Your choices are remembered.

## Troubleshooting

| Problem | What to try |
|---|---|
| No phone appears | Look at **Devices on your Wi-Fi** in the dashboard to see everything on your network. Also check that Wireless debugging is **on**, the phone and PC are on the same network, and the phone screen is awake. Click **Refresh**. Some public or guest Wi-Fi networks block device-to-device traffic. Use the phone's hotspot instead. |
| "Connection refused" | The port changed. Read the current IP:port on the phone's Wireless debugging screen and connect again. |
| Pairing fails | Open **Pair device with pairing code** again and use the new port and code. Enter the code quickly. |
| Phone shows "Not authorised" or "Offline" | Unlock the phone and tap **Allow**. Otherwise turn Wireless debugging off and on, then connect again. |
| Picture is laggy or blurry | Move closer to the router, use 5 GHz Wi-Fi, or change **Quality** in Settings. |
| "Connection to the phone was lost" | Wake the phone, make sure it is still on the network, then click **Reconnect** in the mirror window. |
| No sound from the phone | Needs Android 11 or newer and "Play the phone's sound" ticked in Settings. Check the 🔈 button is not muted, the PC volume is up, and the app is not blocking audio capture. Restart mirroring after changing the setting. |
| The phone screen is black in the window | A secure screen (banking apps, some video apps) blocks mirroring by design. |
| A key does not type | Click inside the mirror window first so that it has the keyboard focus. |
| Everything worked, then stopped after moving to another network | Wireless debugging must be turned on again and the phone re-paired on the new network. |

If something else goes wrong, open **Help > Open log folder** and send the `mirrorshark.log` file to whoever supports you.

## Privacy and safety

- Mirror Shark works only on your local network. Nothing is sent to the internet.
- Pairing gives this PC permission to control the phone. To remove that permission, go to **Settings > System > Developer options > Wireless debugging** and remove the PC from the list of paired devices, or choose **Revoke USB debugging authorizations** in Developer options.
- Turn Wireless debugging off when you are not using it, especially on public networks.

## Where Mirror Shark keeps its files

- Settings: Windows registry under `HKEY_CURRENT_USER\Software\MirrorShark`.
- Logs and helper tools: `%LOCALAPPDATA%\MirrorShark`.
- Screenshots: `Pictures\MirrorShark`.

To remove Mirror Shark, delete `MirrorShark.exe` and the `%LOCALAPPDATA%\MirrorShark` folder.

## Credits

Mirror Shark uses the open-source [scrcpy](https://github.com/Genymobile/scrcpy) server (Apache License 2.0) and the Android SDK Platform-Tools (`adb`).
