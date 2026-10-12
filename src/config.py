import os
import sys
import configparser
import shutil

# 自动定位配置文件路径
# 如果是打包环境，保存在用户目录下，防止 C:\Program Files 无权限写入
if hasattr(sys, '_MEIPASS'):
    # 打包环境：保存在 %APPDATA%\BubbleTranslate\config.ini
    app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
    CONFIG_DIR = os.path.join(app_data, 'BubbleTranslate')
    legacy_dir_name = "js" + "fy"
    legacy_config_file = os.path.join(app_data, legacy_dir_name, 'config.ini')
else:
    # 开发环境：保存在项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_DIR = project_root

if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.ini')
if (
    hasattr(sys, '_MEIPASS')
    and not os.path.exists(CONFIG_FILE)
    and os.path.exists(legacy_config_file)
):
    shutil.copy2(legacy_config_file, CONFIG_FILE)

# 默认配置
defaults = {
    'API': {
        'BASE_URL': "http://127.0.0.1:8000/v1/chat/completions",
        'API_KEY': "",
        'OCR_BASE_URL': "http://127.0.0.1:8000/v1/chat/completions",
        'OCR_API_KEY': "",
        'CHAT_MODEL': "",
        'OCR_MODEL': "",
        'TIMEOUT': "60",
        'CHAT_TEMPERATURE': "0.3",
        'OCR_TEMPERATURE': "0.01",
        'MAX_IMAGE_SIZE': "1536"
    },
    'Translation': {
        'MODE': "DEEPL",
        'STRATEGY': "LOCAL_CPU",
        'TARGET_LANGUAGE': "中文"
    },
    'LanguagePreferences': {
        'LLM_SOURCE': "自动检测",
        'LLM_TARGET': "中文",
        'DEEPL_SOURCE': "自动检测",
        'DEEPL_TARGET': "中文",
        'BAIDU_SOURCE': "自动检测",
        'BAIDU_TARGET': "中文",
        'YOUDAO_SOURCE': "自动检测",
        'YOUDAO_TARGET': "中文",
        'GOOGLE_SOURCE': "自动检测",
        'GOOGLE_TARGET': "中文"
    },
    'DeepL': {
        'DEEPL_API_KEY': "",
        'API_URL': "https://api-free.deepl.com/v2/translate"
    },
    'Baidu': {
        'APP_ID': "",
        'SECRET_KEY': "",
        'API_URL': "https://fanyi-api.baidu.com/api/trans/vip/translate"
    },
    'Youdao': {
        'APP_KEY': "",
        'APP_SECRET': "",
        'API_URL': "https://openapi.youdao.com/api"
    },
    'UI': {
        'BUBBLE_MENU_ENABLED': "True",
        'BUBBLE_DEFAULT_POSITION': "top_center",
        'BUBBLE_OPACITY': "0.9",
        'BUBBLE_BORDER_COLOR': "#ffffff",
        'BUBBLE_FONT_SIZE': "10",
        'BUBBLE_SOURCE_FONT_SIZE': "10",
        'BUBBLE_WIDTH_PERCENT': "40",
        'STREAM_OUTPUT': "True"
    },
    'System': {
        'AUTO_START': "False",
        'AUTO_SELECTION_ENABLED': "True",
        'SCREENSHOT_HOTKEY': "F1",
        'TEXT_HOTKEY': "F2",
    }
}

_parser = configparser.ConfigParser()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        # 创建默认配置
        for section, content in defaults.items():
            _parser[section] = content
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            _parser.write(f)
        print(f"[Config] 首次运行，已生成配置文件: {CONFIG_FILE}")
    else:
        _parser.read(CONFIG_FILE, encoding='utf-8')

def save_config_to_file():
    temporary_file = f"{CONFIG_FILE}.tmp"
    with open(temporary_file, 'w', encoding='utf-8') as file:
        _parser.write(file)
    os.replace(temporary_file, CONFIG_FILE)

# 执行加载
load_config()

# 导出动态变量供全局使用
BASE_URL = _parser.get('API', 'BASE_URL')
API_KEY = _parser.get('API', 'API_KEY')
OCR_BASE_URL = _parser.get('API', 'OCR_BASE_URL', fallback=BASE_URL)
OCR_API_KEY = _parser.get('API', 'OCR_API_KEY', fallback=API_KEY)
CHAT_MODEL = _parser.get('API', 'CHAT_MODEL')
OCR_MODEL = _parser.get('API', 'OCR_MODEL')
TIMEOUT = _parser.getint('API', 'TIMEOUT')
CHAT_TEMPERATURE = _parser.getfloat('API', 'CHAT_TEMPERATURE', fallback=0.3)
OCR_TEMPERATURE = _parser.getfloat('API', 'OCR_TEMPERATURE', fallback=0.01)
MAX_IMAGE_SIZE = _parser.getint('API', 'MAX_IMAGE_SIZE', fallback=1536)


TRANSLATION_MODE = _parser.get('Translation', 'MODE')
SCREENSHOT_STRATEGY = _parser.get('Translation', 'STRATEGY')
DEFAULT_TARGET_LANGUAGE = _parser.get('Translation', 'TARGET_LANGUAGE')

DEEPL_API_KEY = _parser.get('DeepL', 'DEEPL_API_KEY')
DEEPL_API_URL = _parser.get('DeepL', 'API_URL')

BAIDU_APP_ID = _parser.get('Baidu', 'APP_ID', fallback="")
BAIDU_SECRET_KEY = _parser.get('Baidu', 'SECRET_KEY', fallback="")
BAIDU_API_URL = _parser.get(
    'Baidu',
    'API_URL',
    fallback="https://fanyi-api.baidu.com/api/trans/vip/translate",
)

YOUDAO_APP_KEY = _parser.get('Youdao', 'APP_KEY', fallback="")
YOUDAO_APP_SECRET = _parser.get('Youdao', 'APP_SECRET', fallback="")
YOUDAO_API_URL = _parser.get(
    'Youdao',
    'API_URL',
    fallback="https://openapi.youdao.com/api",
)

BUBBLE_MENU_ENABLED = _parser.getboolean(
    'UI',
    'BUBBLE_MENU_ENABLED',
    fallback=True,
)
BUBBLE_OPACITY = _parser.getfloat('UI', 'BUBBLE_OPACITY')
BUBBLE_BORDER_COLOR = _parser.get('UI', 'BUBBLE_BORDER_COLOR')
BUBBLE_FONT_SIZE = _parser.getint('UI', 'BUBBLE_FONT_SIZE')
BUBBLE_SOURCE_FONT_SIZE = _parser.getint('UI', 'BUBBLE_SOURCE_FONT_SIZE', fallback=BUBBLE_FONT_SIZE)
BUBBLE_WIDTH_PERCENT = _parser.getint('UI', 'BUBBLE_WIDTH_PERCENT')
BUBBLE_DEFAULT_POSITION = _parser.get('UI', 'BUBBLE_DEFAULT_POSITION', fallback='top_center')
STREAM_OUTPUT = _parser.getboolean('UI', 'STREAM_OUTPUT')

AUTO_START = _parser.getboolean('System', 'AUTO_START')
SCREENSHOT_HOTKEY = _parser.get('System', 'SCREENSHOT_HOTKEY', fallback='F1')
TEXT_HOTKEY = _parser.get('System', 'TEXT_HOTKEY', fallback='F2')
AUTO_SELECTION_ENABLED = _parser.getboolean(
    'System',
    'AUTO_SELECTION_ENABLED',
    fallback=True,
)

def get_language_preference(provider):
    provider = provider.upper()
    source = _parser.get(
        'LanguagePreferences',
        f'{provider}_SOURCE',
        fallback='自动检测',
    )
    target = _parser.get(
        'LanguagePreferences',
        f'{provider}_TARGET',
        fallback=DEFAULT_TARGET_LANGUAGE,
    )
    return source, target

def update_active_language(provider, source_language, target_language):
    """同步当前引擎语言偏好和兼容目标语言字段。"""
    provider = provider.upper()
    update_configs([
        ('LanguagePreferences', f'{provider}_SOURCE', source_language),
        ('LanguagePreferences', f'{provider}_TARGET', target_language),
        ('Translation', 'TARGET_LANGUAGE', target_language),
    ])

def _sync_global_value(section, option, value):
    section_key = section.upper()
    option_key = option.upper()
    global_name = _section_option_to_global_map.get(
        (section_key, option_key),
        _ini_to_global_map.get(option_key),
    )
    if not global_name or global_name not in globals():
        return

    old_value = globals()[global_name]
    try:
        if isinstance(old_value, bool):
            new_value = str(value).lower() in ('true', '1', 'yes', 'on')
        elif isinstance(old_value, int):
            new_value = int(value)
        elif isinstance(old_value, float):
            new_value = float(value)
        else:
            new_value = str(value)

        globals()[global_name] = new_value
    except (TypeError, ValueError) as error:
        print(f"[Config] 更新变量 {global_name} 失败: {error}")

def update_configs(updates):
    """批量更新配置，并仅写入磁盘一次。"""
    for section, option, value in updates:
        if section not in _parser:
            _parser.add_section(section)
        _parser.set(section, option, str(value))
        _sync_global_value(section, option, value)
    save_config_to_file()

def update_config(section, option, value):
    """更新单个配置项。"""
    update_configs([(section, option, value)])

# 内部映射表：INI 选项名 (大写) -> 全局变量名
_ini_to_global_map = {
    'BASE_URL': 'BASE_URL',
    'API_KEY': 'API_KEY',
    'OCR_BASE_URL': 'OCR_BASE_URL',
    'OCR_API_KEY': 'OCR_API_KEY',
    'CHAT_MODEL': 'CHAT_MODEL',
    'OCR_MODEL': 'OCR_MODEL',
    'TIMEOUT': 'TIMEOUT',
    'CHAT_TEMPERATURE': 'CHAT_TEMPERATURE',
    'OCR_TEMPERATURE': 'OCR_TEMPERATURE',
    'MAX_IMAGE_SIZE': 'MAX_IMAGE_SIZE',
    'MODE': 'TRANSLATION_MODE',
    'STRATEGY': 'SCREENSHOT_STRATEGY',
    'TARGET_LANGUAGE': 'DEFAULT_TARGET_LANGUAGE',
    'DEEPL_API_KEY': 'DEEPL_API_KEY',
    'BUBBLE_MENU_ENABLED': 'BUBBLE_MENU_ENABLED',
    'BUBBLE_DEFAULT_POSITION': 'BUBBLE_DEFAULT_POSITION',
    'BUBBLE_OPACITY': 'BUBBLE_OPACITY',
    'BUBBLE_BORDER_COLOR': 'BUBBLE_BORDER_COLOR',
    'BUBBLE_FONT_SIZE': 'BUBBLE_FONT_SIZE',
    'BUBBLE_SOURCE_FONT_SIZE': 'BUBBLE_SOURCE_FONT_SIZE',
    'BUBBLE_WIDTH_PERCENT': 'BUBBLE_WIDTH_PERCENT',
    'STREAM_OUTPUT': 'STREAM_OUTPUT',
    'AUTO_START': 'AUTO_START',
    'SCREENSHOT_HOTKEY': 'SCREENSHOT_HOTKEY',
    'TEXT_HOTKEY': 'TEXT_HOTKEY',
    'AUTO_SELECTION_ENABLED': 'AUTO_SELECTION_ENABLED',
}

_section_option_to_global_map = {
    ('DEEPL', 'API_URL'): 'DEEPL_API_URL',
    ('BAIDU', 'APP_ID'): 'BAIDU_APP_ID',
    ('BAIDU', 'SECRET_KEY'): 'BAIDU_SECRET_KEY',
    ('BAIDU', 'API_URL'): 'BAIDU_API_URL',
    ('YOUDAO', 'APP_KEY'): 'YOUDAO_APP_KEY',
    ('YOUDAO', 'APP_SECRET'): 'YOUDAO_APP_SECRET',
    ('YOUDAO', 'API_URL'): 'YOUDAO_API_URL',
}
