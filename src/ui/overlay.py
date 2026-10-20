from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QImage, QKeyEvent
from PIL import Image
import sys

class CaptureOverlay(QWidget):
    # 发送：裁剪后的 PIL 图片，选框位置
    area_selected = Signal(object, QRect)
    # 请求退出整个模式
    exit_requested = Signal()
    # 请求清空当前结果（重置为待选状态）
    reset_requested = Signal()

    def __init__(self):
        super().__init__()
        # 在 macOS 上，使用更标准的窗口标志以确保能接收所有输入事件
        if sys.platform == "darwin":
            # 使用 Window 标志，并确保它是一个无边框、置顶的全屏窗口
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Window
        else:
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        
        self.setWindowFlags(flags)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WA_TranslucentBackground)
        else:
            # 截图已覆盖整个窗口；遮罩直接画在截图上，无需透明原生窗口。
            self.setAttribute(Qt.WA_OpaquePaintEvent)
        # 确保能接收鼠标移动事件
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        
        # 强化焦点和输入能力
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, False)
        
        # 关键：在某些系统上，透明背景可能导致点击“穿透”，我们需要确保它捕获点击
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        
        self.pixmap = None
        self.dpi_ratio = 1.0
        # 选框状态
        self.selection_start = QPoint()
        self.selection_current = QPoint()
        self.is_selecting = False
        self.drag_threshold = 3
        self.persisted_rect = None
        self._hint_font = QFont()
        self._hint_font.setFamilies(["Microsoft YaHei", "PingFang SC", "Segoe UI", "Arial"])
        self._hint_font.setPointSize(11)
        self._hint_font.setBold(True)

    def set_data(self, pixmap, dpi_ratio):
        self.pixmap = pixmap
        self.dpi_ratio = dpi_ratio
        self.persisted_rect = None 
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_current = QPoint()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.pixmap:
            painter.drawPixmap(self.rect(), self.pixmap)
        else:
            painter.fillRect(self.rect(), Qt.black)
        
        # 蒙版
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        
        if self.is_selecting:
            selection_rect = QRect(self.selection_start, self.selection_current).normalized()
            painter.setPen(QPen(QColor(0, 174, 255), 2, Qt.DashLine))
            painter.fillRect(selection_rect, QColor(0, 174, 255, 40))
            painter.drawRect(selection_rect)
            painter.setPen(Qt.white)
            painter.drawText(selection_rect, Qt.AlignCenter, "松开翻译")
        elif self.persisted_rect:
            painter.setPen(QPen(QColor(0, 174, 255), 2, Qt.SolidLine))
            painter.fillRect(self.persisted_rect, QColor(0, 174, 255, 20))
            painter.drawRect(self.persisted_rect)

        painter.setPen(Qt.white)
        painter.setFont(self._hint_font)
        painter.drawText(self.rect().adjusted(25, 25, -25, -25), Qt.AlignLeft | Qt.AlignTop, "左键框选翻译，双击右键或 Esc 退出翻译")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selection_start = event.pos()
            self.selection_current = event.pos()
            self.is_selecting = False
            if self.persisted_rect:
                self.reset_requested.emit()
            self.persisted_rect = None
            self.update()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            print("[Overlay] 检测到 Esc 键")
            self.exit_requested.emit()
        event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            pos = event.pos()
            dist = (pos - self.selection_start).manhattanLength()
            if dist > self.drag_threshold:
                old_rect = QRect(self.selection_start, self.selection_current).normalized()
                self.is_selecting = True
                self.selection_current = pos
                new_rect = QRect(self.selection_start, self.selection_current).normalized()
                self.update(old_rect.united(new_rect).adjusted(-3, -3, 3, 3))
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            final_rect = QRect(self.selection_start, self.selection_current).normalized()
            if final_rect.width() > 5 and final_rect.height() > 5:
                self.persisted_rect = final_rect
                self.process_selection(final_rect)
            self.is_selecting = False
            self.update()
            event.accept()

    def process_selection(self, rect):
        if not self.pixmap: return
        p_rect = QRect(
            round(rect.x() * self.dpi_ratio), round(rect.y() * self.dpi_ratio),
            round(rect.width() * self.dpi_ratio), round(rect.height() * self.dpi_ratio),
        )
        qimage = self.pixmap.copy(p_rect).toImage().convertToFormat(QImage.Format_RGB888)
        pil_img = Image.frombytes(
            "RGB", (qimage.width(), qimage.height()), qimage.constBits(),
            "raw", "RGB", qimage.bytesPerLine(),
        )
        self.area_selected.emit(pil_img, rect)

    def exit_mode(self):
        self.persisted_rect = None
        self.is_selecting = False
        self.selection_start = QPoint()
        self.selection_current = QPoint()
        # 隐藏后 update() 不会立即重绘，复用原生窗口时可能闪出缓存的旧选框。
        # 保留截图作为背景，在窗口仍可见时同步擦除选框，再隐藏并释放截图。
        if self.isVisible():
            self.repaint()
        self.hide()
        self.pixmap = None

    def show_full_screen(self):
        # 强制更新几何尺寸并显示
        screen_geo = self.screen().geometry()
        self.setGeometry(screen_geo)
        
        # 无边框置顶窗口按屏幕尺寸覆盖即可，避免进入/退出全屏状态的系统过渡。
        self.showNormal()
            
        self.raise_()
        self.activateWindow()
        self.setFocus()
