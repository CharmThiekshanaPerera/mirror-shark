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
    """Draw the app icon: a shark fin cutting through the water, mirrored in its own reflection."""
    import math

    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = float(size)

    tile = QPainterPath()
    tile.addRoundedRect(QRectF(s * .04, s * .04, s * .92, s * .92), s * .22, s * .22)
    bg = QLinearGradient(0, 0, 0, s)
    bg.setColorAt(0.0, QColor("#0a2350"))
    bg.setColorAt(0.55, QColor("#0d5a8c"))
    bg.setColorAt(1.0, QColor("#1bbcc9"))
    p.fillPath(tile, bg)
    p.setClipPath(tile)

    # mirror glint (two soft diagonal streaks)
    p.setPen(QPen(QColor(255, 255, 255, 34), s * .07, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(int(s * .06), int(s * .50), int(s * .50), int(s * .06))
    p.setPen(QPen(QColor(255, 255, 255, 20), s * .035, Qt.SolidLine, Qt.FlatCap))
    p.drawLine(int(s * .06), int(s * .64), int(s * .64), int(s * .06))

    wy = s * .56  # waterline

    def fin(flip: bool = False) -> QPainterPath:
        def pt(x, y):
            return (x * s, (2 * wy - y * s) if flip else y * s)
        path = QPainterPath()
        # dorsal fin: convex leading edge, tip leaning back, deeply concave trailing edge
        path.moveTo(*pt(.24, .56))
        path.cubicTo(*pt(.30, .36), *pt(.43, .21), *pt(.58, .11))
        path.cubicTo(*pt(.49, .29), *pt(.57, .44), *pt(.66, .56))
        path.closeSubpath()
        # tail tip, a little further back
        path.moveTo(*pt(.74, .56))
        path.cubicTo(*pt(.78, .49), *pt(.83, .42), *pt(.89, .35))
        path.cubicTo(*pt(.85, .45), *pt(.85, .51), *pt(.86, .56))
        path.closeSubpath()
        return path

    # reflection: the fin flipped below the waterline, cut into fading ripple bands
    bands = 7
    band_h = (s - wy) / bands
    for i in range(bands):
        top = wy + i * band_h
        p.save()
        p.setClipRect(QRectF(0, top + band_h * .12, s, band_h * .76), Qt.IntersectClip)
        p.translate(math.sin(i * 1.4) * s * .018 * (0.4 + i / bands), 0)
        p.fillPath(fin(flip=True), QColor(255, 255, 255, int(150 * (1 - i / bands))))
        p.restore()

    # the fin itself
    p.fillPath(fin(), QColor("white"))

    # waterline with a gentle wave
    wave = QPainterPath()
    wave.moveTo(s * .10, wy)
    x = s * .10
    step = s * .10
    up = True
    while x < s * .90 - 1:
        wave.quadTo(x + step / 2, wy + (-s * .012 if up else s * .012), x + step, wy)
        x += step
        up = not up
    p.setPen(QPen(QColor(255, 255, 255, 235), s * .022, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    p.drawPath(wave)
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
