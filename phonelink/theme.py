"""Dark theme and generated application icon."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication

BG = "#0f1115"
SURFACE = "#171a21"
SURFACE_2 = "#1f232c"
BORDER = "#2a2f3a"
TEXT = "#e8eaf0"
MUTED = "#8b93a5"
ACCENT = "#4c8dff"
ACCENT_HOVER = "#6aa1ff"
GOOD = "#3ecf8e"
WARN = "#f5a524"
BAD = "#f2545b"

STYLESHEET = f"""
* {{ font-family: "Segoe UI", "Segoe UI Variable", sans-serif; font-size: 13px; color: {TEXT}; }}
QWidget {{ background: {BG}; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 22px; font-weight: 600; }}
QLabel#subtitle, QLabel#muted {{ color: {MUTED}; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; }}
QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#card QLabel {{ background: transparent; }}
QFrame#deviceRow {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#deviceRow:hover {{ border-color: {ACCENT}; }}
QLineEdit, QComboBox, QSpinBox {{
  background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 10px;
  selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; }}
QPushButton {{
  background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 16px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {SURFACE_2}; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: {SURFACE_2}; color: {MUTED}; }}
QPushButton#link {{ background: transparent; border: none; color: {ACCENT}; padding: 4px 6px; text-align: left; }}
QPushButton#link:hover {{ color: {ACCENT_HOVER}; }}
QPushButton#chip {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 12px; padding: 4px 12px; }}
QPushButton#chip:hover {{ border-color: {GOOD}; }}
QPushButton#tool {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 0; font-size: 15px; }}
QPushButton#tool:hover {{ border-color: {ACCENT}; background: {SURFACE_2}; }}
QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {BORDER}; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {MUTED}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QPlainTextEdit, QTextBrowser {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 8px; }}
QStatusBar {{ background: {SURFACE}; color: {MUTED}; }}
QMessageBox {{ background: {BG}; }}
"""


def make_pixmap(size: int = 256) -> QPixmap:
    """Draw the app icon: a rounded gradient tile with a phone and mirror waves."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size
    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0, QColor("#5b9bff"))
    grad.setColorAt(1, QColor("#7a4dff"))
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(s * .04, s * .04, s * .92, s * .92), s * .22, s * .22)
    p.fillPath(tile, grad)
    # phone body
    body = QRectF(s * .34, s * .18, s * .32, s * .64)
    p.setPen(QPen(QColor("white"), s * .035))
    p.setBrush(QColor(255, 255, 255, 40))
    p.drawRoundedRect(body, s * .06, s * .06)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawRoundedRect(QRectF(s * .45, s * .21, s * .10, s * .014), s * .007, s * .007)
    # mirror waves
    p.setBrush(Qt.NoBrush)
    for i, r in enumerate((.10, .16)):
        pen = QPen(QColor(255, 255, 255, 230 - i * 70), s * .028, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        rect = QRectF(s * .66 - s * r, s * .5 - s * r, s * r * 2, s * r * 2)
        p.drawArc(rect, -45 * 16, 90 * 16)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(size))
    return icon


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())
