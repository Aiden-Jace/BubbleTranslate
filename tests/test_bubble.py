import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import BubbleTranslateApp, GlobalEventFilter
from src.ui.bubble import TranslationBubble


class TranslationBubbleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_bubble(self, source="中文", target="英语"):
        with patch("src.ui.bubble.config.get_language_preference", return_value=(source, target)):
            bubble = TranslationBubble()
            bubble.set_translation_provider("LLM")
        self.addCleanup(bubble.close)
        self.addCleanup(bubble.deleteLater)
        bubble.show_translation("Hello", source_text="你好")
        return bubble

    def test_default_positions_respect_screen_available_geometry(self):
        screen = Mock()
        screen.availableGeometry.return_value = QRect(-1600, 50, 1600, 900)
        with patch("src.ui.bubble.QApplication.primaryScreen", return_value=screen):
            bubble = self.make_bubble()
            for position in ("top_right", "top_left", "top_center", "invalid"):
                with self.subTest(position=position):
                    bubble.hide()
                    with patch("src.ui.bubble.config.BUBBLE_DEFAULT_POSITION", position):
                        bubble.show_translation("译文")
                    expected_x = {
                        "top_right": -bubble.width() - 30,
                        "top_left": -1570,
                    }.get(position, -1600 + (1600 - bubble.width()) // 2)
                    self.assertEqual(bubble.pos(), QPoint(expected_x, 80))

    def test_position_setting_applies_immediately_and_preserves_dragged_position(self):
        with patch("src.ui.bubble.config.BUBBLE_DEFAULT_POSITION", "top_center"):
            bubble = self.make_bubble()
            bubble.move(100, 150)
            bubble.show_translation("新译文")
            self.assertEqual(bubble.pos(), QPoint(100, 150))
            bubble.refresh_settings()
            self.assertEqual(bubble.pos(), QPoint(100, 150))

        with patch("src.ui.bubble.config.BUBBLE_DEFAULT_POSITION", "top_left"):
            bubble.refresh_settings()
            screen = self.app.primaryScreen().availableGeometry()
            margin = min(30, max(0, (screen.width() - bubble.width()) // 2))
            self.assertEqual(bubble.pos(), QPoint(screen.left() + margin, screen.top() + 30))
            bubble.hide()
            bubble.show_translation("重新打开")
            self.assertEqual(bubble.pos(), QPoint(screen.left() + margin, screen.top() + 30))

    def test_right_click_swaps_and_saves_languages_without_hiding_bubble(self):
        bubble = self.make_bubble()
        changes = []
        bubble.language_changed.connect(lambda source, target: changes.append((source, target)))

        with patch("src.ui.bubble.config.update_active_language") as save:
            QTest.mouseClick(bubble.language_button, Qt.RightButton)
            self.assertEqual(bubble.source_language_label.text(), "英语")
            self.assertEqual(bubble.target_language_label.text(), "中文")
            self.assertEqual(bubble.source_text, "Hello")
            self.assertEqual(bubble.source_edit.toPlainText(), "Hello")
            self.assertEqual(bubble.translation_text, "你好")
            self.assertTrue(bubble.isVisible())
            save.assert_called_once_with("LLM", "英语", "中文")
            QTest.mouseClick(bubble.language_button, Qt.RightButton)
            self.assertEqual((bubble.source_language, bubble.target_language), ("中文", "英语"))
            self.assertEqual(save.call_count, 2)
            self.assertEqual((bubble.source_text, bubble.translation_text), ("你好", "Hello"))

        self.assertEqual(changes, [("英语", "中文"), ("中文", "英语")])

    def test_language_swap_retranslates_previous_translation_in_both_views(self):
        for edit_mode in (False, True):
            with self.subTest(edit_mode=edit_mode):
                bubble = self.make_bubble()
                if edit_mode:
                    bubble.show_edit_view()
                    bubble.source_edit.setFocus()
                    bubble.source_edit.setPlainText("修改过的原文")
                    self.assertTrue(bubble.edit_debounce_timer.isActive())
                app = Mock()
                app.bubble = bubble
                app.current_source_text = "旧原文"
                app.ensure_bubble.return_value = bubble
                app._start_text_translation.side_effect = lambda text, status: BubbleTranslateApp._start_text_translation(app, text, status)
                bubble.language_changed.connect(
                    lambda source, target: BubbleTranslateApp.retranslate_for_language_change(app, source, target)
                )
                with patch("src.ui.bubble.config.update_active_language"):
                    QTest.mouseClick(bubble.language_button, Qt.RightButton)
                self.assertEqual(bubble.source_text, "Hello")
                self.assertEqual(bubble.source_edit.toPlainText(), "Hello")
                self.assertEqual(app.current_source_text, "Hello")
                app.llm_engine.translate_text.assert_called_once_with(
                    "Hello",
                    callback=app.on_translation_success,
                    error_callback=app.on_translation_error,
                    stream_callback=app.on_translation_stream,
                    source_callback=app.on_source_text_ready,
                    target_lang="中文",
                    source_lang="英语",
                )
                self.assertFalse(bubble.edit_debounce_timer.isActive())

    def test_language_swap_does_not_use_status_messages_as_source(self):
        bubble = self.make_bubble()
        for status in ("正在翻译...", "翻译失败", ""):
            with self.subTest(status=status):
                bubble.set_status_text(status)
                with patch("src.ui.bubble.config.update_active_language"):
                    bubble.swap_languages()
                self.assertEqual(bubble.source_text, "你好")
                self.assertEqual(bubble.source_edit.toPlainText(), "你好")

    def test_source_and_translation_font_sizes_apply_independently(self):
        with (
            patch("src.ui.bubble.config.BUBBLE_SOURCE_FONT_SIZE", 12),
            patch("src.ui.bubble.config.BUBBLE_FONT_SIZE", 16),
        ):
            bubble = self.make_bubble()
            bubble.show_edit_view()
            self.assertEqual(bubble.source_label.font().pointSize(), 12)
            self.assertEqual(bubble.source_edit.font().pointSize(), 12)
            self.assertEqual(bubble.translation_label.font().pointSize(), 16)
            old_source_line_height = bubble.source_edit.fontMetrics().height()
            with patch("src.ui.bubble.config.BUBBLE_SOURCE_FONT_SIZE", 24):
                bubble.refresh_settings()
                self.assertEqual(bubble.source_label.font().pointSize(), 24)
                self.assertEqual(bubble.source_edit.font().pointSize(), 24)
                self.assertGreater(bubble.source_edit.fontMetrics().height(), old_source_line_height)
                self.assertEqual(bubble.translation_label.font().pointSize(), 16)
            with patch("src.ui.bubble.config.BUBBLE_FONT_SIZE", 20):
                bubble.refresh_settings()
                self.assertEqual(bubble.source_edit.font().pointSize(), 12)
                self.assertEqual(bubble.translation_label.font().pointSize(), 20)

    def test_full_opacity_has_an_opaque_background(self):
        with patch("src.ui.bubble.config.BUBBLE_OPACITY", 1.0):
            bubble = self.make_bubble()
            self.app.processEvents()
            self.assertEqual(bubble.windowOpacity(), 1.0)
            background = bubble.container.grab().toImage()
            scale = background.devicePixelRatio()
            pixel = background.pixelColor(int(20 * scale), int((bubble.container.height() - 6) * scale))
            self.assertEqual(pixel.alpha(), 255)
            self.assertEqual((pixel.red(), pixel.green(), pixel.blue()), (255, 255, 255))
        with patch("src.ui.bubble.config.BUBBLE_OPACITY", 0.5):
            bubble.refresh_settings()
            self.assertAlmostEqual(bubble.windowOpacity(), 0.5, delta=0.01)

    def test_single_right_click_keeps_bubble_open_and_double_click_closes(self):
        for target_name in (None, "translation_label", "source_edit", "copy_button"):
            with self.subTest(target=target_name):
                bubble = self.make_bubble()
                if target_name == "source_edit":
                    bubble.show_edit_view()
                    target = bubble.source_edit.viewport()
                else:
                    target = getattr(bubble, target_name) if target_name else bubble
                QTest.mouseClick(target, Qt.RightButton)
                self.assertTrue(bubble.isVisible())
                QTest.mouseDClick(target, Qt.RightButton)
                self.assertFalse(bubble.isVisible())

    def test_language_double_click_does_not_close_bubble(self):
        bubble = self.make_bubble()
        with patch("src.ui.bubble.config.update_active_language"):
            QTest.mouseClick(bubble.language_button, Qt.RightButton)
            QTest.mouseDClick(bubble.language_button, Qt.RightButton)
        self.assertTrue(bubble.isVisible())
        self.assertEqual((bubble.source_language, bubble.target_language), ("英语", "中文"))

    def test_auto_detect_and_same_language_do_not_trigger_translation(self):
        for source, target in [("自动检测", "英语"), ("中文", "中文")]:
            with self.subTest(source=source, target=target):
                bubble = self.make_bubble(source, target)
                changed = Mock()
                bubble.language_changed.connect(changed)
                with patch("src.ui.bubble.config.update_active_language") as save:
                    QTest.mouseClick(bubble.language_button, Qt.RightButton)
                    save.assert_not_called()
                changed.assert_not_called()
                self.assertEqual((bubble.source_language, bubble.target_language), (source, target))
                self.assertTrue(bubble.isVisible())

    def test_left_click_still_opens_language_menu(self):
        bubble = self.make_bubble()
        QTest.mouseClick(bubble.language_button, Qt.LeftButton)
        self.assertIsNotNone(bubble.language_menu)
        self.assertTrue(bubble.language_menu.isVisible())
        bubble.language_menu.close()

    def test_right_click_with_language_menu_open_closes_menu_and_swaps(self):
        bubble = self.make_bubble()
        bubble.show_language_menu()
        with patch("src.ui.bubble.config.update_active_language"):
            QTest.mouseClick(bubble.language_button, Qt.RightButton)
        self.assertIsNone(bubble.language_menu)
        self.assertFalse(bubble._language_menu_filter_installed)
        self.assertEqual((bubble.source_language, bubble.target_language), ("英语", "中文"))

    def test_swap_works_while_capture_overlay_is_visible(self):
        bubble = self.make_bubble()
        owner = Mock()
        owner.bubble = bubble
        owner.overlay.isVisible.return_value = True
        event_filter = GlobalEventFilter(owner)
        self.app.installEventFilter(event_filter)
        try:
            with patch("src.ui.bubble.config.update_active_language") as save:
                QTest.mouseClick(bubble.language_button, Qt.RightButton)
                save.assert_called_once_with("LLM", "英语", "中文")
            owner.handle_right_click.assert_not_called()
            self.assertTrue(bubble.isVisible())
        finally:
            self.app.removeEventFilter(event_filter)

    def test_capture_language_right_click_delivered_to_window_swaps_languages(self):
        bubble = self.make_bubble()
        self.app.processEvents()
        self.assertGreater(bubble.language_button.height(), 0)
        owner = Mock()
        owner.bubble = bubble
        owner.overlay.isVisible.return_value = True
        event_filter = GlobalEventFilter(owner)
        self.app.installEventFilter(event_filter)
        try:
            global_pos = bubble.language_button.mapToGlobal(bubble.language_button.rect().center())
            event = QMouseEvent(
                QEvent.MouseButtonPress,
                QPointF(bubble.mapFromGlobal(global_pos)),
                QPointF(global_pos),
                Qt.RightButton, Qt.RightButton, Qt.NoModifier,
            )
            with patch("src.ui.bubble.config.update_active_language") as save:
                self.app.sendEvent(bubble.windowHandle(), event)
                save.assert_called_once_with("LLM", "英语", "中文")
                bubble.show_language_menu()
                self.app.sendEvent(bubble.windowHandle(), event)
                self.assertEqual(save.call_count, 2)
                save.assert_called_with("LLM", "中文", "英语")
                self.assertIsNone(bubble.language_menu)
            self.assertTrue(bubble.isVisible())
            owner.handle_right_click.assert_not_called()
        finally:
            self.app.removeEventFilter(event_filter)

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
