import sys
import os
import signal

# 自动修复导入路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QStyle, QWidget
from PySide6.QtCore import Qt, QObject, QEvent, QTimer
from PySide6.QtGui import QPixmap, QImage, QAction, QCursor

from src import config
from src.core.listener import HotkeyListener
from src.core.selection_capture import ClipboardSelectionReader
from src.core.screenshot import capture_screen, get_dpi_scaling
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

    def eventFilter(self, obj, event):
        # 仅当截图层显示时工作
        if self.app.overlay and self.app.overlay.isVisible():
            # 气泡语言区域自行处理右键交换，不触发截图模式的关闭动作。
            bubble = self.app.bubble
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
        self.selection_reader = ClipboardSelectionReader(self)
        self.selection_tip = SelectionTranslateTip()
        self.selection_tip.translate_requested.connect(
            self.translate_detected_selection
        )

        # 安装全局事件过滤器
        self.event_filter = GlobalEventFilter(self)
        QApplication.instance().installEventFilter(self.event_filter)

        # 启动热键监听 (Alt + Z)
        self.listener = HotkeyListener()
        self.listener.trigger_signal.connect(self.start_capture_mode)
        self.listener.text_trigger_signal.connect(self.start_text_translation)
        self.listener.selection_drag_finished.connect(
            self.handle_selection_drag_finished
        )
        self.listener.pointer_pressed.connect(self.handle_global_pointer_press)
        self.listener.start()

        self.init_tray()
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
        print("操作: Alt + Z 开启截图, Ctrl + Q 划词翻译, 左键拖拽翻译, 双击右键退出")

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
        self.tray_icon.setToolTip("气泡翻译\nAlt + Z: 截图翻译\nCtrl + Q: 划词翻译")
        
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
        self.config_window.refresh_language_settings()
        self.config_window.show()
        self.config_window.activateWindow()
        self.config_window.raise_()

    def ensure_bubble(self):
        if not self.bubble:
            self.bubble = TranslationBubble()
            self.bubble.source_edit_requested.connect(self.retranslate_edited_source)
            self.bubble.language_changed.connect(self.retranslate_for_language_change)
        return self.bubble

    def apply_saved_settings(self, provider, source_language, target_language):
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

    def update_status(self, msg):
        """
        [状态更新回调] 将 AI 处理进度显示在气泡中
        """
        if self.bubble:
            self.bubble.set_text(msg)
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
        # 如果已经显示了，直接返回
        if self.overlay and self.overlay.isVisible():
            return
            
        # 修复 Bug: 进入截图模式前，先清理掉可能存在的翻译气泡
        self.selection_reader.cancel()
        self.selection_tip.hide()
        self.hide_bubble()
        
        # macOS 特有处理：强制等待气泡窗口完全消失后再进行截屏，防止气泡被截入图中
        if sys.platform == "darwin":
            import time
            for _ in range(3):
                QApplication.processEvents()
                time.sleep(0.05)

        self.dpi_ratio = get_dpi_scaling()
        pil_img = capture_screen()
        
        # 权限检测 (针对 macOS)
        if sys.platform == "darwin":
            extrema = pil_img.convert("L").getextrema()
            if extrema == (0, 0):
                print("\n" + "!"*50)
                print("[Warning] 截取的图片内容为空（全黑）。")
                print("[Action] 请确保已在 '系统设置 -> 隐私与安全性 -> 屏幕录制' 中为终端/Python 开启权限。")
                print("!"*50 + "\n")

        # 内存安全：进行深拷贝
        data = pil_img.tobytes("raw", "RGB")
        qimg = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimg)
        
        # 为了解决“第二次触发无法框选”的问题，每次都重新创建 Overlay 窗口
        # 这能确保窗口状态（焦点、标志等）在 macOS 上是完全干净的
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

        self.overlay = CaptureOverlay()
        self.overlay.area_selected.connect(self.request_llm_translation)
        self.overlay.exit_requested.connect(self.exit_capture_mode)
        self.overlay.reset_requested.connect(self.reset_capture_selection)
        
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
            source_text=selected_text
        )
        self.bubble.show()

        self._start_text_translation(
            selected_text,
            status_text,
        )

    def request_llm_translation(self, cropped_pil_img, rect):
        self.ensure_bubble()

        self.current_source_text = ""
        self.bubble.show_translation("正在初始化翻译...", QCursor.pos())
        
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
        bubble.set_translation_text("输入原文后自动翻译")

    def on_source_text_ready(self, source_text):
        self.current_source_text = source_text
        if self.bubble:
            self.bubble.set_source_text(source_text)
        print(f"原文: {source_text}")

    def _start_text_translation(self, source_text, status_text):
        bubble = self.ensure_bubble()
        self.current_source_text = source_text
        bubble.set_source_text(source_text)
        bubble.set_translation_text(status_text)
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
        if self.bubble:
            self.bubble.set_text(partial_text)

    def on_translation_success(self, translated_text):
        if self.bubble:
            self.bubble.set_text(translated_text)
        print(f"翻译结果: {translated_text}")

    def on_translation_error(self, error_msg):
        if self.bubble:
            self.bubble.set_text(error_msg)
        print(f"错误: {error_msg}")

    def hide_bubble(self):
        if self.bubble:
            self.bubble.hide()
            QApplication.processEvents() 

    def exit_capture_mode(self):
        """
        退出截屏模式：隐藏截图层，清理资源
        """
        if self.overlay:
            self.overlay.exit_mode()
            # 为了下一次触发能彻底刷新状态，在退出时彻底清理对象
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None
            
        self.hide_bubble()
    def quit_app(self):
        self.selection_reader.cancel()
        self.selection_tip.close()
        self.listener.stop()
        self.listener.wait(1000)
        self.llm_engine.stop()
        QApplication.quit()

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
