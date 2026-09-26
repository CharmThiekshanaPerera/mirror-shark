# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security > Report a vulnerability** on this repository. Do not open a public issue for them. You will get a reply as soon as possible.

## Scope and things to know

- Mirror Shark talks only to devices on your local network through ADB. It does not contact the internet and collects no data.
- Pairing gives the PC permission to control the phone. Turn Wireless debugging off when you are not using it, especially on public networks, and remove paired computers in Developer options if you no longer trust them.
- **Mirror Shark Helper (phone app).** It listens on the local network and can switch on Wireless debugging, but only after the phone's owner taps Accept on a notification that names the requesting computer. It never accepts on its own, requests time out after 60 seconds, and repeated declines trigger a cool-down. It needs the WRITE_SECURE_SETTINGS permission, which Mirror Shark grants once over ADB. Do not accept requests you did not start. Switch the helper off in its app or uninstall it to remove the capability.
- The release exe is not code-signed. Only download releases from this repository's Releases page and compare the file size or hash if you need to be sure.
- Bundled tools (`adb`, the scrcpy server) come from their official releases. Report vulnerabilities in those projects to their maintainers.
