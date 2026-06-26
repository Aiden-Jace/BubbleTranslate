import mss
from PIL import Image

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
