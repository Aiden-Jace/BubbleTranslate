import configparser
import unittest
from unittest.mock import Mock, patch

from src import config
from src.core.hotkeys import parse_hotkey, validate_hotkeys
from src.core.listener import HotkeyListener
from src.main import BubbleTranslateApp


class HotkeyTests(unittest.TestCase):
    def test_function_keys_and_modifier_combinations_convert_for_both_backends(self):
        cases = {
            "F1": ("F1", (0, 0x70), "<f1>"),
            "F2": ("F2", (0, 0x71), "<f2>"),
            "Alt+Z": ("Alt+Z", (1, 0x5A), "<alt>+z"),
            "Shift+Ctrl+F12": ("Ctrl+Shift+F12", (6, 0x7B), "<ctrl>+<shift>+<f12>"),
            "Meta+Home": ("Meta+Home", (8, 0x24), "<cmd>+<home>"),
            "Ctrl+9": ("Ctrl+9", (2, 0x39), "<ctrl>+9"),
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(parse_hotkey(value), expected)

    def test_invalid_and_duplicate_shortcuts_are_rejected(self):
        for value in ("", "Ctrl", "F1, F2", "F25", "Ctrl+Unknown"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_hotkey(value)
        with self.assertRaises(ValueError):
            validate_hotkeys("Shift+Ctrl+A", "Ctrl+Shift+A")

    def test_settings_update_persisted_and_runtime_hotkeys(self):
        with (
            patch.object(config, "_parser", configparser.ConfigParser()) as parser,
            patch.object(config, "SCREENSHOT_HOTKEY", "F1"),
            patch.object(config, "TEXT_HOTKEY", "F2"),
            patch.object(config, "save_config_to_file") as save,
        ):
            config.update_configs([
                ("System", "SCREENSHOT_HOTKEY", "Ctrl+F3"),
                ("System", "TEXT_HOTKEY", "Alt+Q"),
            ])
            self.assertEqual(config.SCREENSHOT_HOTKEY, "Ctrl+F3")
            self.assertEqual(config.TEXT_HOTKEY, "Alt+Q")
            self.assertEqual(parser.get("System", "SCREENSHOT_HOTKEY"), "Ctrl+F3")
            save.assert_called_once_with()


class HotkeyListenerTests(unittest.TestCase):
    def make_listener(self):
        with (
            patch.object(config, "SCREENSHOT_HOTKEY", "F1"),
            patch.object(config, "TEXT_HOTKEY", "F2"),
        ):
            return HotkeyListener()

    def test_pynput_callbacks_pause_while_settings_are_open(self):
        listener = self.make_listener()
        triggers = []
        listener.trigger_signal.connect(lambda: triggers.append("screenshot"))
        listener.text_trigger_signal.connect(lambda: triggers.append("text"))
        listener.set_hotkeys_enabled(False)
        listener.on_trigger_screenshot()
        listener.on_trigger_text()
        self.assertEqual(triggers, [])
        listener.set_hotkeys_enabled(True)
        listener.on_trigger_screenshot()
        listener.on_trigger_text()
        self.assertEqual(triggers, ["screenshot", "text"])

    def test_windows_replaces_old_bindings_and_prevents_repeated_keydown(self):
        listener = self.make_listener()
        user32 = Mock()
        user32.RegisterHotKey.return_value = True
        changes = []
        listener.hotkeys_changed.connect(lambda *pair: changes.append(pair))
        self.assertEqual(listener._replace_windows_hotkeys(user32), ("F1", "F2"))
        user32.RegisterHotKey.assert_any_call(None, 100, 0x4000, 0x70)
        user32.RegisterHotKey.assert_any_call(None, 101, 0x4000, 0x71)

        listener.update_hotkeys("Ctrl+F3", "Alt+Q")
        user32.reset_mock()
        self.assertEqual(listener._replace_windows_hotkeys(user32, ("F1", "F2")), ("Ctrl+F3", "Alt+Q"))
        user32.UnregisterHotKey.assert_any_call(None, 100)
        user32.UnregisterHotKey.assert_any_call(None, 101)
        user32.RegisterHotKey.assert_any_call(None, 100, 0x4002, 0x72)
        user32.RegisterHotKey.assert_any_call(None, 101, 0x4001, 0x51)
        self.assertEqual(changes, [("F1", "F2"), ("Ctrl+F3", "Alt+Q")])

    def test_windows_registration_failure_restores_previous_bindings(self):
        listener = self.make_listener()
        listener.update_hotkeys("Ctrl+F3", "Alt+Q")
        user32 = Mock()
        user32.RegisterHotKey.side_effect = [False, True, True, True]
        errors = []
        listener.registration_failed.connect(errors.append)
        self.assertEqual(listener._replace_windows_hotkeys(user32, ("F1", "F2")), ("F1", "F2"))
        user32.RegisterHotKey.assert_any_call(None, 100, 0x4000, 0x70)
        user32.RegisterHotKey.assert_any_call(None, 101, 0x4000, 0x71)
        self.assertIn("Ctrl+F3", errors[0])
        self.assertEqual(listener._active_hotkeys, ("F1", "F2"))

    def test_windows_shortcuts_are_unregistered_during_settings_and_restored_afterward(self):
        listener = self.make_listener()
        user32 = Mock()
        user32.RegisterHotKey.return_value = True
        listener.set_hotkeys_enabled(False)
        listener._replace_windows_hotkeys(user32, ("F1", "F2"))
        user32.RegisterHotKey.assert_not_called()
        listener.set_hotkeys_enabled(True)
        self.assertEqual(listener._replace_windows_hotkeys(user32, ("F1", "F2")), ("F1", "F2"))

    def test_pynput_keyboard_listener_rebuilds_without_restarting_mouse_listener(self):
        listener = self.make_listener()
        listener._system = "Darwin"
        initial, replacement = Mock(), Mock()
        initial.join.side_effect = lambda: listener.update_hotkeys("Ctrl+F3", "Alt+Q")
        replacement.join.side_effect = listener.stop
        with patch("pynput.keyboard.GlobalHotKeys", side_effect=[initial, replacement]) as factory:
            listener._run_macos_listener()
        self.assertEqual(set(factory.call_args_list[0].args[0]), {"<f1>", "<f2>"})
        self.assertEqual(set(factory.call_args_list[1].args[0]), {"<ctrl>+<f3>", "<alt>+q"})
        initial.start.assert_called_once_with()
        initial.stop.assert_called_once_with()
        replacement.start.assert_called_once_with()
        replacement.stop.assert_called_once_with()

    def test_saved_shortcuts_apply_even_without_an_open_bubble(self):
        app = Mock()
        app.bubble = None
        with (
            patch.object(config, "SCREENSHOT_HOTKEY", "Ctrl+F3"),
            patch.object(config, "TEXT_HOTKEY", "Alt+Q"),
        ):
            BubbleTranslateApp.apply_saved_settings(app, "LLM", "中文", "英语")
        app.listener.update_hotkeys.assert_called_once_with("Ctrl+F3", "Alt+Q")


if __name__ == "__main__":
    unittest.main()
