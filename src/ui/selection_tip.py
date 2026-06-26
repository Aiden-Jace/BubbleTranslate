import sys

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from src.resources import resource_path


class SelectionTranslateTip(QWidget):
    """显示在选区附近的轻量翻译入口。"""

    translate_requested = Signal(str)

    def __init__(self):
        super().__init__()
        flags = (
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        if sys.platform == "darwin":
            flags |= Qt.NoDropShadowWindowHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._text = ""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(5000)
        self._hide_timer.timeout.connect(self.hide)

        self.button = QPushButton(self)
        self.button.setToolTip("翻译选中文本")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setIcon(QIcon(resource_path("assets", "logo.png")))
        self.button.setIconSize(QSize(25, 25))
        self.button.setFixedSize(38, 38)
        self.button.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 248);
                border: 1px solid rgba(91, 101, 124, 80);
                border-radius: 8px;
                padding: 5px;
            }
            QPushButton:hover {
                background: white;
                border-color: #5169ff;
            }
            QPushButton:pressed {
                background: #eef1ff;
            }
        """)
        self.button.clicked.connect(self._request_translation)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.button)
        self.setFixedSize(42, 42)

    def show_for_text(self, text, global_position):
        self._text = text.strip()
        if not self._text:
            self.hide()
            return

        position = QPoint(global_position) + QPoint(10, 10)
        screen = QApplication.screenAt(global_position)
        if screen is None:
            screen = QApplication.primaryScreen()
        available = screen.availableGeometry()
        position.setX(
            max(
                available.left(),
                min(position.x(), available.right() - self.width() + 1),
            )
        )
        position.setY(
            max(
                available.top(),
                min(position.y(), available.bottom() - self.height() + 1),
            )
        )

        self.move(position)
        self.show()
        self.raise_()
        self._hide_timer.start()

    def contains_global_point(self, point):
        return self.isVisible() and self.geometry().contains(point)

    def hideEvent(self, event):
        self._hide_timer.stop()
        super().hideEvent(event)

    def _request_translation(self):
        text = self._text
        self.hide()
        if text:
            self.translate_requested.emit(text)
