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
        self.setAttribute(Qt.WA_TranslucentBackground)
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

    def set_data(self, pixmap, dpi_ratio):
        self.pixmap = pixmap
        self.dpi_ratio = dpi_ratio
        self.persisted_rect = None 
        self.is_selecting = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.pixmap:
            painter.drawPixmap(self.rect(), self.pixmap)
        
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
        font = QFont()
        font.setFamilies(["Microsoft YaHei", "PingFang SC", "Segoe UI", "Arial"])
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect().adjusted(25, 25, -25, -25), Qt.AlignLeft | Qt.AlignTop, "左键框选翻译，右键或 Esc 退出翻译")

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
                self.is_selecting = True
                self.selection_current = pos
                self.update()
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
        p_rect = QRect(rect.x()*self.dpi_ratio, rect.y()*self.dpi_ratio, rect.width()*self.dpi_ratio, rect.height()*self.dpi_ratio)
        qimage = self.pixmap.copy(p_rect).toImage().convertToFormat(QImage.Format_RGB888)
        pil_img = Image.frombytes("RGB", (qimage.width(), qimage.height()), qimage.bits(), "raw", "RGB")
        self.area_selected.emit(pil_img, rect)

    def exit_mode(self):
        self.hide()
        self.pixmap = None 
        self.persisted_rect = None
        self.is_selecting = False
        self.update()

    def show_full_screen(self):
        # 强制更新几何尺寸并显示
        screen_geo = self.screen().geometry()
        self.setGeometry(screen_geo)
        
        if sys.platform == "darwin":
            self.showNormal()
        else:
            self.showFullScreen()
            
        self.raise_()
        self.activateWindow()
        self.setFocus()
