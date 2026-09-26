"""In-app help: renders the bundled user guide."""
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout

from .. import APP_NAME, __version__
from ..resources import find_resource

FALLBACK = """# Quick start
1. On the phone: **Settings > System > Developer options > Wireless debugging** - turn it on.
2. First time only: tap **Pair device with pairing code** and enter the IP:port and 6-digit code under
   *Connect a new phone > Pair*.
3. Your phone appears under *Your phones*. Click **Mirror**.
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} {__version__} - User guide")
        self.resize(760, 640)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        guide = find_resource("docs/USER_GUIDE.md")
        text = guide.read_text(encoding="utf-8") if guide else FALLBACK
        view.setMarkdown(text)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addWidget(view)
        lay.addLayout(row)
