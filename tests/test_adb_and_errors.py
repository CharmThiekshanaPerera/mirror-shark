from mirrorshark.adb import Adb
from mirrorshark.errors import friendly


class FakeAdb(Adb):
    def __init__(self, outputs):
        self.exe = "adb"
        self._outputs = outputs

    def run(self, *args, serial=None, timeout=30):
        return self._outputs[args]


def test_devices_parsing():
    out = ("List of devices attached\n"
           "* daemon started successfully\n"
           "192.168.1.5:37361\tdevice product:cheetah model:Pixel_7_Pro\n"
           "R58M\tunauthorized\n")
    a = FakeAdb({("devices", "-l"): out.replace("\t", " ")})
    devs = a.devices()
    assert [(d.serial, d.state) for d in devs] == [("192.168.1.5:37361", "device"), ("R58M", "unauthorized")]


def test_mdns_parsing():
    out = ("List of discovered mdns services\n"
           "adb-ABC-xyz\t_adb-tls-connect._tcp\t192.168.1.5:37361\n"
           "adb-ABC-pair\t_adb-tls-pairing._tcp.\t192.168.1.5:41000\n")
    a = FakeAdb({("mdns", "services"): out})
    svc = a.mdns_services()
    assert [(s.kind, s.address) for s in svc] == [("connect", "192.168.1.5:37361"), ("pairing", "192.168.1.5:41000")]


def test_model_name_dedupes_brand():
    a = FakeAdb({("shell", "getprop ro.product.manufacturer"): "Google\n",
                 ("shell", "getprop ro.product.model"): "Pixel 7 Pro\n"})
    assert a.model_name("x") == "Google Pixel 7 Pro"
    b = FakeAdb({("shell", "getprop ro.product.manufacturer"): "samsung\n",
                 ("shell", "getprop ro.product.model"): "samsung SM-S911B\n"})
    assert b.model_name("x") == "samsung SM-S911B"


def test_friendly_errors():
    assert "refused" in friendly("failed to connect: 10061 actively refused").lower()
    assert "unlock the phone" in friendly("device unauthorized").lower()
    assert friendly("something odd") == "something odd"
    assert friendly("") == "Unknown error"
