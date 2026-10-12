import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QKeySequence

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
        window.screenshot_hotkey_edit.setKeySequence(QKeySequence("Ctrl+F3"))
        window.text_hotkey_edit.setKeySequence(QKeySequence("Alt+Q"))
        window.source_font_size_spin.setValue(18)
        window.translation_font_size_spin.setValue(12)
        window.strategy_combo.setCurrentIndex(window.strategy_combo.findData("LOCAL_CPU"))
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
        self.assertIn(("System", "SCREENSHOT_HOTKEY", "Ctrl+F3"), updates)
        self.assertIn(("System", "TEXT_HOTKEY", "Alt+Q"), updates)
        self.assertIn(("UI", "BUBBLE_SOURCE_FONT_SIZE", 18), updates)
        self.assertIn(("UI", "BUBBLE_FONT_SIZE", 12), updates)
        self.assertIn(("Translation", "STRATEGY", "LOCAL_CPU"), updates)
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

    def test_invalid_hotkeys_do_not_write_configuration(self):
        window = ConfigWindow()
        for screenshot, text in [("", "F2"), ("F2", "F2")]:
            with self.subTest(screenshot=screenshot, text=text):
                window.screenshot_hotkey_edit.setKeySequence(QKeySequence(screenshot))
                window.text_hotkey_edit.setKeySequence(QKeySequence(text))
                with (
                    patch("src.ui.config_gui.config.update_configs") as update,
                    patch("src.ui.config_gui.QMessageBox.warning") as warning,
                ):
                    window.save_config()
                update.assert_not_called()
                warning.assert_called_once()
        window.deleteLater()

    def test_screenshot_strategy_loads_cpu_and_existing_api_options(self):
        for strategy in ("LOCAL_CPU", "OCR_LLM", "VLM"):
            with self.subTest(strategy=strategy):
                with patch("src.ui.config_gui.config.SCREENSHOT_STRATEGY", strategy):
                    window = ConfigWindow()
                    self.assertEqual(window.strategy_combo.currentData(), strategy)
                    window.strategy_combo.setCurrentIndex((window.strategy_combo.currentIndex() + 1) % 3)
                    window.refresh_language_settings()
                    self.assertEqual(window.strategy_combo.currentData(), strategy)
                window.deleteLater()

    def test_hotkey_settings_reload_and_reset_to_f1_f2(self):
        window = ConfigWindow()
        with (
            patch("src.ui.config_gui.config.SCREENSHOT_HOTKEY", "Ctrl+F3"),
            patch("src.ui.config_gui.config.TEXT_HOTKEY", "Alt+Q"),
        ):
            window.refresh_hotkey_settings()
        self.assertEqual(window.screenshot_hotkey_edit.keySequence(), QKeySequence("Ctrl+F3"))
        self.assertEqual(window.text_hotkey_edit.keySequence(), QKeySequence("Alt+Q"))
        window.reset_hotkeys()
        self.assertEqual(window.screenshot_hotkey_edit.keySequence(), QKeySequence("F1"))
        self.assertEqual(window.text_hotkey_edit.keySequence(), QKeySequence("F2"))
        closed = []
        window.closed.connect(lambda: closed.append(True))
        window.close()
        self.assertEqual(closed, [True])
        window.deleteLater()


if __name__ == "__main__":
    unittest.main()
