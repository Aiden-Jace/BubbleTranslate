import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QEvent, QPoint, Qt

from src.main import BubbleTranslateApp, GlobalEventFilter
from src.core.listener import HotkeyListener


class MouseEventStub:
    def __init__(self, event_type, button=Qt.RightButton):
        self._event_type = event_type
        self._button = button

    def type(self):
        return self._event_type

    def button(self):
        return self._button

    def modifiers(self):
        return Qt.NoModifier


class GlobalEventFilterTests(unittest.TestCase):
    def test_right_click_is_consumed_until_release(self):
        app = Mock()
        app.overlay.isVisible.return_value = True
        event_filter = GlobalEventFilter(app)

        press_consumed = event_filter.eventFilter(
            None,
            MouseEventStub(QEvent.MouseButtonPress),
        )
        app.handle_right_click.assert_not_called()

        release_consumed = event_filter.eventFilter(
            None,
            MouseEventStub(QEvent.MouseButtonRelease),
        )

        self.assertTrue(press_consumed)
        self.assertTrue(release_consumed)
        app.handle_right_click.assert_called_once_with()

    def test_context_menu_event_is_consumed_without_second_exit(self):
        app = Mock()
        app.overlay.isVisible.return_value = True
        event_filter = GlobalEventFilter(app)

        consumed = event_filter.eventFilter(
            None,
            MouseEventStub(QEvent.ContextMenu),
        )

        self.assertTrue(consumed)
        app.handle_right_click.assert_not_called()


class ButtonStub:
    name = "left"


class HotkeyListenerMouseTests(unittest.TestCase):
    def test_drag_release_emits_selection_position(self):
        listener = HotkeyListener()
        pressed = []
        released = []
        listener.pointer_pressed.connect(
            lambda x, y, button: pressed.append((x, y, button))
        )
        listener.selection_drag_finished.connect(
            lambda x, y: released.append((x, y))
        )

        listener._on_mouse_click(10, 10, ButtonStub(), True)
        listener._on_mouse_click(40, 25, ButtonStub(), False)

        self.assertEqual(pressed, [(10, 10, 1)])
        self.assertEqual(released, [(40, 25)])

    def test_simple_click_does_not_emit_selection(self):
        listener = HotkeyListener()
        released = []
        listener.selection_drag_finished.connect(
            lambda x, y: released.append((x, y))
        )

        listener._on_mouse_click(10, 10, ButtonStub(), True)
        listener._on_mouse_click(12, 12, ButtonStub(), False)

        self.assertEqual(released, [])


class SelectionTipPositionTests(unittest.TestCase):
    def test_drag_uses_qt_cursor_position_instead_of_physical_coordinates(self):
        app = Mock()
        app.overlay = None
        app.selection_tip = Mock()
        app._capture_automatic_selection = Mock()
        logical_position = QPoint(320, 240)

        with (
            patch("src.main.config.AUTO_SELECTION_ENABLED", True),
            patch("src.main.QCursor.pos", return_value=logical_position),
            patch(
                "src.main.QTimer.singleShot",
                side_effect=lambda delay, callback: callback(),
            ),
        ):
            BubbleTranslateApp.handle_selection_drag_finished(
                app,
                3840,
                2160,
            )

        app._capture_automatic_selection.assert_called_once_with(
            logical_position
        )

    def test_click_inside_tip_does_not_hide_it(self):
        app = Mock()
        app.selection_tip.isVisible.return_value = True
        app.selection_tip.contains_global_point.return_value = True
        app.selection_reader.is_active = False
        logical_position = QPoint(320, 240)

        with patch(
            "src.main.QCursor.pos",
            return_value=logical_position,
        ):
            BubbleTranslateApp.handle_global_pointer_press(
                app,
                3840,
                2160,
                1,
            )

        app.selection_tip.contains_global_point.assert_called_once_with(
            logical_position
        )
        app.selection_tip.hide.assert_not_called()


if __name__ == "__main__":
    unittest.main()
