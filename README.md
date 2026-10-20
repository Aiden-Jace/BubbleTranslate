<div align="center">

<img src="assets/logo.png" alt="Bubble Translate Logo" width="112">

# 气泡翻译

### Bubble Translate

截图、划词、手动输入，让译文出现在你正在阅读的位置<br>
A lightweight and configurable desktop translator for screenshots and selected text

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)
![Platforms](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-5B6573)
[![License: MIT](https://img.shields.io/badge/License-MIT-2E8B57)](LICENSE)

[快速开始](#快速开始) · [配置](#配置) · [常见问题](#常见问题) · [English](#english) · [架构文档](docs/ARCHITECTURE.md) · [反馈问题](https://github.com/Aiden-Jace/BubbleTranslate/issues)

</div>

---

## 中文说明

气泡翻译是一款常驻系统托盘的桌面翻译工具。它可以快速截取屏幕区域、翻译选中的文字，也可以作为一个随时可用的手动翻译输入框。

项目支持本地或远程 OpenAI 兼容模型，并内置 DeepL、百度翻译、有道翻译和 Google 免费翻译适配。OCR 模型和翻译模型可以使用完全独立的服务地址与密钥。

可以用 **本地 CPU OCR + Google 翻译** 开始体验，无需显卡或 API Key；也可以接入自己的本地模型，让识别与翻译在本机完成。本地 OCR 首次使用需下载模型，Google 翻译仍需联网。

### 功能亮点

| 功能 | 说明 |
| --- | --- |
| 截图翻译 | 使用 `F1` 框选屏幕区域并翻译 |
| 自动划词提示 | 拖选文本后在选区旁显示翻译按钮 |
| 划词翻译 | 使用 `F2` 翻译当前选中的文本 |
| 手动翻译 | 未检测到选中文本时自动打开编辑气泡 |
| 本地 CPU OCR | 使用 RapidOCR + PP-OCRv6 small 提取截图文字，无需显卡、大模型或 OCR API |
| 双阶段识别 | 支持专用 OCR 识别后翻译 |
| VLM 识别 | 支持视觉语言模型识别截图后翻译 |
| 多翻译引擎 | LLM、DeepL、百度、有道、Google 免费翻译 |
| 独立 API | OCR 与翻译模型可配置不同地址、密钥和模型 |
| 自定义提示词 | 在配置文件中调整翻译、VLM 和 OCR 提示词，适配不同模型 |
| 智能气泡 | 自适应高度、原文编辑、复制；左键选择语言，右键交换语言并将当前译文作为原文重新翻译（需选定具体原文语言） |
| 精简模式 | 可隐藏顶部气泡菜单，只显示译文 |
| 气泡默认位置 | 右上角、左上角、顶部居中可选，默认顶部居中 |
| 气泡字体 | 原文与译文字体大小分别设置，原文编辑框同步使用原文字号 |
| 独立语言偏好 | 每种翻译引擎分别保存原文和目标语言 |

### 工作方式

#### 截图翻译

```text
F1
   ↓
框选屏幕区域
   ↓
本地 CPU OCR / OCR API / VLM 识别原文
   ↓
当前翻译引擎生成译文
   ↓
气泡展示结果
```

#### 划词翻译

```text
选中文字
   ↓
选区旁显示翻译按钮，点击按钮
或直接按 F2
   ↓
读取剪贴板并立即恢复原内容
   ↓
翻译并显示气泡
```

### 支持的翻译服务

| 引擎 | 凭据 | 说明 |
| --- | --- | --- |
| OpenAI 兼容 LLM | API URL、API Key | 支持本地或远程 Chat/VLM 服务 |
| DeepL | API Key、API URL | 支持自定义 Free/Pro 接口地址 |
| 百度翻译 | App ID、密钥 | 使用官方通用翻译 API |
| 有道翻译 | 应用 ID、应用密钥 | 使用官方文本翻译 API |
| Google 免费翻译 | 无 | 使用 `client=gtx` 免密端点，不是 Google Cloud Translation API；可能受网络、限流或上游变更影响 |

### 快速开始

#### 环境要求

- Python 3.10 或更高版本
- Windows 10/11 或 macOS

依赖版本范围见 [requirements.txt](requirements.txt)，可安装版本取决于 Python、操作系统及处理器架构。项目包含 Windows 和 macOS 的平台适配与打包脚本；Linux 暂不作为支持平台。

#### 安装

Windows（PowerShell）：

```powershell
git clone https://github.com/Aiden-Jace/BubbleTranslate.git
cd BubbleTranslate
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m src.main
```

macOS（终端）：

```bash
git clone https://github.com/Aiden-Jace/BubbleTranslate.git
cd BubbleTranslate
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python -m src.main
```

命令直接使用虚拟环境中的 Python，无需先激活虚拟环境。程序启动后常驻系统托盘；右键单击托盘图标打开设置。

#### 首次使用

1. 打开 **设置 → 设置**，将翻译主引擎改为 **Google 免费翻译**，截图策略选择 **本地 CPU OCR**，选择目标语言并保存。新配置的默认翻译引擎是 DeepL，需要密钥；首次体验时请手动切换。
2. 按 `F1` 框选屏幕文字。首次识别会下载 OCR 模型，请保持联网并等待准备完成。
3. 选中文字后按 `F2` 翻译；未读取到选中文本时，会打开手动输入框。也可拖选文字，点击选区旁的翻译按钮。
4. 通过托盘菜单退出程序；双击右键可关闭气泡或退出截图模式，截图模式也支持 `Esc`。

macOS 源码运行时，需要为实际启动程序的终端或 Python 授予屏幕录制及辅助功能权限；全局监听也可能需要输入监控权限。可在系统设置的隐私与安全性中检查，授权后重新启动程序。

#### 使用自己的模型或翻译服务

| 使用方式 | 需要配置 |
| --- | --- |
| 本地 OCR + 外部翻译 | 保持本地 CPU OCR，填写 DeepL、百度或有道凭据；Google 模式不需要密钥 |
| 本地 OCR + LLM 翻译 | 主引擎选择大模型翻译，在 API 页填写翻译接口，在模型页填写 Chat 模型名 |
| OCR API + 任意翻译引擎 | 策略选择 OCR API，单独填写 OCR 地址、密钥和模型，再配置所选翻译引擎 |
| VLM + 任意翻译引擎 | 策略选择 VLM，翻译模型 API 必须支持图片输入；识别原文后再交给所选翻译引擎 |

界面中的 **Base URL 必须填写完整 Chat Completions 地址**，例如 `http://127.0.0.1:8000/v1/chat/completions`，程序会直接向此地址发送请求。仅填写 `/v1` 不够；模型名称须与服务端提供的名称一致。无需鉴权的本地服务可以留空 API Key。

### 快捷键

可在 **设置 → 快捷键** 中自定义截屏翻译和划词翻译按键，支持单键及组合键。点击输入框录入，保存后立即生效，也可恢复默认 F1 / F2。打开设置时暂停翻译快捷键，关闭设置后恢复。

| 操作 | Windows | macOS |
| --- | --- | --- |
| 截图翻译 | `F1` | `F1` |
| 划词/手动翻译 | `F2` | `F2` |
| 退出截图模式 | 双击右键或 `Esc` | 双击右键或 `Esc` |

### 配置

设置窗口包含以下页面：

- **设置**：翻译引擎、截图策略、语言、自动划词提示、开机启动。
- **快捷键**：截屏翻译和划词翻译快捷键。
- **气泡**：顶部菜单、透明度、边框颜色、字体大小、气泡宽度。
- **模型**：翻译模型与 OCR 模型。
- **API**：LLM、OCR、DeepL、百度和有道服务配置。

开发环境配置保存在项目根目录的 `config.ini`。打包版本配置保存在：

- Windows：`%APPDATA%\BubbleTranslate\config.ini`（未设置 `APPDATA` 时回退到用户主目录下的 `BubbleTranslate`）。
- macOS：通常为 `~/BubbleTranslate/config.ini`。当前实现优先使用 `APPDATA`，不存在时回退到用户主目录，并非 `~/Library/Application Support`。

API Key 保存在本地 `config.ini` 中，未加密。该文件已加入 `.gitignore`；分享配置或反馈问题前请移除密钥。

#### 自定义模型提示词

关闭程序后编辑 `config.ini` 的 `[Prompts]` 段，保存并重新启动即可生效。首次运行会生成默认提示词；升级后启动时会为旧配置补齐缺失项，保留已有自定义内容。

| 配置项 | 用途 |
| --- | --- |
| `TRANSLATION_SYSTEM` | LLM 翻译的系统提示词，划词、手动输入和截图识别后的翻译共用 |
| `OCR_CONTEXT` | 截图翻译时插入 `{ocr_context}` 的补充说明，可留空 |
| `VLM_SYSTEM` | VLM 截图文字识别的系统提示词 |
| `VLM_USER` | VLM 识别请求中与截图一起发送的文字提示词 |
| `OCR_USER` | 专用 OCR 模型的文字提示词，默认 `OCR:`，可按模型要求修改 |

语言占位符 `{source_language}` 和 `{target_language}` 会替换为当前选择的语言；`{ocr_context}` 仅用于 `TRANSLATION_SYSTEM`，非截图翻译时为空。百分号、JSON 花括号和未知占位符保留原文。除 `OCR_CONTEXT` 外，空白配置项回退到默认提示词。

例如，偏好英文指令的模型可以使用：

```ini
[Prompts]
TRANSLATION_SYSTEM = You are a professional translator. {ocr_context}
    Translate from {source_language} to {target_language}.
    Preserve paragraphs and lists. Output only the translation.
OCR_CONTEXT = The input text was extracted from a screenshot using OCR.
VLM_SYSTEM = Transcribe only the visible text in the image. Do not translate or explain.
VLM_USER = Read the text in {source_language}. Detect the language if set to auto-detect.
OCR_USER = OCR:
```

多行提示词的后续行必须缩进。提示词配置用于 LLM、VLM 和 OCR API，不改变 DeepL、百度、有道、Google 或本地 CPU OCR 的调用方式。

#### 本地 CPU OCR

1. 安装 `requirements.txt` 中的依赖。
2. 在 **设置 → 截图翻译策略** 中选择 **本地 CPU OCR（无需显卡或 OCR API）**。
3. 将翻译主引擎选为 **Google 免费翻译**，即可无需配置 OCR 或大模型 API 使用截图翻译。

本地识别采用 RapidOCR + PP-OCRv6 small 检测与识别模型，通过 ONNX Runtime 在 CPU 上推理。可识别语言和效果取决于所用模型及截图质量。首次识别会联网下载模型，气泡会显示准备提示；成功缓存后，后续 OCR 可以离线运行。Google 翻译仍需联网。新配置默认采用本地 CPU OCR，已有配置保留原来的截图策略。

模型缓存位于配置目录下的 `models/cpu_ocr/`：源码运行时为项目目录，打包版本为用户配置目录。模型文件不进入 Git。首次准备会较慢，模型在当前进程内复用；若下载失败，检查网络后可重试。此模式无需填写 OCR API 地址、密钥或模型名。

### 常见问题

| 问题 | 排查方式 |
| --- | --- |
| 启动后没有主窗口 | 程序常驻系统托盘，检查通知区域中的隐藏图标，右键打开设置 |
| 首次翻译提示凭据错误 | 新配置默认使用 DeepL；填写密钥，或切换到 Google / 已配置好的 LLM |
| 本地 OCR 首次使用很慢或下载失败 | 首次需要下载模型；检查网络与配置目录写入权限，成功缓存后会复用 |
| macOS 截图全黑、快捷键或划词无响应 | 检查屏幕录制、辅助功能和输入监控权限，授权后重新启动实际运行的终端 / Python / 应用 |
| `F1` / `F2` 被其他软件占用 | 在设置的快捷键页改为组合键；部分键盘需同时按 `Fn` |
| 划词没有读取到文字 | 目标应用必须支持复制所选文本；可改用截图或手动输入。打开设置期间翻译快捷键会暂停 |
| 接口返回 404 / 401 | 核对完整 `/v1/chat/completions` 地址、对应接口的密钥及模型名称 |
| Google 翻译不可用 | 检查网络，或切换到配置好的翻译服务 / 本地 LLM |
| 修改提示词后没有变化 | 关闭程序后修改配置并重启；提示词只作用于对应的模型请求 |

### 测试

在安装好依赖并激活虚拟环境后，从项目根目录运行：

```bash
python -m unittest discover -s tests -v
```

测试覆盖普通及流式响应、OCR 路由、提示词配置迁移与渲染、服务签名、截图线程、设置保存、气泡交互及退出清理。接口请求和 OCR 推理在相关单元测试中使用模拟对象，不代表真实服务或所有平台的端到端验证。

### 打包

在目标操作系统上构建。PyInstaller 是额外的构建依赖，不在运行依赖列表中：

```bash
python -m pip install pyinstaller
```

Windows:

```bash
pyinstaller BubbleTranslate.spec
```

输出目录为 `dist/BubbleTranslate/`。需要 Windows 安装程序时，安装 Inno Setup 后编译：

```text
installer.iss
```

macOS:

```bash
pyinstaller MacBubbleTranslate.spec
```

macOS 脚本生成 `.app`，当前未配置签名或公证。构建脚本不等同于已经验证或发布的安装包。分发时应同时携带项目许可和实际包含的第三方许可与声明，尤其是 Qt / PySide6 及随包模型；本仓库的 MIT 许可证不替代这些要求。详见 [Qt 的 LGPL 说明](https://www.qt.io/development/open-source-lgpl-obligations)和 [RapidOCR 模型许可说明](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/)。

### 项目结构

```text
BubbleTranslate/
├── assets/icons/              # 气泡界面图标
├── docs/ARCHITECTURE.md       # 架构说明
├── scripts/                   # 开发调试工具
├── src/
│   ├── core/
│   │   ├── llm_engine.py      # 后台翻译任务与流程编排
│   │   ├── local_ocr.py       # 本地 CPU OCR
│   │   ├── openai_client.py   # OpenAI 兼容客户端
│   │   └── translation_services.py
│   ├── ui/
│   │   ├── bubble.py          # 翻译气泡
│   │   ├── config_gui.py      # 托盘设置窗口
│   │   └── overlay.py         # 截图选区
│   ├── config.py              # 配置读写
│   ├── main.py                # 应用入口
│   └── resources.py           # 资源路径
├── tests/                     # 自动化回归测试
├── LICENSE                    # MIT 许可证
├── BubbleTranslate.spec       # Windows 打包配置
├── MacBubbleTranslate.spec    # macOS 打包配置
└── installer.iss              # Windows 安装器
```

### 隐私与安全

- **本地 CPU OCR**：在本机识别框选图像；首次下载模型需要联网。
- **OCR API / VLM**：将框选图像发送到所配置的识别服务；识别出的原文继续发送给所选翻译引擎。
- **文本翻译**：将选中或输入的文字发送到所选翻译服务。只有识别和翻译均使用本地服务、模型也已缓存时，整个翻译流程才可离线运行。
- **屏幕与剪贴板**：截屏时先抓取整个桌面供框选使用，再裁剪选区用于识别；划词通过模拟复制读取文本，并尝试恢复原剪贴板内容。
- **配置与日志**：密钥以明文存储在本地配置中；源码运行时控制台可能输出原文、译文和识别结果，分享日志前请脱敏。

### 贡献

欢迎提交 [Issue](https://github.com/Aiden-Jace/BubbleTranslate/issues) 和 [Pull Request](https://github.com/Aiden-Jace/BubbleTranslate/pulls)。

反馈问题时请提供操作系统、Python 版本、翻译引擎、截图策略、复现步骤及脱敏后的错误信息。不要在公开 Issue 中附带 API Key、个人截图或完整配置文件。

修改代码时建议每个 PR 聚焦一个主题，为新增行为补充必要的回归测试；界面变更请附截图，平台相关变更请说明验证平台。提交前请运行：

```bash
python -m unittest discover -s tests -v
```

项目默认配置见 [src/config.py](src/config.py)，模块边界和翻译流程见 [架构文档](docs/ARCHITECTURE.md)。

### 开源许可证

项目原创代码采用 [MIT License](LICENSE)，允许商用、修改及再分发，也允许用于闭源项目，需保留版权和许可声明；软件按现状提供。

第三方依赖、模型及图标仍遵循各自许可证，不因本项目采用 MIT 而改变。

### 致谢

- [Qt for Python / PySide6](https://doc.qt.io/qtforpython-6/)：桌面界面，许可选项及第三方声明见 [Qt 文档](https://doc.qt.io/qtforpython-6/licenses.html)。
- [RapidOCR](https://github.com/RapidAI/RapidOCR)、[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 与 [ONNX Runtime](https://github.com/microsoft/onnxruntime)：本地识别与推理；模型来源及许可见 [RapidOCR 说明](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/)。
- [Lucide](https://lucide.dev/)：`assets/icons/` 中的界面图标，遵循 ISC / Feather 衍生图标 MIT 许可，完整文本保留在 [assets/icons/LICENSE](assets/icons/LICENSE)，上游声明见 [Lucide 许可](https://github.com/lucide-icons/lucide/blob/main/LICENSE)。
- [MSS](https://github.com/BoboTiG/python-mss)、[Pillow](https://github.com/python-pillow/Pillow)、[pynput](https://github.com/moses-palmer/pynput) 与 [Requests](https://github.com/psf/requests)：屏幕捕获、图像处理、输入监听与网络请求。

---

## English

Bubble Translate is a system-tray desktop translator for screenshots, selected text, and manual input.

It supports local or remote OpenAI-compatible models as well as DeepL, Baidu Translate, Youdao Translate, and a built-in keyless Google Translate endpoint. OCR and translation models can use separate API endpoints, credentials, and model names.

### Highlights

| Feature | Description |
| --- | --- |
| Screenshot translation | Press `F1` and select any screen region |
| Automatic selection tip | Shows a translate button next to dragged text |
| Selected-text translation | Press `F2` to translate selected text |
| Local CPU OCR | Extract screenshot text using RapidOCR and PP-OCRv6 small without a GPU, large language model, or OCR API |
| Manual input | Opens the editor when no selected text is detected |
| OCR pipeline | Recognize text with a dedicated OCR model before translation |
| VLM pipeline | Recognize screenshots with a vision-language model |
| Multiple providers | LLM, DeepL, Baidu, Youdao, and Google |
| Separate APIs | Independent OCR and translation endpoints and credentials |
| Custom prompts | Edit translation, VLM, and OCR instructions in the configuration file |
| Smart bubble | Adaptive height, editable source, copy; left-click to select languages, right-click to swap them and translate the current result back (requires a specific source language) |
| Minimal mode | Hide the toolbar and display translation only |
| Provider preferences | Independent source and target languages per provider |
| Default bubble position | Choose top right, top left, or top center; defaults to top center |
| Bubble fonts | Set source and translation font sizes independently; the source editor uses the source font size |

### Translation Providers

| Provider | Credentials | Notes |
| --- | --- | --- |
| OpenAI-compatible LLM | API URL and API key | Local or remote Chat/VLM services |
| DeepL | API key and API URL | Custom Free or Pro endpoint |
| Baidu Translate | App ID and secret | Official general translation API |
| Youdao Translate | App ID and app secret | Official text translation API |
| Google Translate | None | Keyless `client=gtx` endpoint, separate from Google Cloud Translation API; subject to network access, rate limits, and upstream changes |

### Quick Start

Requirements:

- Python 3.10+
- Windows 10/11 or macOS

The repository includes Windows and macOS platform adapters and build scripts. Linux is not currently a supported target. Dependency availability depends on your Python version, OS, and architecture.

Windows (PowerShell):

```powershell
git clone https://github.com/Aiden-Jace/BubbleTranslate.git
cd BubbleTranslate
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m src.main
```

macOS:

```bash
git clone https://github.com/Aiden-Jace/BubbleTranslate.git
cd BubbleTranslate
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
./venv/bin/python -m src.main
```

These commands use the virtual environment directly. The app runs in the system tray; right-click its icon to open settings.

On first launch, choose **Google Translate** and **Local CPU OCR**, select a target language, and save. New configurations default to DeepL, which needs an API key. Press `F1` to select a screenshot region, or `F2` to translate selected text. If no text is captured, the manual editor opens. Local OCR downloads its models on first use; Google translation still requires a network connection.

On macOS, grant Screen Recording and Accessibility permissions to the terminal / Python / app that runs the program. Global input monitoring may also need Input Monitoring permission. Restart after granting permissions.

### Keyboard Shortcuts

Customize screenshot and selected-text shortcuts in **Settings → Shortcuts**. Click an input and press a key or key combination; save to apply immediately, or restore F1 / F2. Translation shortcuts pause while settings are open and resume when settings close.

| Action | Windows | macOS |
| --- | --- | --- |
| Screenshot translation | `F1` | `F1` |
| Selected text / manual input | `F2` | `F2` |
| Exit capture mode | Double right-click or `Esc` | Double right-click or `Esc` |

### Configuration

Right-click the tray icon to open the settings window:

- **Settings**: provider, screenshot strategy, languages, automatic selection tip, and auto-start.
- **Shortcuts**: screenshot and selected-text key bindings.
- **Bubble**: toolbar visibility, opacity, border, font size, and width.
- **Models**: translation and OCR model names.
- **API**: LLM, OCR, DeepL, Baidu, and Youdao credentials.

Use a complete Chat Completions endpoint for the LLM and OCR **Base URL**, such as `http://127.0.0.1:8000/v1/chat/completions`. The app sends requests directly to this URL; `/v1` alone is insufficient. Set a model name supported by your service. Local services without authentication may leave the API key empty. The VLM screenshot strategy requires an image-capable Chat model; dedicated OCR uses its own URL, key, and model.

Development settings are stored in the project root's `config.ini`. Packaged builds use `%APPDATA%\BubbleTranslate\config.ini` on Windows and usually `~/BubbleTranslate/config.ini` on macOS: the implementation uses `APPDATA` when present and otherwise falls back to the home directory. Model cache files live in `models/cpu_ocr/` under the same configuration directory. API keys are stored as plain text; configuration and model caches are ignored by Git.

Customize model instructions in the `[Prompts]` section of `config.ini`, then restart the app. Available keys are `TRANSLATION_SYSTEM`, `OCR_CONTEXT`, `VLM_SYSTEM`, `VLM_USER`, and `OCR_USER`. Language placeholders `{source_language}` and `{target_language}` use the selected languages; `{ocr_context}` inserts screenshot-specific context into the translation prompt and is empty for text translation. Indent continuation lines for multiline prompts. Missing keys are added automatically without replacing custom values. Blank prompts use defaults, except `OCR_CONTEXT`, which may be empty. These settings do not affect external translation providers or local CPU OCR.

### Tests

With dependencies installed and your virtual environment activated, run from the project root:

```bash
python -m unittest discover -s tests -v
```

Relevant tests mock model inference and network requests; passing tests do not certify live services or end-to-end behavior on every OS.

### Packaging

Build on the target operating system. Install PyInstaller separately inside the virtual environment:

```bash
python -m pip install pyinstaller
```

Windows:

```bash
pyinstaller BubbleTranslate.spec
```

macOS:

```bash
pyinstaller MacBubbleTranslate.spec
```

Windows output is in `dist/BubbleTranslate/`. Build the installer using Inno Setup and `installer.iss`. The macOS spec creates an `.app` without configured signing or notarization. Build scripts are not a guarantee of published or verified binaries. Distributions must include the project's license and the licenses and notices of bundled dependencies and models; see [Qt's LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations) and [RapidOCR's model license notice](https://rapidai.github.io/RapidOCRDocs/main/en/model_licenses/).

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| No main window | Look for the app in the system tray and right-click to open settings |
| Credentials error on first use | Configure DeepL credentials or switch to Google / a configured LLM |
| Slow first OCR or download failure | Check network access and write permissions for the model cache |
| Black screenshots or missing input on macOS | Check Screen Recording, Accessibility, and Input Monitoring permissions, then restart |
| Shortcut conflict | Change the key binding in Settings; some keyboards require `Fn` |
| Selected text is not captured | The target app must support copying; use screenshots or manual input instead |
| 404 / 401 from a model | Check the complete endpoint, API key, and model name |
| Google translation fails | Check connectivity or switch to another configured provider |


### Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for module boundaries and translation workflows.

### Privacy

- Local CPU OCR processes the selected region on your device. Its first model download needs a connection.
- Remote OCR / VLM receives the selected image; the chosen translation provider receives the recognized or entered text. Fully offline translation requires cached OCR models and a local translation service.
- Capture first grabs the desktop for region selection, then crops the region for recognition. Selected-text capture simulates copying and attempts to restore the clipboard.
- Keys are stored as plain text in the local configuration. Console output can contain source text, translations, and OCR results; redact logs before sharing.

### Contributing

[Issues](https://github.com/Aiden-Jace/BubbleTranslate/issues) and [pull requests](https://github.com/Aiden-Jace/BubbleTranslate/pulls) are welcome. Include your OS, Python version, provider, screenshot strategy, reproduction steps, and redacted errors. Keep API keys and private screenshots out of public reports. Keep PRs focused, run the test suite, add relevant regression coverage, and describe which platforms you verified. Include screenshots for UI changes.

### License

Original project code is available under the [MIT License](LICENSE). Third-party libraries, models, and icons retain their own licenses. See [Acknowledgements](#致谢) for upstream projects and license references.
