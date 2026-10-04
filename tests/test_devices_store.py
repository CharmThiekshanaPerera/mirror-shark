from mirrorshark import devices_store as store


def test_upsert_and_load(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    d = store.upsert("C6:C3:CE:4E:10:F6", name="Pixel-7-Pro", last_ip="192.168.8.185", last_port=44529)
    assert d.mac == "c6:c3:ce:4e:10:f6" and d.name == "Pixel-7-Pro"
    loaded = store.load()
    assert "c6:c3:ce:4e:10:f6" in loaded
    assert loaded["c6:c3:ce:4e:10:f6"].last_port == 44529


def test_upsert_merges_without_erasing_with_blanks(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    store.upsert("aa:bb:cc:dd:ee:ff", name="Redmi-Note-9", last_ip="192.168.8.131", last_port=41239)
    store.upsert("aa:bb:cc:dd:ee:ff", name="", last_ip="192.168.8.131", last_port=0)  # a re-save with blanks
    d = store.load()["aa:bb:cc:dd:ee:ff"]
    assert d.name == "Redmi-Note-9" and d.last_port == 41239  # not clobbered


def test_remove(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    store.upsert("11:22:33:44:55:66", name="X")
    assert store.is_saved("11:22:33:44:55:66")
    store.remove("11:22:33:44:55:66")
    assert not store.is_saved("11:22:33:44:55:66")
    assert "11:22:33:44:55:66" not in store.load()


def test_mac_case_insensitive(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    store.upsert("AA:BB:CC:00:11:22", name="X")
    assert store.is_saved("aa:bb:cc:00:11:22")
    store.remove("AA:BB:CC:00:11:22")
    assert not store.is_saved("aa:bb:cc:00:11:22")


def test_empty_mac_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    assert store.upsert("") is None
    assert store.load() == {}
    store.remove("")  # must not raise
    assert not store.is_saved("")


def test_load_survives_corrupt_file(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    (tmp_path / "devices.json").write_text("{not valid json", encoding="utf-8")
    assert store.load() == {}


def test_persists_across_loads(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
    store.upsert("de:ad:be:ef:00:01", name="Phone A")
    store.upsert("de:ad:be:ef:00:02", name="Phone B")
    assert set(store.load()) == {"de:ad:be:ef:00:01", "de:ad:be:ef:00:02"}
