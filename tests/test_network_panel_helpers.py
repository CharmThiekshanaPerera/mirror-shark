from mirrorshark.devices_store import format_age


def test_format_age():
    assert format_age(None) == "never"
    assert format_age(10) == "just now"
    assert format_age(89) == "just now"
    assert format_age(90) == "1 min ago"
    assert format_age(125) == "2 min ago"
    assert format_age(3599) == "59 min ago"
    assert format_age(3600) == "1 h ago"
    assert format_age(3 * 3600 + 100) == "3 h ago"
    assert format_age(86399) == "23 h ago"
    assert format_age(86400) == "1 d ago"
    assert format_age(2 * 86400 + 10) == "2 d ago"
