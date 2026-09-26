"""Small reusable widgets for the PhoneLink UI."""
from PySide6.QtCore import QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton,
                               QVBoxLayout, QWidget)

from .. import theme

STATE_TEXT = {
    "device": ("Connected", theme.GOOD),
    "offline": ("Offline", theme.WARN),
    "unauthorized": ("Not authorised", theme.WARN),
    "connecting": ("Connecting…", theme.MUTED),
}


class Badge(QLabel):
    def __init__(self, text: str = "", color: str = theme.MUTED):
        super().__init__()
        self.set(text, color)

    def set(self, text: str, color: str) -> None:
        self.setText(text)
        self.setStyleSheet(
            f"background: transparent; color: {color}; border: 1px solid {color}; border-radius: 9px;"
            "padding: 1px 9px; font-size: 11px;")


class DeviceRow(QFrame):
    """One phone: name, address, status badge and a Mirror button."""
    mirror_clicked = Signal(str)     # serial
    action_requested = Signal(str, str)  # serial, action: 'send' | 'install' | 'disconnect'

    def __init__(self, serial: str, name: str, subtitle: str, state: str):
        super().__init__()
        self.serial = serial
        self.setObjectName("deviceRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        icon = QLabel("📱")
        icon.setStyleSheet("font-size: 26px; background: transparent;")
        lay.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.name = QLabel(name)
        self.name.setObjectName("sectionTitle")
        self.sub = QLabel(subtitle)
        self.sub.setObjectName("muted")
        text.addWidget(self.name)
        text.addWidget(self.sub)
        lay.addLayout(text, 1)
        label, color = STATE_TEXT.get(state, (state, theme.MUTED))
        self.badge = Badge(label, color)
        lay.addWidget(self.badge)
        self.mirror_btn = QPushButton("Mirror")
        self.mirror_btn.setObjectName("primary")
        self.mirror_btn.setMinimumWidth(96)
        self.mirror_btn.setEnabled(state == "device")
        self.mirror_btn.clicked.connect(lambda: self.mirror_clicked.emit(self.serial))
        lay.addWidget(self.mirror_btn)
        more = QPushButton("More")
        menu = QMenu(more)
        menu.addAction("Send files to phone…", lambda: self.action_requested.emit(self.serial, "send"))
        menu.addAction("Install APK…", lambda: self.action_requested.emit(self.serial, "install"))
        if ":" in serial or serial.startswith("adb-"):  # wireless devices can be disconnected
            menu.addSeparator()
            menu.addAction("Disconnect", lambda: self.action_requested.emit(self.serial, "disconnect"))
        more.setMenu(menu)
        more.setEnabled(state == "device")
        lay.addWidget(more)


class Collapsible(QWidget):
    """A header button that shows/hides a body widget."""

    def __init__(self, title: str, body: QWidget, expanded: bool = False):
        super().__init__()
        self.button = QToolButton()
        self.button.setText(f"  {title}")
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.button.setStyleSheet("QToolButton { border: none; background: transparent; font-weight: 600; "
                                  "font-size: 14px; text-align: left; padding: 6px 0; }")
        self.button.toggled.connect(self._toggle)
        self.body = body
        self.body.setVisible(expanded)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(self.button)
        lay.addWidget(self.body)

    def _toggle(self, on: bool) -> None:
        self.button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)

    def set_expanded(self, on: bool) -> None:
        self.button.setChecked(on)


class Toast(QLabel):
    """Short-lived message shown over a parent widget."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"background: {theme.SURFACE_2}; color: {theme.TEXT}; border: 1px solid {theme.BORDER};"
                           "border-radius: 8px; padding: 8px 14px;")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(400)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade)
        self.hide()

    def show_message(self, text: str, ms: int = 2200) -> None:
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        self.move(max(8, (p.width() - self.width()) // 2), max(8, p.height() - self.height() - 24))
        self._anim.stop()
        self._effect.setOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(ms)

    def _fade(self) -> None:
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()
