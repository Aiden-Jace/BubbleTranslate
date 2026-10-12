import os
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QRect, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

from src.core.screenshot import CaptureService, _CaptureWorker
from src.main import BubbleTranslateApp
from src.ui.overlay import CaptureOverlay


class CapturePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_capture_runs_off_gui_thread_and_reuses_backend(self):
        thread_ids = []
        screen = Mock()
        screen.monitors = [{}]

        def grab(monitor):
            thread_ids.append(threading.get_ident())
            return SimpleNamespace(width=2, height=1, bgra=bytes([0, 0, 255, 0, 255, 0, 0, 0]))

        screen.grab.side_effect = grab
        frames = []
        loop = QEventLoop()
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        with patch("src.core.screenshot.mss.mss", return_value=screen) as create:
            service = CaptureService()
            def receive(request_id, frame):
                frames.append((request_id, frame))
                if len(frames) == 2:
                    loop.quit()
            service.ready.connect(receive)
            try:
                service.warm_up()
                service.capture(1)
                service.capture(2)
                timeout.start(3000)
                loop.exec()
            finally:
                timeout.stop()
                service.stop()
            create.assert_called_once()
        self.assertEqual([item[0] for item in frames], [1, 2])
        self.assertEqual(len(thread_ids), 2 if sys.platform == "darwin" else 3)
        self.assertEqual(len(set(thread_ids)), 1)
        self.assertNotEqual(thread_ids[0], threading.get_ident())
        self.assertEqual(frames[0][1].pixelColor(0, 0), QColor("red"))
        self.assertEqual(frames[0][1].pixelColor(1, 0), QColor("blue"))
        screen.close.assert_called_once()

    def test_failure_releases_backend_and_next_capture_retries(self):
        broken = Mock()
        broken.monitors = [{}]
        broken.grab.side_effect = RuntimeError("screen unavailable")
        good = Mock()
        good.monitors = [{}]
        good.grab.return_value = SimpleNamespace(width=1, height=1, bgra=bytes([0, 0, 255, 0]))
        worker = _CaptureWorker()
        failed, ready = [], []
        worker.failed.connect(lambda request_id, message: failed.append((request_id, message)))
        worker.ready.connect(lambda request_id, frame: ready.append(request_id))
        with patch("src.core.screenshot.mss.mss", side_effect=[broken, good]):
            worker.capture(1)
            worker.capture(2)
        worker.close()
        self.assertEqual(failed, [(1, "screen unavailable")])
        self.assertEqual(ready, [2])
        broken.close.assert_called_once()
        good.close.assert_called_once()

    def test_repeated_hotkeys_do_not_queue_duplicate_capture(self):
        app = Mock()
        app.overlay = None
        app._capture_pending = False
        app._capture_generation = 0
        BubbleTranslateApp.start_capture_mode(app)
        BubbleTranslateApp.start_capture_mode(app)
        self.assertEqual(app._capture_generation, 1)
        app._capture_prepare_timer.start.assert_called_once()
        app.selection_reader.cancel.assert_called_once()

    def test_windows_overlay_is_reused_and_resets_after_exit(self):
        app = Mock()
        app.overlay = None
        app._capture_pending = True
        app._capture_generation = 1
        app.dpi_ratio = 1.0
        app._create_overlay.side_effect = lambda: BubbleTranslateApp._create_overlay(app)
        frame = QImage(20, 20, QImage.Format_RGB32)
        frame.fill(QColor("white"))
        with patch("src.main.sys.platform", "win32"), patch.object(CaptureOverlay, "show_full_screen"):
            BubbleTranslateApp._show_capture_frame(app, 1, frame)
            overlay = app.overlay
            overlay.persisted_rect = QRect(1, 1, 8, 8)
            overlay.is_selecting = True
            BubbleTranslateApp.exit_capture_mode(app)
            self.assertIsNone(overlay.pixmap)
            app._capture_pending = True
            BubbleTranslateApp._show_capture_frame(app, app._capture_generation, frame)
            self.assertIs(app.overlay, overlay)
            self.assertIsNone(overlay.persisted_rect)
            self.assertFalse(overlay.is_selecting)
            app._create_overlay.assert_called_once()
        overlay.close()

    def test_display_layout_change_reopens_backend(self):
        first, second = Mock(), Mock()
        for screen in (first, second):
            screen.monitors = [{}]
            screen.grab.return_value = SimpleNamespace(width=1, height=1, bgra=bytes([0, 0, 255, 0]))
        worker = _CaptureWorker()
        with patch("src.core.screenshot.mss.mss", side_effect=[first, second]) as create:
            worker.capture(1)
            worker.close()
            worker.capture(2)
            self.assertEqual(create.call_count, 2)
        worker.close()

    def test_exit_discards_frame_from_previous_request(self):
        app = Mock()
        app.overlay = None
        app._capture_pending = True
        app._capture_generation = 1
        BubbleTranslateApp.exit_capture_mode(app)
        BubbleTranslateApp._show_capture_frame(app, 1, QImage())
        app._create_overlay.assert_not_called()
        self.assertFalse(app._capture_pending)

    def test_crop_handles_rgb_row_padding(self):
        overlay = CaptureOverlay()
        image = QImage(7, 6, QImage.Format_RGB32)
        for y in range(6):
            for x in range(7):
                image.setPixelColor(x, y, QColor(x * 20, y * 30, 100))
        overlay.set_data(QPixmap.fromImage(image), 1.0)
        crops = []
        overlay.area_selected.connect(lambda image, rect: crops.append(image))
        overlay.process_selection(QRect(1, 1, 5, 3))
        self.assertEqual(crops[0].size, (5, 3))
        self.assertEqual(crops[0].getpixel((0, 0)), (20, 30, 100))
        self.assertEqual(crops[0].getpixel((4, 2)), (100, 90, 100))
        overlay.close()

    def test_stream_merges_chunks_and_final_result_cancels_pending_refresh(self):
        app = Mock()
        app._stream_timer.isActive.return_value = False
        BubbleTranslateApp.on_translation_stream(app, "first")
        app._stream_timer.isActive.return_value = True
        BubbleTranslateApp.on_translation_stream(app, "latest")
        app.bubble.set_text.assert_not_called()
        app._stream_timer.start.assert_called_once()
        BubbleTranslateApp._flush_translation_stream(app)
        app.bubble.set_text.assert_called_once_with("latest")
        app._clear_translation_stream.side_effect = lambda: BubbleTranslateApp._clear_translation_stream(app)
        BubbleTranslateApp.on_translation_stream(app, "old partial")
        BubbleTranslateApp.on_translation_success(app, "final")
        BubbleTranslateApp._flush_translation_stream(app)
        self.assertEqual(app.bubble.set_text.call_count, 2)
        app.bubble.set_text.assert_called_with("final")


if __name__ == "__main__":
    unittest.main()
