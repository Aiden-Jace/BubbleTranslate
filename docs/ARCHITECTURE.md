# 架构说明

## 模块边界

- `src/main.py`：应用控制器，负责托盘、快捷键、截图流程和 UI 生命周期。
- `src/config.py`：配置加载、内存同步和批量持久化。
- `src/resources.py`：开发环境与 PyInstaller 环境的统一资源寻址。
- `src/core/openai_client.py`：OpenAI 兼容接口、普通响应和 SSE 流式解析。
- `src/core/llm_engine.py`：后台工作线程及文本、OCR、VLM 流程编排。
- `src/core/translation_services.py`：DeepL、百度、有道和 Google 翻译适配。
- `src/core/listener.py`：Windows/macOS 全局快捷键监听。
- `src/core/selection_capture.py`：异步选中文本读取与剪贴板恢复。
- `src/ui/bubble.py`：翻译气泡及语言、编辑和内容展示状态。
- `src/ui/config_gui.py`：设置、气泡、模型和 API 配置页面。
- `src/ui/overlay.py`：截图选区遮罩。
- `src/ui/selection_tip.py`：选区旁的轻量翻译按钮。

## 翻译流程

### 文本翻译

1. 全局鼠标监听器检测拖选完成，或由 `Ctrl + Q` 主动触发。
2. 异步剪贴板读取器模拟复制并完整恢复原剪贴板。
3. 自动划词模式在选区附近显示轻量翻译按钮，点击后才调用接口。
4. 根据当前翻译引擎调用大模型或外部翻译服务。
5. 工作线程通过 Qt 信号发送原文、进度、流式译文和最终结果。

### 截图翻译

1. 截取选区并编码为 PNG。
2. `OCR_LLM` 使用独立 OCR API 识别；`VLM` 使用翻译模型 API 识别。
3. 识别出的原文交给当前翻译引擎。
4. 气泡展示译文，编辑模式可查看和修改原文。

## 配置原则

- OCR API 与翻译模型 API 完全独立。
- 每种翻译引擎单独保存原文语言和目标语言。
- 设置窗口使用批量更新，一次保存仅写入配置文件一次。
- 源码默认配置不包含真实密钥；密钥只保存在本地 `config.ini`。

## 测试

`tests/` 使用标准库 `unittest`，覆盖：

- OpenAI 普通与流式响应解析。
- OCR API 和翻译 API 路由。
- 图片编码不修改输入对象。
- 百度签名和 Google 响应解析。
- 按引擎独立语言列表。
- 设置窗口批量保存。
