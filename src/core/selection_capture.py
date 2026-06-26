import sys

from PySide6.QtCore import QObject, QMimeData, QTimer
from PySide6.QtWidgets import QApplication


class ClipboardSelectionReader(QObject):
    """通过模拟复制异步读取选中文本，并完整恢复剪贴板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._callback = None
        self._backup = None
        self._attempts = 0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._poll_clipboard)

    @property
    def is_active(self):
        return self._timer.isActive()

    def capture(self, callback):
        self.cancel()
        self._callback = callback
        self._attempts = 0
        self._backup = self._clone_mime_data(
            QApplication.clipboard().mimeData()
        )

        clipboard = QApplication.clipboard()
        clipboard.clear()
        QApplication.processEvents()

        try:
            self._simulate_copy()
        except Exception as error:
            print(f"[Selection] 模拟复制失败: {error}")
            self._finish("")
            return

        self._timer.start()

    def cancel(self):
        if self._timer.isActive():
            self._timer.stop()
        if self._backup is not None:
            self._restore_clipboard()
        self._callback = None
        self._attempts = 0

    def _poll_clipboard(self):
        self._attempts += 1
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        selected_text = (
            ""
            if mime_data.hasUrls()
            else clipboard.text().strip()
        )
        if selected_text:
            self._finish(selected_text)
        elif self._attempts >= 12:
            self._finish("")

    def _finish(self, selected_text):
        self._timer.stop()
        self._restore_clipboard()
        callback = self._callback
        self._callback = None
        if callback:
            callback(selected_text)

    def _restore_clipboard(self):
        backup = self._backup
        self._backup = None
        if backup is not None:
            QApplication.clipboard().setMimeData(backup)
            QApplication.processEvents()

    @staticmethod
    def _clone_mime_data(source):
        clone = QMimeData()
        for mime_format in source.formats():
            clone.setData(mime_format, source.data(mime_format))
        return clone

    @staticmethod
    def _simulate_copy():
        from pynput.keyboard import Controller, Key

        keyboard = Controller()
        modifier = Key.cmd if sys.platform == "darwin" else Key.ctrl
        with keyboard.pressed(modifier):
            keyboard.press("c")
            keyboard.release("c")
