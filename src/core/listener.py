import platform
import sys
from PySide6.QtCore import QThread, Signal

class HotkeyListener(QThread):
    # 定义跨线程信号：触发截屏翻译模式
    trigger_signal = Signal()
    # 定义跨线程信号：触发选中文本翻译模式
    text_trigger_signal = Signal()
    selection_drag_finished = Signal(int, int)
    pointer_pressed = Signal(int, int, int)

    def __init__(self):
        super().__init__()
        self._running = True
        self._system = platform.system()
        self._listener = None # 用于 macOS pynput
        self._mouse_listener = None
        self._win_thread_id = None
        self._left_press_position = None

    def run(self):
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
        
        # 记录当前线程 ID，用于后续停止时唤醒
        self._win_thread_id = kernel32.GetCurrentThreadId()
        
        # 注册全局热键 ID
        HOTKEY_Z_ID = 100
        HOTKEY_Q_ID = 101
        
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        VK_Z = 0x5A
        VK_Q = 0x51

        if not user32.RegisterHotKey(None, HOTKEY_Z_ID, MOD_ALT, VK_Z):
            print(f"[Error] Windows 独占热键 Alt + Z 注册失败，可能被占用")
        
        if not user32.RegisterHotKey(None, HOTKEY_Q_ID, MOD_CONTROL, VK_Q):
            print(f"[Error] Windows 独占热键 Ctrl + Q 注册失败，可能被占用")

        print("[Listener] Windows 独占热键监听已启动 (Alt+Z / Ctrl+Q)")

        try:
            msg = wintypes.MSG()
            while self._running:
                res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if res > 0:
                    if msg.message == 0x0312:  # WM_HOTKEY
                        if msg.wParam == HOTKEY_Z_ID:
                            self.trigger_signal.emit()
                        elif msg.wParam == HOTKEY_Q_ID:
                            self.text_trigger_signal.emit()
                    elif msg.message == 0x0012: # WM_QUIT
                        break
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                elif res == 0 or res == -1:
                    break
        finally:
            user32.UnregisterHotKey(None, HOTKEY_Z_ID)
            user32.UnregisterHotKey(None, HOTKEY_Q_ID)
            print("[Listener] Windows 热键已注销")

    def _run_macos_listener(self):
        """
        macOS 专用：使用 pynput 监听热键
        按照用户要求简化：
        截图: Control + Option + Z
        划词: Control + Q
        """
        try:
            from pynput import keyboard
            
            # 使用用户指定的精准组合键
            hotkeys = {
                '<ctrl>+<alt>+z': self.on_trigger_screenshot, # 截图 (Mac 上的 alt 即 option)
                '<ctrl>+q': self.on_trigger_text              # 划词
            }

            print("[Listener] macOS 热键监听已启动:")
            print("       截图翻译: Control + Option + Z")
            print("       划词翻译: Control + Q")
            
            with keyboard.GlobalHotKeys(hotkeys) as self._listener:
                self._listener.join()
        except Exception as e:
            print(f"[Error] macOS 热键监听器启动失败: {e}")

    def on_trigger_screenshot(self):
        print("[Listener] 触发截图信号")
        self.trigger_signal.emit()

    def on_trigger_text(self):
        print("[Listener] 触发划词信号")
        self.text_trigger_signal.emit()

    def stop(self):
        self._running = False
        self._stop_mouse_listener()
        if self._system == "Windows" and self._win_thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._win_thread_id, 0x0012, 0, 0)
        else:
            if self._listener:
                self._listener.stop()
        print("[Listener] 系统热键监听正在停止...")
