import platform
from threading import Event, Lock
from PySide6.QtCore import QThread, Signal
from src import config
from src.core.hotkeys import parse_hotkey, validate_hotkeys

class HotkeyListener(QThread):
    # 定义跨线程信号：触发截屏翻译模式
    trigger_signal = Signal()
    # 定义跨线程信号：触发选中文本翻译模式
    text_trigger_signal = Signal()
    selection_drag_finished = Signal(int, int)
    pointer_pressed = Signal(int, int, int)
    registration_failed = Signal(str)
    hotkeys_changed = Signal(str, str)
    RELOAD_HOTKEYS_MESSAGE = 0x8001

    def __init__(self):
        super().__init__()
        self._running = True
        self._system = platform.system()
        self._listener = None # 用于 macOS pynput
        self._mouse_listener = None
        self._win_thread_id = None
        self._left_press_position = None
        self._hotkeys_lock = Lock()
        self._hotkeys_wakeup = Event()
        self._hotkeys_enabled = True
        self._active_hotkeys = None
        self._initial_hotkey_error = None
        try:
            self._hotkeys = validate_hotkeys(config.SCREENSHOT_HOTKEY, config.TEXT_HOTKEY)
        except ValueError as error:
            self._hotkeys = ("F1", "F2")
            self._initial_hotkey_error = f"配置中的快捷键无效，暂时使用 F1 / F2：{error}"

    @property
    def hotkeys(self):
        with self._hotkeys_lock:
            return self._hotkeys

    def update_hotkeys(self, screenshot, text):
        hotkeys = validate_hotkeys(screenshot, text)
        with self._hotkeys_lock:
            if hotkeys == self._hotkeys and hotkeys == self._active_hotkeys:
                return
            self._hotkeys = hotkeys
            if self._system != "Windows" and self._listener:
                self._listener.stop()
        self._wake_hotkey_listener()

    def set_hotkeys_enabled(self, enabled):
        with self._hotkeys_lock:
            if self._hotkeys_enabled == enabled:
                return
            self._hotkeys_enabled = enabled
            if self._system != "Windows" and self._listener:
                self._listener.stop()
        self._wake_hotkey_listener()

    def _wake_hotkey_listener(self):
        self._hotkeys_wakeup.set()
        if self._system == "Windows" and self._win_thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(
                self._win_thread_id, self.RELOAD_HOTKEYS_MESSAGE, 0, 0
            )

    def run(self):
        if self._initial_hotkey_error:
            self.registration_failed.emit(self._initial_hotkey_error)
        self._start_mouse_listener()
        try:
            if self._system == "Windows":
                self._run_windows_listener()
            else:
                self._run_macos_listener()
        finally:
            self._stop_mouse_listener()

    def _start_mouse_listener(self):
        try:
            from pynput import mouse

            self._mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
            self._mouse_listener.start()
        except Exception as error:
            print(f"[Listener] 全局鼠标监听启动失败: {error}")

    def _stop_mouse_listener(self):
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

    def _on_mouse_click(self, x, y, button, pressed):
        button_name = getattr(button, "name", str(button).lower())
        button_code = {"left": 1, "right": 2, "middle": 3}.get(
            button_name,
            0,
        )

        if pressed:
            self.pointer_pressed.emit(int(x), int(y), button_code)
            if button_name == "left":
                self._left_press_position = (int(x), int(y))
            return

        if button_name != "left" or self._left_press_position is None:
            return

        start_x, start_y = self._left_press_position
        self._left_press_position = None
        if abs(int(x) - start_x) + abs(int(y) - start_y) >= 8:
            self.selection_drag_finished.emit(int(x), int(y))

    def _run_windows_listener(self):
        """
        Windows 专用：使用 RegisterHotKey 实现独占式热键监听
        """
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # 先创建消息队列，确保运行时修改快捷键或停止时能唤醒线程。
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._win_thread_id = kernel32.GetCurrentThreadId()
        active_hotkeys = None
        try:
            if self._running:
                active_hotkeys = self._replace_windows_hotkeys(user32)
            while self._running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res > 0:
                    if msg.message == 0x0312 and self._hotkeys_enabled:  # WM_HOTKEY
                        if msg.wParam == 100:
                            self.trigger_signal.emit()
                        elif msg.wParam == 101:
                            self.text_trigger_signal.emit()
                    elif msg.message == self.RELOAD_HOTKEYS_MESSAGE:
                        active_hotkeys = self._replace_windows_hotkeys(user32, active_hotkeys)
                    elif msg.message == 0x0012: # WM_QUIT
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                elif res == 0 or res == -1:
                    break
        finally:
            user32.UnregisterHotKey(None, 100)
            user32.UnregisterHotKey(None, 101)
            self._win_thread_id = None
            print("[Listener] Windows 热键已注销")

    def _replace_windows_hotkeys(self, user32, previous=None):
        with self._hotkeys_lock:
            requested = self._hotkeys
            enabled = self._hotkeys_enabled
        for hotkey_id in (100, 101):
            user32.UnregisterHotKey(None, hotkey_id)
        if not enabled:
            self._active_hotkeys = None
            return previous

        failed = []
        for hotkey_id, value in zip((100, 101), requested):
            modifiers, key = parse_hotkey(value)[1]
            # MOD_NOREPEAT 防止长按 F1/F2 连续触发。
            if not user32.RegisterHotKey(None, hotkey_id, modifiers | 0x4000, key):
                failed.append(value)
        if not failed:
            self._active_hotkeys = requested
            self.hotkeys_changed.emit(*requested)
            return requested

        for hotkey_id in (100, 101):
            user32.UnregisterHotKey(None, hotkey_id)
        if previous:
            restored = True
            for hotkey_id, value in zip((100, 101), previous):
                modifiers, key = parse_hotkey(value)[1]
                if not user32.RegisterHotKey(None, hotkey_id, modifiers | 0x4000, key):
                    restored = False
            if not restored:
                for hotkey_id in (100, 101):
                    user32.UnregisterHotKey(None, hotkey_id)
                previous = None
        self._active_hotkeys = previous
        self.registration_failed.emit(
            f"快捷键 {', '.join(failed)} 注册失败，可能已被其他程序占用。"
            + ("已恢复之前的快捷键。" if previous else "翻译快捷键尚未启用。")
            + "请在设置中更换快捷键后重新保存。"
        )
        return previous

    def _run_macos_listener(self):
        """使用 pynput 监听用户配置的快捷键，修改后重建键盘监听器。"""
        try:
            from pynput import keyboard
            
            while self._running:
                with self._hotkeys_lock:
                    if not self._running:
                        break
                    enabled = self._hotkeys_enabled
                    if not enabled:
                        self._hotkeys_wakeup.clear()
                        self._active_hotkeys = None
                    else:
                        screenshot, text = self._hotkeys
                        listener = keyboard.GlobalHotKeys({
                            parse_hotkey(screenshot)[2]: self.on_trigger_screenshot,
                            parse_hotkey(text)[2]: self.on_trigger_text,
                        })
                        self._listener = listener
                        listener.start()
                        self._active_hotkeys = (screenshot, text)
                if not enabled:
                    self._hotkeys_wakeup.wait()
                    continue
                self.hotkeys_changed.emit(screenshot, text)
                listener.join()
                with self._hotkeys_lock:
                    if self._listener is listener:
                        self._listener = None
        except Exception as e:
            self.registration_failed.emit(f"快捷键监听器启动失败：{e}")

    def on_trigger_screenshot(self):
        if not self._running or not self._hotkeys_enabled:
            return
        print("[Listener] 触发截图信号")
        self.trigger_signal.emit()

    def on_trigger_text(self):
        if not self._running or not self._hotkeys_enabled:
            return
        print("[Listener] 触发划词信号")
        self.text_trigger_signal.emit()

    def stop(self):
        with self._hotkeys_lock:
            self._running = False
            if self._listener:
                self._listener.stop()
        self._hotkeys_wakeup.set()
        self._stop_mouse_listener()
        if self._system == "Windows" and self._win_thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._win_thread_id, 0x0012, 0, 0)
        print("[Listener] 系统热键监听正在停止...")
