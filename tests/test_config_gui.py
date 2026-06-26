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
        with (
            patch("src.ui.config_gui.config.update_configs") as update,
            patch("src.ui.config_gui.QMessageBox.information"),
            patch.object(window, "close"),
        ):
            window.save_config()

        update.assert_called_once()
        updates = update.call_args.args[0]
        self.assertGreater(len(updates), 20)
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


if __name__ == "__main__":
    unittest.main()
