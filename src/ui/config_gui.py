from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QFormLayout, 
                             QGroupBox, QCheckBox, QMessageBox,
                             QSlider, QSpinBox, QColorDialog, QTabWidget,
                             QScrollArea, QFrame, QKeySequenceEdit)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QColor, QKeySequence
import src.config as config
from src.core.autostart import set_autostart
import os
import requests
from src.core import translation_services
from src.core.hotkeys import validate_hotkeys
from src.resources import resource_path

class ConfigWindow(QWidget):
    settings_saved = Signal(str, str, str)
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("设置 - 气泡翻译")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setFixedSize(560, 520)
        
        # 设置窗口图标
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d9dee8;
                border-radius: 6px;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                color: #657087;
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 72px;
                padding: 10px 14px;
                font-size: 13px;
            }
            QTabBar::tab:hover {
                color: #3f506d;
            }
            QTabBar::tab:selected {
                color: #5169ff;
                border-bottom-color: #5169ff;
                font-weight: bold;
            }
            QGroupBox {
                color: #34415a;
                font-weight: bold;
                border: 1px solid #e1e5ed;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)

        # 设置
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)
        settings_layout.setContentsMargins(16, 16, 16, 16)

        core_group = QGroupBox("核心逻辑设置")
        core_layout = QFormLayout()
        core_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("大模型翻译", "LLM")
        self.mode_combo.addItem("DeepL", "DEEPL")
        self.mode_combo.addItem("百度翻译", "BAIDU")
        self.mode_combo.addItem("有道翻译", "YOUDAO")
        self.mode_combo.addItem("Google 免费翻译", "GOOGLE")
        mode_index = self.mode_combo.findData(config.TRANSLATION_MODE)
        self.mode_combo.setCurrentIndex(max(0, mode_index))
        core_layout.addRow("翻译主引擎:", self.mode_combo)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItem("本地 CPU OCR（无需显卡或 OCR API）", "LOCAL_CPU")
        self.strategy_combo.addItem("OCR API 识别后翻译", "OCR_LLM")
        self.strategy_combo.addItem("VLM 识别后翻译", "VLM")
        strategy_index = self.strategy_combo.findData(config.SCREENSHOT_STRATEGY)
        self.strategy_combo.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)
        self.strategy_combo.setToolTip("本地 CPU OCR 首次使用可能需要下载模型，之后识别无需联网。可搭配 Google 免费翻译。")
        core_layout.addRow("截图翻译策略:", self.strategy_combo)

        self.language_preferences = {}
        for provider in translation_services.PROVIDERS:
            source, target = config.get_language_preference(provider)
            self.language_preferences[provider] = list(
                translation_services.normalize_language_selection(
                    provider,
                    source,
                    target,
                )
            )

        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        core_layout.addRow("原文语言:", self.source_lang_combo)
        core_layout.addRow("目标翻译语言:", self.target_lang_combo)
        self._current_language_provider = self.mode_combo.currentData()
        self._load_language_options(self._current_language_provider)
        self.mode_combo.currentIndexChanged.connect(self._handle_provider_changed)
        
        # 1.1 自启动设置
        self.autostart_check = QCheckBox("开机自启动")
        self.autostart_check.setChecked(getattr(config, "AUTO_START", False))
        core_layout.addRow("系统设置:", self.autostart_check)

        self.auto_selection_check = QCheckBox("选中文本后显示翻译按钮")
        self.auto_selection_check.setChecked(
            getattr(config, "AUTO_SELECTION_ENABLED", True)
        )
        core_layout.addRow("划词提示:", self.auto_selection_check)
        
        core_group.setLayout(core_layout)
        settings_layout.addWidget(core_group)
        settings_layout.addStretch()
        self.tabs.addTab(settings_page, "设置")

        hotkey_page = QWidget()
        hotkey_layout = QVBoxLayout(hotkey_page)
        hotkey_layout.setContentsMargins(16, 16, 16, 16)
        hotkey_group = QGroupBox("翻译快捷键")
        hotkey_form = QFormLayout(hotkey_group)
        self.screenshot_hotkey_edit = QKeySequenceEdit(QKeySequence(config.SCREENSHOT_HOTKEY))
        self.text_hotkey_edit = QKeySequenceEdit(QKeySequence(config.TEXT_HOTKEY))
        for editor in (self.screenshot_hotkey_edit, self.text_hotkey_edit):
            editor.setMaximumSequenceLength(1)
        hotkey_form.addRow("截屏翻译:", self.screenshot_hotkey_edit)
        hotkey_form.addRow("划词翻译:", self.text_hotkey_edit)
        hotkey_hint = QLabel("点击输入框后按下快捷键。默认 F1 截屏翻译，F2 划词翻译。保存后立即生效。")
        hotkey_hint.setWordWrap(True)
        hotkey_form.addRow(hotkey_hint)
        reset_hotkeys_button = QPushButton("恢复默认快捷键")
        reset_hotkeys_button.clicked.connect(self.reset_hotkeys)
        hotkey_form.addRow(reset_hotkeys_button)
        hotkey_layout.addWidget(hotkey_group)
        hotkey_layout.addStretch()
        self.tabs.addTab(hotkey_page, "快捷键")

        # 气泡
        bubble_page = QWidget()
        bubble_layout = QVBoxLayout(bubble_page)
        bubble_layout.setContentsMargins(16, 16, 16, 16)

        style_group = QGroupBox("翻译气泡样式")
        style_layout = QFormLayout()
        style_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.bubble_menu_check = QCheckBox("气泡菜单")
        self.bubble_menu_check.setChecked(
            getattr(config, "BUBBLE_MENU_ENABLED", True)
        )
        style_layout.addRow("菜单显示:", self.bubble_menu_check)

        self.bubble_position_combo = QComboBox()
        self.bubble_position_combo.addItem("右上角", "top_right")
        self.bubble_position_combo.addItem("左上角", "top_left")
        self.bubble_position_combo.addItem("顶部居中", "top_center")
        position_index = self.bubble_position_combo.findData(
            getattr(config, "BUBBLE_DEFAULT_POSITION", "top_center")
        )
        self.bubble_position_combo.setCurrentIndex(position_index if position_index >= 0 else 2)
        style_layout.addRow("默认显示位置:", self.bubble_position_combo)
        
        opacity_container = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(20, 100)
        self.opacity_slider.setValue(int(getattr(config, "BUBBLE_OPACITY", 0.95) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        opacity_container.addWidget(self.opacity_slider)
        opacity_container.addWidget(self.opacity_label)
        self.opacity_slider.setToolTip("100% 完全不透明；数值越低越透明")
        style_layout.addRow("气泡不透明度:", opacity_container)
        
        color_container = QHBoxLayout()
        self.current_border_color = getattr(config, "BUBBLE_BORDER_COLOR", "#409EFF")
        self.color_preview = QPushButton()
        self.color_preview.setFixedWidth(60)
        self.color_preview.setStyleSheet(f"background-color: {self.current_border_color}; border: 1px solid gray;")
        self.color_btn = QPushButton("选择颜色")
        self.color_btn.clicked.connect(self.pick_color)
        color_container.addWidget(self.color_preview)
        color_container.addWidget(self.color_btn)
        color_container.addStretch()
        style_layout.addRow("边框颜色:", color_container)
        
        self.source_font_size_spin = QSpinBox()
        self.source_font_size_spin.setRange(8, 30)
        self.source_font_size_spin.setValue(config.BUBBLE_SOURCE_FONT_SIZE)
        style_layout.addRow("原文字体大小:", self.source_font_size_spin)

        self.translation_font_size_spin = QSpinBox()
        self.translation_font_size_spin.setRange(8, 30)
        self.translation_font_size_spin.setValue(config.BUBBLE_FONT_SIZE)
        style_layout.addRow("译文字体大小:", self.translation_font_size_spin)
        
        width_container = QHBoxLayout()
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(10, 80)
        self.width_slider.setValue(getattr(config, "BUBBLE_WIDTH_PERCENT", 25))
        self.width_label = QLabel(f"{self.width_slider.value()}%")
        self.width_slider.valueChanged.connect(lambda v: self.width_label.setText(f"{v}%"))
        width_container.addWidget(self.width_slider)
        width_container.addWidget(self.width_label)
        style_layout.addRow("气泡宽度(占屏幕):", width_container)
        
        style_group.setLayout(style_layout)
        bubble_layout.addWidget(style_group)
        bubble_layout.addStretch()
        self.tabs.addTab(bubble_page, "气泡")

        # API
        api_page = QScrollArea()
        api_page.setWidgetResizable(True)
        api_page.setFrameShape(QFrame.NoFrame)
        api_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        api_content = QWidget()
        api_page.setWidget(api_content)
        api_page_layout = QVBoxLayout(api_content)
        api_page_layout.setContentsMargins(16, 16, 16, 16)

        api_group = QGroupBox("翻译模型 API")
        api_layout = QFormLayout()
        api_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.api_key_edit = QLineEdit(config.API_KEY)
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key_edit)
        
        self.base_url_edit = QLineEdit(config.BASE_URL)
        api_layout.addRow("Base URL:", self.base_url_edit)
        api_group.setLayout(api_layout)
        api_page_layout.addWidget(api_group)

        ocr_api_group = QGroupBox("OCR 模型 API")
        ocr_api_layout = QFormLayout()
        ocr_api_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.ocr_api_key_edit = QLineEdit(config.OCR_API_KEY)
        self.ocr_api_key_edit.setEchoMode(QLineEdit.Password)
        ocr_api_layout.addRow("API Key:", self.ocr_api_key_edit)

        self.ocr_base_url_edit = QLineEdit(config.OCR_BASE_URL)
        ocr_api_layout.addRow("Base URL:", self.ocr_base_url_edit)

        ocr_api_group.setLayout(ocr_api_layout)
        api_page_layout.addWidget(ocr_api_group)

        deepl_group = QGroupBox("DeepL API")
        deepl_layout = QFormLayout()
        deepl_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.deepl_key_edit = QLineEdit(config.DEEPL_API_KEY)
        self.deepl_key_edit.setEchoMode(QLineEdit.Password)
        deepl_layout.addRow("DeepL Key:", self.deepl_key_edit)

        self.deepl_url_edit = QLineEdit(config.DEEPL_API_URL)
        deepl_layout.addRow("API URL:", self.deepl_url_edit)

        deepl_group.setLayout(deepl_layout)
        api_page_layout.addWidget(deepl_group)

        baidu_group = QGroupBox("百度翻译 API")
        baidu_layout = QFormLayout()
        baidu_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.baidu_app_id_edit = QLineEdit(config.BAIDU_APP_ID)
        baidu_layout.addRow("App ID:", self.baidu_app_id_edit)
        self.baidu_secret_edit = QLineEdit(config.BAIDU_SECRET_KEY)
        self.baidu_secret_edit.setEchoMode(QLineEdit.Password)
        baidu_layout.addRow("密钥:", self.baidu_secret_edit)
        self.baidu_url_edit = QLineEdit(config.BAIDU_API_URL)
        baidu_layout.addRow("API URL:", self.baidu_url_edit)

        baidu_group.setLayout(baidu_layout)
        api_page_layout.addWidget(baidu_group)

        youdao_group = QGroupBox("有道翻译 API")
        youdao_layout = QFormLayout()
        youdao_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.youdao_app_key_edit = QLineEdit(config.YOUDAO_APP_KEY)
        youdao_layout.addRow("应用 ID:", self.youdao_app_key_edit)
        self.youdao_secret_edit = QLineEdit(config.YOUDAO_APP_SECRET)
        self.youdao_secret_edit.setEchoMode(QLineEdit.Password)
        youdao_layout.addRow("应用密钥:", self.youdao_secret_edit)
        self.youdao_url_edit = QLineEdit(config.YOUDAO_API_URL)
        youdao_layout.addRow("API URL:", self.youdao_url_edit)

        youdao_group.setLayout(youdao_layout)
        api_page_layout.addWidget(youdao_group)
        api_page_layout.addStretch()

        # 模型
        model_page = QWidget()
        model_page_layout = QVBoxLayout(model_page)
        model_page_layout.setContentsMargins(16, 16, 16, 16)

        llm_group = QGroupBox("模型选择")
        llm_layout = QFormLayout()
        llm_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        
        chat_model_container = QHBoxLayout()
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setEditable(True)
        self.chat_model_combo.addItem(config.CHAT_MODEL)
        self.chat_model_combo.setCurrentText(config.CHAT_MODEL)
        
        self.refresh_chat_btn = QPushButton("刷新列表")
        self.refresh_chat_btn.clicked.connect(
            lambda: self.fetch_models(
                self.chat_model_combo,
                self.refresh_chat_btn,
                self.base_url_edit,
                self.api_key_edit,
            )
        )
        
        chat_model_container.addWidget(self.chat_model_combo)
        chat_model_container.addWidget(self.refresh_chat_btn)
        llm_layout.addRow("翻译模型:", chat_model_container)

        ocr_model_container = QHBoxLayout()
        self.ocr_model_combo = QComboBox()
        self.ocr_model_combo.setEditable(True)
        self.ocr_model_combo.addItem(config.OCR_MODEL)
        self.ocr_model_combo.setCurrentText(config.OCR_MODEL)
        
        self.refresh_ocr_btn = QPushButton("刷新列表")
        self.refresh_ocr_btn.clicked.connect(
            lambda: self.fetch_models(
                self.ocr_model_combo,
                self.refresh_ocr_btn,
                self.ocr_base_url_edit,
                self.ocr_api_key_edit,
            )
        )
        
        ocr_model_container.addWidget(self.ocr_model_combo)
        ocr_model_container.addWidget(self.refresh_ocr_btn)
        llm_layout.addRow("OCR 模型:", ocr_model_container)
        
        llm_group.setLayout(llm_layout)
        model_page_layout.addWidget(llm_group)
        model_page_layout.addStretch()

        self.tabs.addTab(model_page, "模型")
        self.tabs.addTab(api_page, "API")
        layout.addWidget(self.tabs)

        self.save_btn = QPushButton("保存并应用配置")
        self.save_btn.setFixedHeight(45)
        self.save_btn.setStyleSheet("background-color: #409EFF; color: white; border-radius: 6px; font-weight: bold; font-size: 14px;")
        self.save_btn.clicked.connect(self.save_config)
        layout.addWidget(self.save_btn)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_border_color), self, "选择气泡边框颜色")
        if color.isValid():
            self.current_border_color = color.name().upper()
            self.color_preview.setStyleSheet(f"background-color: {self.current_border_color}; border: 1px solid gray;")

    def reset_hotkeys(self):
        self.screenshot_hotkey_edit.setKeySequence(QKeySequence("F1"))
        self.text_hotkey_edit.setKeySequence(QKeySequence("F2"))

    def refresh_hotkey_settings(self):
        self.screenshot_hotkey_edit.setKeySequence(QKeySequence(config.SCREENSHOT_HOTKEY))
        self.text_hotkey_edit.setKeySequence(QKeySequence(config.TEXT_HOTKEY))

    def _store_current_language_selection(self):
        if not self._current_language_provider:
            return
        self.language_preferences[self._current_language_provider] = [
            self.source_lang_combo.currentText(),
            self.target_lang_combo.currentText(),
        ]

    def _load_language_options(self, provider):
        source_languages, target_languages = (
            translation_services.get_language_options(provider)
        )
        source, target = self.language_preferences[provider]
        source, target = translation_services.normalize_language_selection(
            provider,
            source,
            target,
        )
        self.language_preferences[provider] = [source, target]

        self.source_lang_combo.blockSignals(True)
        self.target_lang_combo.blockSignals(True)
        self.source_lang_combo.clear()
        self.source_lang_combo.addItems(source_languages)
        self.source_lang_combo.setCurrentText(source)
        self.target_lang_combo.clear()
        self.target_lang_combo.addItems(target_languages)
        self.target_lang_combo.setCurrentText(target)
        self.source_lang_combo.blockSignals(False)
        self.target_lang_combo.blockSignals(False)

    def _handle_provider_changed(self):
        self._store_current_language_selection()
        self._current_language_provider = self.mode_combo.currentData()
        self._load_language_options(self._current_language_provider)

    def refresh_language_settings(self):
        self.language_preferences = {}
        for provider in translation_services.PROVIDERS:
            source, target = config.get_language_preference(provider)
            self.language_preferences[provider] = list(
                translation_services.normalize_language_selection(
                    provider,
                    source,
                    target,
                )
            )

        self.mode_combo.blockSignals(True)
        mode_index = self.mode_combo.findData(config.TRANSLATION_MODE)
        self.mode_combo.setCurrentIndex(max(0, mode_index))
        self.mode_combo.blockSignals(False)
        self._current_language_provider = self.mode_combo.currentData()
        self._load_language_options(self._current_language_provider)
        strategy_index = self.strategy_combo.findData(config.SCREENSHOT_STRATEGY)
        self.strategy_combo.setCurrentIndex(strategy_index if strategy_index >= 0 else 0)

    def fetch_models(self, target_combo, target_btn, base_url_edit, api_key_edit):
        """
        根据对应的 Base URL 和 API Key 获取模型列表
        """
        base_url = base_url_edit.text().strip()
        api_key = api_key_edit.text().strip()
        
        if not base_url:
            QMessageBox.warning(self, "错误", "请先填写 Base URL")
            return

        if "chat/completions" in base_url:
            models_url = base_url.replace("chat/completions", "models")
        elif base_url.endswith("/v1") or base_url.endswith("/v1/"):
            models_url = base_url.rstrip("/") + "/models"
        else:
            models_url = base_url if base_url.endswith("/models") else base_url.rstrip("/") + "/models"

        target_btn.setEnabled(False)
        target_btn.setText("获取中...")
        
        try:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(models_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            models = []
            if isinstance(data, dict) and "data" in data:
                for item in data["data"]:
                    if isinstance(item, dict) and "id" in item: models.append(item["id"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, str): models.append(item)
                    elif isinstance(item, dict) and "id" in item: models.append(item["id"])
            
            if models:
                current = target_combo.currentText()
                target_combo.clear()
                target_combo.addItems(sorted(models))
                if current in models: target_combo.setCurrentText(current)
                QMessageBox.information(self, "成功", f"获取到 {len(models)} 个模型")
            else:
                QMessageBox.warning(self, "提示", "未获取到模型列表")
                
        except Exception as e:
            QMessageBox.critical(self, "获取失败", f"请求模型列表失败:\n{str(e)}")
        finally:
            target_btn.setEnabled(True)
            target_btn.setText("刷新列表")

    def save_config(self):
        try:
            screenshot_hotkey, text_hotkey = validate_hotkeys(
                self.screenshot_hotkey_edit.keySequence().toString(QKeySequence.PortableText),
                self.text_hotkey_edit.keySequence().toString(QKeySequence.PortableText),
            )
        except ValueError as error:
            QMessageBox.warning(self, "快捷键设置无效", str(error))
            return
        # 记录自启动变化
        old_autostart = getattr(config, "AUTO_START", False)
        new_autostart = self.autostart_check.isChecked()
        
        # 更新配置文件 (使用新引入的 update_config)
        try:
            self._store_current_language_selection()
            selected_provider = self.mode_combo.currentData()
            selected_source, selected_target = self.language_preferences[selected_provider]

            updates = [
                ('Translation', 'MODE', selected_provider),
                ('Translation', 'STRATEGY', self.strategy_combo.currentData()),
                ('Translation', 'TARGET_LANGUAGE', selected_target),
            ]
            for provider, languages in self.language_preferences.items():
                updates.extend([
                    (
                        'LanguagePreferences',
                        f'{provider}_SOURCE',
                        languages[0],
                    ),
                    (
                        'LanguagePreferences',
                        f'{provider}_TARGET',
                        languages[1],
                    ),
                ])

            updates.extend([
                ('API', 'API_KEY', self.api_key_edit.text()),
                ('API', 'BASE_URL', self.base_url_edit.text()),
                ('API', 'OCR_API_KEY', self.ocr_api_key_edit.text()),
                ('API', 'OCR_BASE_URL', self.ocr_base_url_edit.text()),
                ('API', 'CHAT_MODEL', self.chat_model_combo.currentText()),
                ('API', 'OCR_MODEL', self.ocr_model_combo.currentText()),
                ('DeepL', 'DEEPL_API_KEY', self.deepl_key_edit.text()),
                ('DeepL', 'API_URL', self.deepl_url_edit.text()),
                ('Baidu', 'APP_ID', self.baidu_app_id_edit.text()),
                ('Baidu', 'SECRET_KEY', self.baidu_secret_edit.text()),
                ('Baidu', 'API_URL', self.baidu_url_edit.text()),
                ('Youdao', 'APP_KEY', self.youdao_app_key_edit.text()),
                ('Youdao', 'APP_SECRET', self.youdao_secret_edit.text()),
                ('Youdao', 'API_URL', self.youdao_url_edit.text()),
                ('System', 'AUTO_START', new_autostart),
                ('System', 'SCREENSHOT_HOTKEY', screenshot_hotkey),
                ('System', 'TEXT_HOTKEY', text_hotkey),
                (
                    'System',
                    'AUTO_SELECTION_ENABLED',
                    self.auto_selection_check.isChecked(),
                ),
                (
                    'UI',
                    'BUBBLE_MENU_ENABLED',
                    self.bubble_menu_check.isChecked(),
                ),
                ('UI', 'BUBBLE_OPACITY', self.opacity_slider.value() / 100.0),
                ('UI', 'BUBBLE_BORDER_COLOR', self.current_border_color),
                ('UI', 'BUBBLE_SOURCE_FONT_SIZE', self.source_font_size_spin.value()),
                ('UI', 'BUBBLE_FONT_SIZE', self.translation_font_size_spin.value()),
                ('UI', 'BUBBLE_WIDTH_PERCENT', self.width_slider.value()),
                ('UI', 'BUBBLE_DEFAULT_POSITION', self.bubble_position_combo.currentData()),
            ])
            config.update_configs(updates)

            # 处理自启动逻辑
            if old_autostart != new_autostart:
                set_autostart(new_autostart)

            self.settings_saved.emit(
                selected_provider,
                selected_source,
                selected_target,
            )
            QMessageBox.information(self, "成功", "配置已保存！部分设置可能需要重启程序生效。")
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
