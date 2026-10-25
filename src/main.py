import sys
import os
import signal
from PIL import Image

# 自动修复导入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QStyle, QWidget, QMessageBox
from PySide6.QtCore import Qt, QObject, QEvent, QTimer
from PySide6.QtGui import QPixmap, QAction, QCursor
from shiboken6 import isValid

from src import config
from src.core.listener import HotkeyListener
from src.core.selection_capture import ClipboardSelectionReader
from src.core.screenshot import CaptureService, get_dpi_scaling
from src.core.llm_engine import LLMVisionEngine
from src.ui.overlay import CaptureOverlay
from src.ui.bubble import TranslationBubble
from src.ui.config_gui import ConfigWindow
from src.ui.selection_tip import SelectionTranslateTip
from src.resources import resource_path

class GlobalEventFilter(QObject):
    """
    全局事件过滤器：双击右键关闭气泡或退出截屏模式。
    """
    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._right_double_click_active = False

    def deactivate(self):
        self.app = None
        self._right_double_click_active = False

    def eventFilter(self, obj, event):
        if self.app is None:
            return False
        overlay = self.app.overlay
        if isinstance(overlay, QObject) and not isValid(overlay):
            return False
        # 仅当截图层显示时工作
        if overlay and overlay.isVisible():
            # 气泡语言区域自行处理右键交换，不触发截图模式的关闭动作。
            bubble = self.app.bubble
            if isinstance(bubble, QObject) and not isValid(bubble):
                bubble = None
            # 原生窗口先收到鼠标事件，此时 obj 是 QWindow，需按全局位置识别。
            if (
                bubble
                and event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick)
                and event.button() == Qt.RightButton
                and hasattr(event, "globalPosition")
                and bubble.contains_language_button(event.globalPosition().toPoint())
            ):
                self._right_double_click_active = False
                if event.type() == QEvent.MouseButtonPress:
                    bubble._handle_language_button_press(event)
                event.accept()
                return True
            if bubble and isinstance(obj, QWidget):
                button = bubble.language_button
                if obj is button or button.isAncestorOf(obj):
                    return False
            # 单击右键仅消耗事件，双击后的释放才执行关闭。
            if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
                is_right_click = event.button() == Qt.RightButton
                
                # macOS 特有优化：识别 Control + 左键为右键行为
                if sys.platform == "darwin" and event.button() == Qt.LeftButton:
                    if event.modifiers() & Qt.ControlModifier:
                        is_right_click = True
                        print("[GlobalFilter] 检测到 Control + 左键 (macOS 右键模拟)")

                if is_right_click:
                    if event.type() == QEvent.MouseButtonDblClick:
                        self._right_double_click_active = True
                    elif event.type() == QEvent.MouseButtonRelease and self._right_double_click_active:
                        self._right_double_click_active = False
                        self.app.handle_right_click()
                    return True

            # 捕获上下文菜单事件
            elif event.type() == QEvent.ContextMenu:
                print("[GlobalFilter] 已拦截上下文菜单事件")
                return True
                
        else:
            self._right_double_click_active = False
        return super().eventFilter(obj, event)

class BubbleTranslateApp(QMainWindow):
    """
    气泡翻译主程序
    """
    def __init__(self):
        super().__init__()
        self._shutting_down = False
        # 隐藏主窗口
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.hide()

        # 初始化引擎
        self.llm_engine = LLMVisionEngine()
        
        self.overlay = None
        self.bubble = None
        self.config_window = None
        self.dpi_ratio = 1.0
        self.current_source_text = ""
        self._capture_pending = False
        self._capture_generation = 0
        self.capture_service = CaptureService(self)
        self.capture_service.ready.connect(self._show_capture_frame)
        self.capture_service.failed.connect(self._capture_failed)
        app = QApplication.instance()
        for screen in app.screens():
            screen.geometryChanged.connect(self.capture_service.invalidate)
        app.screenAdded.connect(self._capture_screen_added)
        app.screenRemoved.connect(self.capture_service.invalidate)
        self._capture_prepare_timer = QTimer(self)
        self._capture_prepare_timer.setSingleShot(True)
        self._capture_prepare_timer.timeout.connect(self._request_capture_frame)
        self._pending_stream_text = None
        self._stream_timer = QTimer(self)
        self._stream_timer.setSingleShot(True)
        self._stream_timer.setInterval(40)
        self._stream_timer.timeout.connect(self._flush_translation_stream)
        self.selection_reader = ClipboardSelectionReader(self)
        self.selection_tip = SelectionTranslateTip()
        self.selection_tip.translate_requested.connect(
            self.translate_detected_selection
        )

        # 安装全局事件过滤器
        self.event_filter = GlobalEventFilter(self)
        QApplication.instance().installEventFilter(self.event_filter)

        # 启动用户配置的全局快捷键监听。
        self.listener = HotkeyListener()
        self.listener.registration_failed.connect(self.show_hotkey_error)
        self.listener.hotkeys_changed.connect(self.update_hotkey_tooltip)
        self.listener.trigger_signal.connect(self.start_capture_mode)
        self.listener.text_trigger_signal.connect(self.start_text_translation)
        self.listener.selection_drag_finished.connect(
            self.handle_selection_drag_finished
        )
        self.listener.pointer_pressed.connect(self.handle_global_pointer_press)
        self.listener.start()

        self.init_tray()
        # 截图层、翻译气泡和截屏缓冲区在首次使用时初始化。
        # 启动后保持空闲，避免字体、控件初始化和整屏抓取集中执行。
        app.aboutToQuit.connect(self._shutdown)
        print("--- 气泡翻译 (Bubble Translate) 已启动 ---")
        if config.TRANSLATION_MODE == "LLM":
            print(f"翻译模式: 大模型翻译 (LLM) 双阶段 AI 翻译 (OCR: {config.OCR_MODEL} -> Chat: {config.CHAT_MODEL})")
        else:
            provider_names = {
                "DEEPL": "DeepL",
                "BAIDU": "百度翻译",
                "YOUDAO": "有道翻译",
                "GOOGLE": "Google 免费翻译",
            }
            print(f"翻译模式: {provider_names.get(config.TRANSLATION_MODE, config.TRANSLATION_MODE)}")
        print(f"目标语言: {config.DEFAULT_TARGET_LANGUAGE}")
        print(f"操作: {config.SCREENSHOT_HOTKEY} 开启截图, {config.TEXT_HOTKEY} 划词翻译, 左键拖拽翻译, 双击右键退出")

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        
        # 加载图标 (优先使用资源路径下的 icon.ico)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QPixmap(icon_path))
        else:
            # 兜底：如果没有图标，使用系统默认的“菜单”风格图标
            self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMenuButton))

        # 悬浮提示快捷键
        self.update_hotkey_tooltip(*self.listener.hotkeys)
        
        menu = QMenu()
        
        # 设置菜单
        config_action = QAction("设置", self)
        config_action.triggered.connect(self.show_config_window)
        menu.addAction(config_action)
        
        menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def show_config_window(self):
        if not self.config_window:
            self.config_window = ConfigWindow()
            self.config_window.settings_saved.connect(self.apply_saved_settings)
            self.config_window.closed.connect(self.resume_hotkeys)
        self.listener.set_hotkeys_enabled(False)
        self.config_window.refresh_language_settings()
        self.config_window.refresh_hotkey_settings()
        self.config_window.show()
        self.config_window.activateWindow()
        self.config_window.raise_()

    def resume_hotkeys(self):
        if self._shutting_down:
            return
        self.listener.set_hotkeys_enabled(True)

    def ensure_bubble(self):
        if not self.bubble:
            self.bubble = TranslationBubble()
            self.bubble.source_edit_requested.connect(self.retranslate_edited_source)
            self.bubble.language_changed.connect(self.retranslate_for_language_change)
        return self.bubble

    def apply_saved_settings(self, provider, source_language, target_language):
        self.listener.update_hotkeys(config.SCREENSHOT_HOTKEY, config.TEXT_HOTKEY)
        if not config.AUTO_SELECTION_ENABLED:
            self.selection_reader.cancel()
            self.selection_tip.hide()

        if not self.bubble:
            return

        self.bubble.set_translation_provider(provider)
        self.bubble.refresh_settings()
        if self.current_source_text.strip():
            self.retranslate_for_language_change(
                source_language,
                target_language,
            )

    def update_hotkey_tooltip(self, screenshot, text):
        self.tray_icon.setToolTip(f"气泡翻译\n{screenshot}: 截图翻译\n{text}: 划词翻译")

    def show_hotkey_error(self, message):
        QMessageBox.warning(self.config_window, "快捷键未生效", message)

    def update_status(self, msg):
        """
        [状态更新回调] 将 AI 处理进度显示在气泡中
        """
        if self.bubble:
            self.bubble.set_status_text(msg)
            if not self.bubble.isVisible():
                self.bubble.show()

    def handle_right_click(self):
        """双击右键一次关闭气泡并退出截屏模式。"""
        self.exit_capture_mode()

    def reset_capture_selection(self):
        """重新框选时清理上次结果，继续保留截屏模式。"""
        self.hide_bubble()
        if self.overlay:
            self.overlay.persisted_rect = None
            self.overlay.update()

    def start_capture_mode(self):
        if self._shutting_down:
            return
        # 如果已经显示了，直接返回
        if self._capture_pending or (self.overlay and self.overlay.isVisible()):
            return
        self._capture_pending = True
        self._capture_generation += 1
        # 修复 Bug: 进入截图模式前，先清理掉可能存在的翻译气泡
        self.selection_reader.cancel()
        self.selection_tip.hide()
        self.hide_bubble()
        
        # 给窗口管理器时间移除气泡；使用定时器避免阻塞界面线程。
        self._capture_prepare_timer.start(150 if sys.platform == "darwin" else 0)

    def _request_capture_frame(self):
        if not self._capture_pending:
            return
        self.dpi_ratio = get_dpi_scaling()
        self.capture_service.capture(self._capture_generation)

    def _capture_screen_added(self, screen):
        screen.geometryChanged.connect(self.capture_service.invalidate)
        self.capture_service.invalidate()

    def _create_overlay(self):
        self.overlay = CaptureOverlay()
        self.overlay.area_selected.connect(self.request_llm_translation)
        self.overlay.exit_requested.connect(self.exit_capture_mode)
        self.overlay.reset_requested.connect(self.reset_capture_selection)

    def _capture_failed(self, request_id, message):
        if request_id != self._capture_generation or not self._capture_pending:
            return
        self._capture_pending = False
        QMessageBox.warning(self.config_window, "截图失败", message)

    def _show_capture_frame(self, request_id, frame):
        if request_id != self._capture_generation or not self._capture_pending:
            return
        self._capture_pending = False
        # 权限检测 (针对 macOS)
        if sys.platform == "darwin":
            pil_img = Image.frombytes(
                "RGB", (frame.width(), frame.height()), frame.constBits(),
                "raw", "BGRX", frame.bytesPerLine(),
            )
            extrema = pil_img.convert("L").getextrema()
            if extrema == (0, 0):
                print("\n" + "!"*50)
                print("[Warning] 截取的图片内容为空（全黑）。")
                print("[Action] 请确保已在 '系统设置 -> 隐私与安全性 -> 屏幕录制' 中为终端/Python 开启权限。")
                print("!"*50 + "\n")

        pixmap = QPixmap.fromImage(frame)
        
        # macOS 重新创建窗口以刷新焦点状态；其他平台复用已有窗口。
        if self.overlay and sys.platform == "darwin":
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        if not self.overlay:
            self._create_overlay()
        
        self.overlay.set_data(pixmap, self.dpi_ratio)
        self.overlay.show_full_screen()

    def start_text_translation(self):
        """读取当前选中文本；未选中时打开手动翻译。"""
        self.selection_tip.hide()
        self.selection_reader.capture(self._handle_hotkey_selection)

    def _handle_hotkey_selection(self, selected_text):
        if not selected_text:
            print("[Info] 未检测到选中的文本，打开手动输入翻译。")
            self.open_manual_translation_bubble()
            return

        print(f"[Text] 获取到选中文本: {selected_text}")
        self._show_and_translate_text(selected_text)

    def handle_selection_drag_finished(self, x, y):
        if (
            not config.AUTO_SELECTION_ENABLED
            or self._capture_pending
            or (self.overlay and self.overlay.isVisible())
        ):
            return

        # pynput 在高 DPI 环境中返回物理坐标，Qt 窗口使用逻辑坐标。
        # 直接读取 Qt 当前鼠标位置可保证提示按钮贴近鼠标释放点。
        position = QCursor.pos()
        self.selection_tip.hide()
        QTimer.singleShot(
            80,
            lambda point=position: self._capture_automatic_selection(point),
        )

    def _capture_automatic_selection(self, position):
        if (
            not config.AUTO_SELECTION_ENABLED
            or self._capture_pending
            or (self.overlay and self.overlay.isVisible())
        ):
            return
        self.selection_reader.capture(
            lambda text, point=position: self._show_selection_tip(text, point)
        )

    def _show_selection_tip(self, selected_text, position):
        if selected_text and config.AUTO_SELECTION_ENABLED:
            self.selection_tip.show_for_text(selected_text, position)

    def handle_global_pointer_press(self, x, y, button):
        point = QCursor.pos()
        if (
            self.selection_tip.isVisible()
            and not self.selection_tip.contains_global_point(point)
        ):
            self.selection_tip.hide()
        if self.selection_reader.is_active:
            self.selection_reader.cancel()

    def translate_detected_selection(self, selected_text):
        self._show_and_translate_text(selected_text)

    def _show_and_translate_text(self, selected_text):
        self.ensure_bubble()
        status_text = f"{config.TRANSLATION_MODE} 正在翻译选中文本..."
        self.bubble.show_translation(
            status_text,
            QCursor.pos(),
            source_text=selected_text,
            is_status=True,
        )
        self.bubble.show()

        self._start_text_translation(
            selected_text,
            status_text,
        )

    def request_llm_translation(self, cropped_pil_img, rect):
        self._clear_translation_stream()
        self.ensure_bubble()

        self.current_source_text = ""
        self.bubble.show_translation("正在初始化翻译...", QCursor.pos(), is_status=True)
        
        # 发起异步 LLM 翻译 (支持流式)
        self.llm_engine.translate_image(
            cropped_pil_img, 
            callback=self.on_translation_success, 
            error_callback=self.on_translation_error,
            status_callback=self.update_status,
            stream_callback=self.on_translation_stream,
            source_callback=self.on_source_text_ready,
            target_lang=self.bubble.target_language,
            source_lang=self.bubble.source_language
        )

    def open_manual_translation_bubble(self):
        bubble = self.ensure_bubble()
        self.current_source_text = ""
        bubble.show_translation("", QCursor.pos(), source_text="")
        bubble.show_edit_view()
        bubble.show()
        bubble.raise_()
        bubble.source_edit.setFocus()
        bubble.source_edit.clear()
        bubble.set_status_text("输入原文后自动翻译")

    def on_source_text_ready(self, source_text):
        self.current_source_text = source_text
        if self.bubble:
            self.bubble.set_source_text(source_text)
        print(f"原文: {source_text}")

    def _start_text_translation(self, source_text, status_text):
        self._clear_translation_stream()
        bubble = self.ensure_bubble()
        self.current_source_text = source_text
        bubble.set_source_text(source_text)
        bubble.set_status_text(status_text)
        self.llm_engine.translate_text(
            source_text,
            callback=self.on_translation_success,
            error_callback=self.on_translation_error,
            stream_callback=self.on_translation_stream,
            source_callback=self.on_source_text_ready,
            target_lang=bubble.target_language,
            source_lang=bubble.source_language,
        )

    def retranslate_edited_source(self, source_text):
        self._start_text_translation(
            source_text,
            f"{config.TRANSLATION_MODE} 正在翻译编辑后的原文...",
        )

    def retranslate_for_language_change(self, source_lang, target_lang):
        source_text = ""
        if self.bubble:
            source_text = self.bubble.source_edit.toPlainText().strip() or self.bubble.source_text.strip()
        source_text = source_text or self.current_source_text

        if not source_text:
            return

        self._start_text_translation(
            source_text,
            f"{config.TRANSLATION_MODE} 正在重新翻译...",
        )

    def on_translation_stream(self, partial_text):
        self._pending_stream_text = partial_text
        if not self._stream_timer.isActive():
            self._stream_timer.start()

    def _flush_translation_stream(self):
        text = self._pending_stream_text
        self._pending_stream_text = None
        if self.bubble and text is not None:
            self.bubble.set_text(text)

    def _clear_translation_stream(self):
        self._stream_timer.stop()
        self._pending_stream_text = None

    def on_translation_success(self, translated_text):
        self._clear_translation_stream()
        if self.bubble:
            self.bubble.set_text(translated_text)
        print(f"翻译结果: {translated_text}")

    def on_translation_error(self, error_msg):
        self._clear_translation_stream()
        if self.bubble:
            self.bubble.set_status_text(error_msg)
        print(f"错误: {error_msg}")

    def hide_bubble(self):
        self._clear_translation_stream()
        if self.bubble:
            self.bubble.hide()

    def exit_capture_mode(self):
        """
        退出截屏模式：隐藏截图层，清理资源
        """
        self._capture_pending = False
        self._capture_generation += 1
        self._capture_prepare_timer.stop()
        if self.overlay:
            self.overlay.exit_mode()
            # macOS 需要重建原生窗口以恢复下一次框选的输入焦点。
            if sys.platform == "darwin":
                self.overlay.close()
                self.overlay.deleteLater()
                self.overlay = None
            
        self.hide_bubble()
    def quit_app(self):
        self._shutdown()
        QApplication.quit()

    def _shutdown(self):
        """先注销事件过滤器，再停止任务并关闭窗口；退出信号重复触发也安全。"""
        if self._shutting_down:
            return
        self._shutting_down = True
        self.event_filter.deactivate()
        QApplication.instance().removeEventFilter(self.event_filter)
        self._capture_pending = False
        self._capture_generation += 1
        self._clear_translation_stream()
        self._capture_prepare_timer.stop()
        self.capture_service.stop()
        self.selection_reader.cancel()
        self.selection_tip.close()
        self.listener.stop()
        self.listener.wait(1000)
        self.llm_engine.stop()
        for name in ("overlay", "bubble", "config_window"):
            window = getattr(self, name)
            setattr(self, name, None)
            if window is not None and isValid(window):
                window.close()
                window.deleteLater()
        self.tray_icon.hide()

if __name__ == "__main__":
    # Windows 下创建命名互斥量，防止重复启动，并供安装/卸载程序检测
    if sys.platform == "win32":
        from ctypes import windll
        # 使用 AppId 相同的字符串作为互斥量名称
        mutex_name = "Global\\BubbleTranslate_Mutex_B7A42C91"
        kernel32 = windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        if kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            print("[System] 程序已在运行中。")
            sys.exit(0)

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    translate_app = BubbleTranslateApp()
    
    sys.exit(app.exec())
