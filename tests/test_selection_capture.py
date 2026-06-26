import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication

from src.core.selection_capture import ClipboardSelectionReader


class ClipboardSelectionReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_capture_restores_clipboard(self):
        class MemoryClipboard:
            def __init__(self):
                self._mime_data = QMimeData()

            def mimeData(self):
                return self._mime_data

            def clear(self):
                self._mime_data = QMimeData()

            def text(self):
                return self._mime_data.text()

            def setText(self, text):
                mime_data = QMimeData()
                mime_data.setText(text)
                self._mime_data = mime_data

            def setMimeData(self, mime_data):
                self._mime_data = mime_data

        clipboard = MemoryClipboard()
        clipboard.setText("original")
        captured = []
        reader = ClipboardSelectionReader()

        def simulate_copy():
            clipboard.setText("selected")

        with (
            patch(
                "src.core.selection_capture.QApplication.clipboard",
                return_value=clipboard,
            ),
            patch.object(reader, "_simulate_copy", side_effect=simulate_copy),
        ):
            reader.capture(captured.append)
            reader._poll_clipboard()

        self.assertEqual(captured, ["selected"])
        self.assertEqual(clipboard.text(), "original")
        self.assertFalse(reader.is_active)

    def test_file_url_clipboard_is_not_treated_as_text_selection(self):
        class UrlClipboard:
            def __init__(self):
                self._mime_data = QMimeData()
                self._mime_data.setUrls([])

            def mimeData(self):
                return self._mime_data

            def text(self):
                return "C:/example.txt"

        clipboard = UrlClipboard()
        clipboard._mime_data.setData(
            "text/uri-list",
            b"file:///C:/example.txt",
        )
        captured = []
        reader = ClipboardSelectionReader()
        reader._callback = captured.append
        reader._backup = None
        reader._attempts = 11

        with patch(
            "src.core.selection_capture.QApplication.clipboard",
            return_value=clipboard,
        ):
            reader._poll_clipboard()

        self.assertEqual(captured, [""])


if __name__ == "__main__":
    unittest.main()
