import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from src.ui.selection_tip import SelectionTranslateTip


class SelectionTranslateTipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_tip_emits_stored_text(self):
        tip = SelectionTranslateTip()
        translated = []
        tip.translate_requested.connect(translated.append)

        tip.show_for_text("selected", QPoint(20, 20))
        self.app.processEvents()
        self.assertTrue(tip.isVisible())
        self.assertTrue(tip.contains_global_point(tip.geometry().center()))

        tip.button.click()

        self.assertEqual(translated, ["selected"])
        self.assertFalse(tip.isVisible())


if __name__ == "__main__":
    unittest.main()
