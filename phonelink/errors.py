"""Turn raw adb/scrcpy failures into messages a non-technical user can act on."""

_RULES = [
    (("10061", "actively refused", "connection refused"),
     "The phone refused the connection. Check that Wireless debugging is still ON and that the port matches "
     "the one shown on the phone (it changes every time Wireless debugging is toggled)."),
    (("10060", "timed out", "timeout"),
     "The phone did not answer. Make sure the phone and this PC are on the same Wi-Fi (or the phone's hotspot) "
     "and that the phone screen is awake."),
    (("unauthorized",),
     "The phone has not authorised this PC. Unlock the phone and tap Allow on the 'Allow wireless debugging' prompt."),
    (("failed to authenticate", "protocol fault", "unable to authenticate"),
     "Authentication failed. Pair the phone again: Wireless debugging > Pair device with pairing code."),
    (("wrong password", "pairing code", "failed: "),
     "Pairing failed. The 6-digit code and the pairing IP:port change every time the pairing screen opens - "
     "re-open 'Pair device with pairing code' on the phone and enter the new values."),
    (("more than one device",),
     "More than one device is connected. Select the phone you want in the list."),
    (("offline",),
     "The phone shows as offline. Toggle Wireless debugging off and on, then press Refresh."),
    (("device not found", "no devices"),
     "The phone is no longer connected. Reconnect it from the 'Connect a phone' section."),
    (("exited early",),
     "The mirroring service on the phone stopped right after starting. Unlock the phone, keep Wireless debugging on "
     "and try again. Details are in the log (Help > Open log)."),
    (("timed out waiting for the scrcpy server",),
     "The phone did not start the mirroring service in time. Unlock the phone and try again."),
    (("cannot connect", "failed to connect", "no route", "unreachable"),
     "Could not reach the phone. Check the IP address and port, and that both devices share the same network."),
]


def friendly(message: str) -> str:
    """Return a helpful explanation for a raw error message, followed by the original text."""
    low = (message or "").lower()
    for needles, text in _RULES:
        if any(n in low for n in needles):
            return f"{text}\n\nDetails: {message.strip()}"
    return message.strip() or "Unknown error"
