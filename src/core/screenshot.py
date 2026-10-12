import mss
import sys
from PIL import Image
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage


class _CaptureWorker(QObject):
    ready = Signal(int, QImage)
    failed = Signal(int, str)

    def __init__(self):
        super().__init__()
        self._screen = None

    def _grab(self):
        # MSS 的原生句柄属于创建它的线程；初始化、预热和截屏均在此线程。
        if self._screen is None:
            self._screen = mss.mss()
        return self._screen.grab(self._screen.monitors[0])

    @Slot()
    def warm_up(self):
        try:
            if sys.platform == "darwin":
                # macOS 首次屏幕录制授权留到用户主动截屏时。
                if self._screen is None:
                    self._screen = mss.mss()
            else:
                self._grab()  # 提前准备原生截屏缓冲区，不保留桌面内容。
        except Exception:
            self.close()

    @Slot(int)
    def capture(self, request_id):
        try:
            screenshot = self._grab()
            # BGRA 可直接交给 Qt，跳过整屏 PIL/RGB 转换；copy 保证跨线程内存独立。
            frame = QImage(
                screenshot.bgra, screenshot.width, screenshot.height,
                screenshot.width * 4, QImage.Format_RGB32,
            ).copy()
            self.ready.emit(request_id, frame)
        except Exception as error:
            self.close()
            self.failed.emit(request_id, str(error))

    @Slot()
    def close(self):
        if self._screen is not None:
            self._screen.close()
            self._screen = None


class CaptureService(QObject):
    """复用后台截屏线程，界面线程仅负责显示图片。"""
    ready = Signal(int, QImage)
    failed = Signal(int, str)
    _requested = Signal(int)
    _warm_up_requested = Signal()
    _invalidated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = _CaptureWorker()
        self._worker.moveToThread(self._thread)
        self._requested.connect(self._worker.capture)
        self._warm_up_requested.connect(self._worker.warm_up)
        self._invalidated.connect(self._worker.close)
        self._worker.ready.connect(self.ready)
        self._worker.failed.connect(self.failed)
        self._thread.finished.connect(self._worker.close)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def warm_up(self):
        self._warm_up_requested.emit()

    def capture(self, request_id):
        self._requested.emit(request_id)

    def invalidate(self, *args):
        # 显示器分辨率或连接状态改变后重新获取屏幕布局。
        self._invalidated.emit()

    def stop(self):
        self._thread.quit()
        self._thread.wait()

def capture_screen():
    """
    Captures the entire screen using mss and returns it as a PIL.Image.
    Handles multiple monitors correctly.
    """
    with mss.mss() as sct:
        # Get the dimensions of all monitors combined (monitor 0)
        monitor = sct.monitors[0]
        sct_img = sct.grab(monitor)
        
        # Convert mss image to PIL Image
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        return img

def get_dpi_scaling():
    """
    获取系统 DPI 缩放比例
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        return app.primaryScreen().devicePixelRatio()
    return 1.0

if __name__ == "__main__":
    # Test capture
    img = capture_screen()
    print(f"Captured screen size: {img.size}")
    img.save("test_screenshot.png")
    print("Screenshot saved to test_screenshot.png")
