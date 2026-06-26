import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.bubble import TranslationBubble


class TranslationBubbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bubble_menu_visibility_follows_setting(self):
        with patch("src.ui.bubble.config.BUBBLE_MENU_ENABLED", False):
            bubble = TranslationBubble()
            bubble.show_translation("译文", source_text="source")
            bubble.show_edit_view()
            bubble.refresh_settings()
            bubble.show()
            self.app.processEvents()
            hidden_height = bubble.height()

            self.assertFalse(bubble.toolbar.isVisible())
            self.assertEqual(bubble.view_mode, "translation")
            self.assertFalse(bubble.source_title.isVisible())
            self.assertTrue(bubble.translation_label.isVisible())

        with patch("src.ui.bubble.config.BUBBLE_MENU_ENABLED", True):
            bubble.refresh_settings()
            self.app.processEvents()

            self.assertTrue(bubble.toolbar.isVisible())
            self.assertGreater(bubble.height(), hidden_height)


if __name__ == "__main__":
    unittest.main()
