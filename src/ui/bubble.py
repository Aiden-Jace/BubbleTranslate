from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QApplication,
    QScrollArea,
    QPushButton,
    QMenu,
    QWidgetAction,
    QGridLayout,
    QPlainTextEdit,
)
from PySide6.QtCore import Qt, QSize, QPoint, QRect, Signal, QTimer, QEvent
from PySide6.QtGui import QFont, QIcon, QPixmap
import sys
import os
from src import config
from src.core import translation_services
from src.resources import resource_path

class TranslationBubble(QWidget):
    source_edit_requested = Signal(str)
    language_changed = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 窗口属性：无边框、置顶
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        if sys.platform == "darwin":
            flags |= Qt.Window | Qt.NoDropShadowWindowHint
        else:
            flags |= Qt.Tool
            
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 用于拖拽的变量
        self._dragging = False
        self._drag_position = QPoint()
        self._default_position = getattr(config, "BUBBLE_DEFAULT_POSITION", "top_center")
        self.source_text = ""
        self.translation_text = ""
        self.placeholder_text = "正在翻译..."
        self.view_mode = "translation"
        self._updating_source_editor = False
        self.source_expanded = False
        self.translation_expanded = True
        self.translation_provider = config.TRANSLATION_MODE
        self.source_languages = []
        self.target_languages = []
        self.source_language = "自动检测"
        self.target_language = "中文"
        self.set_translation_provider(self.translation_provider, refresh_ui=False)
        self.language_menu = None
        self._language_menu_filter_installed = False
        self.icon_dir = resource_path("assets", "icons")
        self.expand_icon = self._load_svg_icon("chevron-right.svg")
        self.collapse_icon = self._load_svg_icon("chevron-down.svg")
        self.move_right_icon = self._load_svg_icon("move-right.svg", color="#526078")
        self.language_globe_icon = self._load_svg_icon("globe.svg", color="#526078")
        self.action_icons = {}
        self.edit_debounce_timer = QTimer(self)
        self.edit_debounce_timer.setSingleShot(True)
        self.edit_debounce_timer.timeout.connect(self._emit_source_edit_request)
        
        self.init_ui()
        self.apply_styles()
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)

    def init_ui(self):
        # 创建一个圆角背景容器
        self.container = QFrame(self)
        self.container.setObjectName("container")
        
        # 主容器布局
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(2, 2, 2, 2) # 为滚动条留一点空间
        container_layout.setSpacing(0)

        self.toolbar = QWidget(self.container)
        self.toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 4)
        toolbar_layout.setSpacing(6)

        self.language_button = QFrame()
        self.language_button.setObjectName("languageButton")
        self.language_button.setCursor(Qt.PointingHandCursor)
        self.language_button.mousePressEvent = self._handle_language_button_press
        self.language_button.mouseDoubleClickEvent = lambda event: event.accept()
        language_layout = QHBoxLayout(self.language_button)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_layout.setSpacing(5)

        self.source_language_label = QLabel()
        self.source_language_label.setObjectName("languageText")
        self.source_language_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.move_right_icon_button = QPushButton()
        self.move_right_icon_button.setObjectName("languageIconButton")
        self.move_right_icon_button.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.move_right_icon_button.setFocusPolicy(Qt.NoFocus)
        self.move_right_icon_button.setIcon(self.move_right_icon)
        self.move_right_icon_button.setIconSize(QSize(16, 16))
        self.move_right_icon_button.setFixedSize(18, 18)
        self.target_language_label = QLabel()
        self.target_language_label.setObjectName("languageText")
        self.target_language_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.dropdown_icon_button = QPushButton()
        self.dropdown_icon_button.setObjectName("languageIconButton")
        self.dropdown_icon_button.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.dropdown_icon_button.setFocusPolicy(Qt.NoFocus)
        self.dropdown_icon_button.setIcon(self.language_globe_icon)
        self.dropdown_icon_button.setIconSize(QSize(16, 16))
        self.dropdown_icon_button.setFixedSize(18, 18)

        language_layout.addWidget(self.dropdown_icon_button)
        language_layout.addWidget(self.source_language_label)
        language_layout.addWidget(self.move_right_icon_button)
        language_layout.addWidget(self.target_language_label)
        toolbar_layout.addWidget(self.language_button)
        toolbar_layout.addStretch()

        self.translation_view_button = self._create_action_button("译文", "messages-square.svg")
        self.edit_view_button = self._create_action_button("编辑", "square-pen.svg")
        self.speak_button = self._create_action_button("朗读", "volume-1.svg")
        self.copy_button = self._create_action_button("复制", "copy.svg")

        self.translation_view_button.clicked.connect(self.show_translation_view)
        self.edit_view_button.clicked.connect(self.show_edit_view)
        self.speak_button.clicked.connect(self._handle_speak_placeholder)
        self.copy_button.clicked.connect(self.copy_translation)

        toolbar_layout.addWidget(self.translation_view_button)
        toolbar_layout.addWidget(self.edit_view_button)
        toolbar_layout.addWidget(self.speak_button)
        toolbar_layout.addWidget(self.copy_button)
        self._update_language_button()
        
        # 创建滚动区域
        self.scroll_area = QScrollArea(self.container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                border: none;
                background: rgba(0,0,0,0);
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(100, 100, 100, 80);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # 翻译文本标签
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(15, 8, 15, 12)
        self.content_layout.setSpacing(8)

        self.source_title = QPushButton()
        self.source_title.setObjectName("sourceSectionHeader")
        self.source_title.setCursor(Qt.PointingHandCursor)
        self.source_title.setLayoutDirection(Qt.RightToLeft)
        self.source_title.clicked.connect(self.toggle_source_section)
        self.source_label = QLabel("")
        self.source_label.setObjectName("sourceText")
        self.source_label.setWordWrap(True)
        self.source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.source_label.setContextMenuPolicy(Qt.NoContextMenu)
        self.source_edit = QPlainTextEdit()
        self.source_edit.setObjectName("sourceEdit")
        self.source_edit.setFrameShape(QFrame.NoFrame)
        self.source_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.source_edit.setContextMenuPolicy(Qt.NoContextMenu)
        self.source_edit.setPlaceholderText("输入原文")
        self.source_edit.textChanged.connect(self._handle_source_edit_changed)

        self.translation_title = QPushButton()
        self.translation_title.setObjectName("translationSectionHeader")
        self.translation_title.setCursor(Qt.PointingHandCursor)
        self.translation_title.setLayoutDirection(Qt.RightToLeft)
        self.translation_title.clicked.connect(self.toggle_translation_section)
        self.translation_label = QLabel("正在翻译...")
        self.translation_label.setObjectName("translationText")
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextFormat(Qt.AutoText)
        self.translation_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.translation_label.setContextMenuPolicy(Qt.NoContextMenu)
        
        self.content_layout.addWidget(self.source_title)
        self.content_layout.addWidget(self.source_label)
        self.content_layout.addWidget(self.source_edit)
        self.content_layout.addWidget(self.translation_title)
        self.content_layout.addWidget(self.translation_label)
        self.scroll_area.setWidget(self.content_widget)
        
        container_layout.addWidget(self.toolbar)
        container_layout.addWidget(self.scroll_area)
        
        # 整体窗口布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def apply_styles(self):
        """根据最新配置应用样式"""
        # 1. 透明度
        self.setWindowOpacity(getattr(config, "BUBBLE_OPACITY", 0.95))
        
        # 2. 边框颜色与背景
        border_color = getattr(config, "BUBBLE_BORDER_COLOR", "#409EFF")
        accent_color = "#5169FF"
        self.container.setStyleSheet(f"""
            QFrame#container {{
                background-color: rgba(255, 255, 255, 245);
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
            QWidget#toolbar {{
                background: transparent;
            }}
            QFrame#languageButton {{
                background: transparent;
                border: none;
                padding: 4px 0;
            }}
            QFrame#languageButton:hover QLabel#languageText {{
                color: {accent_color};
            }}
            QLabel#languageText {{
                color: #3b4652;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#languageIconButton {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QPushButton#toolbarAction {{
                color: #526078;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 7px;
                font-size: 12px;
            }}
            QPushButton#toolbarAction:hover {{
                color: {accent_color};
                background: rgba(81, 105, 255, 16);
            }}
            QPushButton#toolbarAction:checked {{
                color: {accent_color};
                background: rgba(81, 105, 255, 24);
                border-color: rgba(81, 105, 255, 65);
            }}
            QPushButton#sourceSectionHeader, QPushButton#translationSectionHeader {{
                color: {accent_color};
                background: transparent;
                border: none;
                border-top: 1px solid rgba(130, 143, 168, 30);
                border-radius: 0;
                padding: 10px 0 8px 0;
                text-align: left;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#sourceSectionHeader {{
                color: #526078;
            }}
            QPushButton#sourceSectionHeader:hover, QPushButton#translationSectionHeader:hover {{
                color: {accent_color};
            }}
            QLabel#sourceText {{
                color: #4d5966;
                background: transparent;
                border: none;
                padding: 0 0 8px 0;
            }}
            QPlainTextEdit#sourceEdit {{
                color: #4d5966;
                background: transparent;
                border: none;
                padding: 0 0 8px 0;
            }}
            QLabel#translationText {{
                color: #172345;
                background: transparent;
                font-weight: bold;
            }}
        """)
        
        # 3. 字体大小
        font_size = getattr(config, "BUBBLE_FONT_SIZE", 11)
        font_families = ["PingFang SC", "Microsoft YaHei", "Segoe UI", "Arial"]
        font = QFont()
        font.setFamilies(font_families)
        font.setPointSize(font_size)
        self.source_label.setFont(font)
        self.translation_label.setFont(font)
        
        # 4. 宽度计算 (根据屏幕百分比)
        screen = QApplication.primaryScreen().availableGeometry()
        width_percent = getattr(config, "BUBBLE_WIDTH_PERCENT", 25)
        target_width = int(screen.width() * (width_percent / 100))
        # 限制最小宽度和最大宽度
        target_width = max(520, min(target_width, 860))
        self.setFixedWidth(target_width)
        text_width = target_width - 40
        self.source_label.setFixedWidth(text_width) # 减去边距和滚动条空间
        self.translation_label.setFixedWidth(text_width)
        
        # 如果气泡当前可见，且右侧超出屏幕，自动调整位置
        if self.isVisible():
            self._ensure_within_screen()

    def set_text(self, text):
        self.set_translation_text(text)

    def set_source_text(self, text):
        self.source_text = text or ""
        self._refresh_content()

    def set_translation_text(self, text):
        self.translation_text = text or ""
        self._refresh_content()

    def refresh_settings(self):
        if not getattr(config, "BUBBLE_MENU_ENABLED", True):
            self.view_mode = "translation"
            self.source_expanded = False
            self.translation_expanded = True
        self.apply_styles()
        self._refresh_content()
        default_position = getattr(config, "BUBBLE_DEFAULT_POSITION", "top_center")
        if default_position != self._default_position:
            self._default_position = default_position
            if self.isVisible():
                self.move_to_default_position()

    def set_translation_provider(self, provider, refresh_ui=True):
        self.translation_provider = provider.upper()
        self.source_languages, self.target_languages = (
            translation_services.get_language_options(self.translation_provider)
        )
        configured_source, configured_target = config.get_language_preference(
            self.translation_provider
        )
        self.source_language, self.target_language = (
            translation_services.normalize_language_selection(
                self.translation_provider,
                configured_source,
                configured_target,
            )
        )
        if refresh_ui and hasattr(self, "source_language_label"):
            self._update_language_button()

    def show_translation_view(self):
        self.view_mode = "translation"
        self.source_expanded = False
        self.translation_expanded = True
        self._refresh_content()

    def show_edit_view(self):
        self.view_mode = "edit"
        self.source_expanded = True
        self.translation_expanded = True
        self._sync_source_editor()
        self._refresh_content()

    def copy_translation(self):
        QApplication.clipboard().setText(self.translation_text or "")

    def _handle_speak_placeholder(self):
        print("[Bubble] 朗读功能暂未实现")

    def toggle_source_section(self):
        if self.view_mode != "edit":
            return
        self.source_expanded = not self.source_expanded
        self._refresh_content()

    def toggle_translation_section(self):
        if self.view_mode != "edit":
            return
        self.translation_expanded = not self.translation_expanded
        self._refresh_content()

    def show_language_menu(self):
        if self.language_menu and self.language_menu.isVisible():
            self.language_menu.close()
            return

        menu = QMenu(self)
        self.language_menu = menu
        menu.setObjectName("languageMenu")
        menu.aboutToHide.connect(lambda current_menu=menu: self._clear_language_menu(current_menu))
        menu.setStyleSheet("""
            QMenu#languageMenu {
                background: white;
                border: 1px solid rgba(120, 132, 158, 90);
                border-radius: 8px;
                padding: 8px;
            }
        """)

        panel = QWidget()
        grid = QGridLayout(panel)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        source_title = QLabel("原文语言")
        source_title.setObjectName("menuTitle")
        target_title = QLabel("译文语言")
        target_title.setObjectName("menuTitle")
        grid.addWidget(source_title, 0, 0)
        grid.addWidget(target_title, 0, 1)

        max_rows = max(len(self.source_languages), len(self.target_languages))
        for row in range(max_rows):
            if row < len(self.source_languages):
                lang = self.source_languages[row]
                button = self._create_language_option(lang, self.source_language == lang)
                button.clicked.connect(lambda checked=False, value=lang, popup=menu: self._select_source_language(value, popup))
                grid.addWidget(button, row + 1, 0)

            if row < len(self.target_languages):
                lang = self.target_languages[row]
                button = self._create_language_option(lang, self.target_language == lang)
                button.clicked.connect(lambda checked=False, value=lang, popup=menu: self._select_target_language(value, popup))
                grid.addWidget(button, row + 1, 1)

        panel.setStyleSheet("""
            QLabel#menuTitle {
                color: #7a8496;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton {
                color: #26324a;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 10px;
                text-align: left;
                min-width: 96px;
            }
            QPushButton:checked {
                color: #5169ff;
                background: rgba(81, 105, 255, 24);
                border-color: rgba(81, 105, 255, 80);
            }
            QPushButton:hover {
                background: rgba(81, 105, 255, 14);
            }
        """)

        scroll_panel = QScrollArea(menu)
        scroll_panel.setWidgetResizable(True)
        scroll_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_panel.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_panel.setFrameShape(QFrame.NoFrame)
        scroll_panel.setWidget(panel)
        scroll_panel.setStyleSheet("""
            QScrollArea {
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(0,0,0,0);
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(100, 100, 100, 80);
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        panel_height = panel.sizeHint().height()
        screen_height = QApplication.primaryScreen().availableGeometry().height()
        max_menu_height = min(420, int(screen_height * 0.55))
        scroll_panel.setFixedHeight(min(panel_height, max_menu_height))
        scroll_panel.setFixedWidth(panel.sizeHint().width() + 12)

        action = QWidgetAction(menu)
        action.setDefaultWidget(scroll_panel)
        menu.addAction(action)
        self._install_language_menu_filter()
        menu.popup(self.language_button.mapToGlobal(self.language_button.rect().bottomLeft()))

    def _clear_language_menu(self, menu):
        if self.language_menu is menu:
            self._remove_language_menu_filter()
            menu.deleteLater()
            self.language_menu = None

    def _install_language_menu_filter(self):
        if not self._language_menu_filter_installed:
            QApplication.instance().installEventFilter(self)
            self._language_menu_filter_installed = True

    def _remove_language_menu_filter(self):
        if self._language_menu_filter_installed:
            QApplication.instance().removeEventFilter(self)
            self._language_menu_filter_installed = False

    def contains_language_button(self, global_pos):
        if not self.isVisible() or not self.language_button.isVisible():
            return False
        return self.language_button.rect().contains(
            self.language_button.mapFromGlobal(global_pos)
        )

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.MouseButtonDblClick
            and event.button() == Qt.RightButton
            and isinstance(obj, QWidget)
            and self.isAncestorOf(obj)
            and obj is not self.language_button
            and not self.language_button.isAncestorOf(obj)
        ):
            self.hide()
            event.accept()
            return True
        if (
            self.language_menu
            and self.language_menu.isVisible()
            and event.type() == QEvent.MouseButtonPress
            and hasattr(event, "globalPosition")
        ):
            global_pos = event.globalPosition().toPoint()
            if self.contains_language_button(global_pos):
                self.language_menu.close()
                if event.button() == Qt.RightButton:
                    self._handle_language_button_press(event)
                return True

        return super().eventFilter(obj, event)

    def _handle_language_button_press(self, event):
        if event.button() == Qt.LeftButton:
            self.show_language_menu()
            event.accept()
        elif event.button() == Qt.RightButton:
            self.swap_languages()
            event.accept()

    def swap_languages(self):
        if self.language_menu:
            self.language_menu.close()
        source, target = self.target_language, self.source_language
        # 自动检测不能作为目标语言，也不能保存引擎不支持的语言组合。
        if source not in self.source_languages or target not in self.target_languages:
            return
        if (source, target) == (self.source_language, self.target_language):
            return
        self.source_language, self.target_language = source, target
        config.update_active_language(self.translation_provider, source, target)
        self._update_language_button()
        self.language_changed.emit(source, target)

    def _create_action_button(self, text, icon_name):
        button = QPushButton(text)
        button.setObjectName("toolbarAction")
        button.setCursor(Qt.PointingHandCursor)
        button.setCheckable(text in ("译文", "编辑"))
        button.setIcon(self._load_svg_icon(icon_name, color="#526078"))
        button.setIconSize(QSize(15, 15))
        return button

    def _handle_source_edit_changed(self):
        if self._updating_source_editor or self.view_mode != "edit":
            return

        self.source_text = self.source_edit.toPlainText()
        self._resize_to_content()
        self.edit_debounce_timer.start(1000)

    def _emit_source_edit_request(self):
        text = self.source_edit.toPlainText().strip()
        if text:
            self.source_edit_requested.emit(text)

    def _sync_source_editor(self):
        self._updating_source_editor = True
        self.source_edit.setPlainText(self.source_text)
        self._updating_source_editor = False

    def _create_language_option(self, text, checked):
        button = QPushButton(f"✓ {text}" if checked else text)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _select_source_language(self, language, menu):
        if self.source_language == language:
            menu.close()
            return
        self.source_language = language
        config.update_active_language(
            self.translation_provider,
            self.source_language,
            self.target_language,
        )
        self._update_language_button()
        menu.close()
        self.language_changed.emit(self.source_language, self.target_language)

    def _select_target_language(self, language, menu):
        if self.target_language == language:
            menu.close()
            return
        self.target_language = language
        config.update_active_language(
            self.translation_provider,
            self.source_language,
            self.target_language,
        )
        self._update_language_button()
        menu.close()
        self.language_changed.emit(self.source_language, self.target_language)

    def _update_language_button(self):
        self.source_language_label.setText(self.source_language)
        self.target_language_label.setText(self.target_language)
        if self.source_language == "自动检测":
            self.language_button.setToolTip("左键选择语言；先选择具体原文语言，再右键交换原文与译文语言")
        else:
            self.language_button.setToolTip("左键选择语言；右键交换原文与译文语言")

    def _refresh_content(self):
        has_source = bool(self.source_text.strip())
        has_translation = bool(self.translation_text.strip())
        edit_mode = self.view_mode == "edit"
        menu_enabled = getattr(config, "BUBBLE_MENU_ENABLED", True)

        self.toolbar.setVisible(menu_enabled)

        self._set_section_button(self.source_title, "原文", self.source_expanded)
        self._set_section_button(self.translation_title, "译文", self.translation_expanded)

        self.translation_view_button.setChecked(self.view_mode == "translation")
        self.edit_view_button.setChecked(edit_mode)

        self.source_title.setVisible(edit_mode)
        self.source_label.setVisible(False)
        self.source_edit.setVisible(edit_mode and self.source_expanded)
        self.translation_title.setVisible(edit_mode)
        self.translation_label.setVisible((not edit_mode) or self.translation_expanded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.source_label.setText(self.source_text if has_source else "暂无原文")
        if edit_mode and not self.source_edit.hasFocus():
            self._sync_source_editor()
        self.translation_label.setText(self.translation_text if has_translation else self.placeholder_text)

        self._resize_to_content()
        QApplication.processEvents()

    def _set_section_button(self, button, text, expanded):
        button.setText(text)
        button.setIcon(self.collapse_icon if expanded else self.expand_icon)
        button.setIconSize(QSize(15, 15))

    def _load_svg_icon(self, filename, color="#7a8496"):
        path = os.path.join(self.icon_dir, filename)
        if not os.path.exists(path):
            return QIcon()

        with open(path, "r", encoding="utf-8") as f:
            svg = f.read().replace("currentColor", color)

        pixmap = QPixmap()
        pixmap.loadFromData(svg.encode("utf-8"), "SVG")
        return QIcon(pixmap)

    def _resize_to_content(self):
        content_width = max(220, self.width() - 40)
        self._prepare_visible_widgets_for_measure(content_width)
        content_height = self._calculate_single_content_height(content_width)

        toolbar_height = (
            self.toolbar.sizeHint().height()
            if not self.toolbar.isHidden()
            else 0
        )
        container_extra = 10

        screen_height = QApplication.primaryScreen().availableGeometry().height()
        available_window_height = int(screen_height * 0.92)
        available_scroll_height = max(80, available_window_height - toolbar_height - container_extra)
        needed_scroll_height = content_height + 4
        scroll_height = min(needed_scroll_height, available_scroll_height)

        self.scroll_area.setFixedHeight(scroll_height)
        self.setFixedHeight(toolbar_height + scroll_height + container_extra)

    def _prepare_visible_widgets_for_measure(self, content_width):
        for widget in (
            self.source_title,
            self.source_label,
            self.source_edit,
            self.translation_title,
            self.translation_label,
        ):
            if not widget.isHidden():
                widget.setFixedWidth(content_width)

        if not self.source_edit.isHidden():
            self.source_edit.document().setTextWidth(max(1, content_width - 18))
            self.source_edit.setFixedHeight(self._plain_text_edit_height(self.source_edit, content_width))

        self.content_layout.activate()
        self.content_widget.updateGeometry()

    def _calculate_single_content_height(self, content_width):
        visible_widgets = [
            widget for widget in (
                self.source_title,
                self.source_label,
                self.source_edit,
                self.translation_title,
                self.translation_label,
            )
            if not widget.isHidden()
        ]
        return self._calculate_layout_height(visible_widgets, self.content_layout, content_width)

    def _calculate_layout_height(self, widgets, layout, width):
        margins = layout.contentsMargins()
        total = margins.top() + margins.bottom()
        if widgets:
            total += layout.spacing() * (len(widgets) - 1)

        for widget in widgets:
            total += self._label_height_for_width(widget, width)

        return total

    def _label_height_for_width(self, label, width):
        label.setFixedWidth(width)
        if isinstance(label, QPlainTextEdit):
            return self._plain_text_edit_height(label, width)
        if hasattr(label, "wordWrap") and label.wordWrap() and label.hasHeightForWidth():
            return label.heightForWidth(width)
        return label.sizeHint().height()

    def _plain_text_edit_height(self, editor, width):
        text = editor.toPlainText() or editor.placeholderText() or " "
        text_width = max(1, width - 18)
        rect = editor.fontMetrics().boundingRect(
            QRect(0, 0, text_width, 100000),
            Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
            text
        )
        return max(110, rect.height() + 30)

    def _ensure_within_screen(self):
        """确保气泡窗口至少有 10% 保留在屏幕内，防止完全丢失"""
        screen = QApplication.primaryScreen().availableGeometry()
        pos = self.pos()
        new_x = pos.x()
        new_y = pos.y()
        
        # 允许拖出的最大范围：保留 10% 的宽度/高度在屏幕内
        min_visible_w = int(self.width() * 0.1)
        min_visible_h = int(self.height() * 0.1)
        
        # 1. 检查右边界：左侧坐标不能超过 (屏幕宽 - 最小保留宽)
        if pos.x() > screen.left() + screen.width() - min_visible_w:
            new_x = screen.left() + screen.width() - min_visible_w
            
        # 2. 检查左边界：右侧坐标 (pos.x + width) 不能小于 最小保留宽
        if pos.x() + self.width() < screen.left() + min_visible_w:
            new_x = screen.left() + min_visible_w - self.width()
            
        # 3. 检查下边界：上方坐标不能超过 (屏幕高 - 最小保留高)
        if pos.y() > screen.top() + screen.height() - min_visible_h:
            new_y = screen.top() + screen.height() - min_visible_h
            
        # 4. 检查上边界：下方坐标 (pos.y + height) 不能小于 最小保留高
        if pos.y() + self.height() < screen.top() + min_visible_h:
            new_y = screen.top() + min_visible_h - self.height()
        
        if new_x != pos.x() or new_y != pos.y():
            self.move(new_x, new_y)

    def move_to_default_position(self):
        """将气泡移动到配置指定的屏幕顶部位置。"""
        screen = QApplication.primaryScreen().availableGeometry()
        position = getattr(config, "BUBBLE_DEFAULT_POSITION", "top_center")
        margin = min(30, max(0, (screen.width() - self.width()) // 2))
        if position == "top_left":
            x = screen.left() + margin
        elif position == "top_right":
            x = screen.left() + screen.width() - self.width() - margin
        else:
            x = screen.left() + max(0, (screen.width() - self.width()) // 2)
        y = screen.top() + 30
        self.move(x, y)

    def show_translation(self, text, mouse_pos=None, source_text=None):
        """显示翻译，初始位置使用用户设置的默认位置。"""
        # 每次显示前重新应用样式，以防设置已更改
        self.apply_styles()
        self.source_text = source_text or ""
        self.translation_text = text or ""
        self.view_mode = "translation"
        self.source_expanded = False
        self.translation_expanded = True
        self._sync_source_editor()
        self._refresh_content()
        if not self.isVisible():
            self.move_to_default_position()
        else:
            # 如果已显示，确保位置在屏幕内
            self._ensure_within_screen()
            
        self.show()
        # 强制置顶并激活
        self.raise_()
        if sys.platform == "darwin":
            self.activateWindow()

    # --- 交互逻辑 ---

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            event.accept()
        elif event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.RightButton:
            self.hide()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        # 释放鼠标时也检查一下是否拖出了屏幕
        self._ensure_within_screen()
        event.accept()

