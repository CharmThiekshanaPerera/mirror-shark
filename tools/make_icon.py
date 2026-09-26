"""Generate assets/mirrorshark.ico from the icon drawn in mirrorshark.theme."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from mirrorshark.theme import make_pixmap  # noqa: E402

app = QGuiApplication([])
out = Path(__file__).resolve().parents[1] / "assets"
out.mkdir(exist_ok=True)
ok = make_pixmap(256).save(str(out / "mirrorshark.ico"), "ICO")
make_pixmap(512).save(str(out / "mirrorshark.png"), "PNG")
print("icon written" if ok else "ICO write failed")
sys.exit(0 if ok else 1)
