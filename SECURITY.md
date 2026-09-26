# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security > Report a vulnerability** on this repository. Do not open a public issue for them. You will get a reply as soon as possible.

## Scope and things to know

- PhoneLink talks only to devices on your local network through ADB. It does not contact the internet and collects no data.
- Pairing gives the PC permission to control the phone. Turn Wireless debugging off when you are not using it, especially on public networks, and remove paired computers in Developer options if you no longer trust them.
- The release exe is not code-signed. Only download releases from this repository's Releases page and compare the file size or hash if you need to be sure.
- Bundled tools (`adb`, the scrcpy server) come from their official releases. Report vulnerabilities in those projects to their maintainers.
