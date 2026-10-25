import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import delete, isValid

from src.main import BubbleTranslateApp, GlobalEventFilter
from src.ui.overlay import CaptureOverlay


class ShutdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_filter_ignores_deleted_overlay(self):
        overlay = CaptureOverlay()
        event_filter = GlobalEventFilter(SimpleNamespace(overlay=overlay, bubble=None))
        delete(overlay)
        self.assertFalse(isValid(overlay))
        self.assertFalse(event_filter.eventFilter(None, QEvent(QEvent.User)))

    def test_deactivated_filter_never_accesses_windows(self):
        controller = Mock()
        event_filter = GlobalEventFilter(controller)
        event_filter.deactivate()
        self.assertFalse(event_filter.eventFilter(None, QEvent(QEvent.User)))
        self.assertIsNone(event_filter.app)
        self.assertEqual(controller.mock_calls, [])

    def test_quit_stops_timers_detaches_filter_and_clears_windows_once(self):
        with (
            patch("src.main.HotkeyListener.start"),
            patch.object(BubbleTranslateApp, "init_tray", lambda obj: setattr(obj, "tray_icon", Mock())),
        ):
            controller = BubbleTranslateApp()
        controller._create_overlay()
        controller.ensure_bubble()
        overlay = controller.overlay
        bubble = controller.bubble
        try:
            with (
                patch.object(self.app, "removeEventFilter", wraps=self.app.removeEventFilter) as remove_filter,
                patch.object(controller.capture_service, "stop", wraps=controller.capture_service.stop) as stop_capture,
                patch.object(controller.listener, "stop") as stop_listener,
                patch("src.main.QApplication.quit") as quit_app,
            ):
                controller.quit_app()
                controller._shutdown()  # aboutToQuit 再次清理时不能重复停止任务。
                remove_filter.assert_called_once_with(controller.event_filter)
                stop_capture.assert_called_once()
                stop_listener.assert_called_once()
                quit_app.assert_called_once()
            self.assertIsNone(controller.event_filter.app)
            for name in ("overlay", "bubble", "config_window"):
                self.assertIsNone(getattr(controller, name))
            for name in ("_capture_prepare_timer", "_stream_timer"):
                self.assertFalse(getattr(controller, name).isActive())
            self.assertFalse(controller._capture_pending)
            # 退出后不能通过快捷键重新启动截图。
            controller.start_capture_mode()
            self.assertIsNone(controller.overlay)
            self.assertFalse(controller._capture_pending)
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertFalse(isValid(overlay))
            self.assertFalse(isValid(bubble))
            self.app.processEvents()
        finally:
            controller.capture_service.stop()
            controller.selection_tip.close()
            controller.deleteLater()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


if __name__ == "__main__":
    unittest.main()
