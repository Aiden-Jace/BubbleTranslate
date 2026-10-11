import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.ui.config_gui import ConfigWindow


class ConfigWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_save_batches_configuration_writes(self):
        window = ConfigWindow()
        window.bubble_position_combo.setCurrentIndex(
            window.bubble_position_combo.findData("top_left")
        )
        with (
            patch("src.ui.config_gui.config.update_configs") as update,
            patch("src.ui.config_gui.QMessageBox.information"),
            patch.object(window, "close"),
        ):
            window.save_config()

        update.assert_called_once()
        updates = update.call_args.args[0]
        self.assertGreater(len(updates), 20)
        self.assertIn(("UI", "BUBBLE_DEFAULT_POSITION", "top_left"), updates)
        self.assertIn(
            (
                "UI",
                "BUBBLE_MENU_ENABLED",
                window.bubble_menu_check.isChecked(),
            ),
            updates,
        )
        self.assertIn(
            (
                "System",
                "AUTO_SELECTION_ENABLED",
                window.auto_selection_check.isChecked(),
            ),
            updates,
        )

    def test_bubble_position_options_and_saved_selection(self):
        for position in ("top_center", "top_left", "top_right", "invalid"):
            with self.subTest(position=position):
                with patch("src.ui.config_gui.config.BUBBLE_DEFAULT_POSITION", position):
                    window = ConfigWindow()
                self.assertEqual(
                    [window.bubble_position_combo.itemText(i) for i in range(3)],
                    ["右上角", "左上角", "顶部居中"],
                )
                self.assertEqual(
                    window.bubble_position_combo.currentData(),
                    "top_center" if position == "invalid" else position,
                )
                window.close()
                window.deleteLater()


if __name__ == "__main__":
    unittest.main()
