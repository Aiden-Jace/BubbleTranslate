# 架构说明

## 模块边界

- `src/main.py`：应用控制器，负责托盘、快捷键、截图流程和 UI 生命周期。
- `src/config.py`：配置加载、内存同步和批量持久化。
- `src/resources.py`：开发环境与 PyInstaller 环境的统一资源寻址。
- `src/core/openai_client.py`：OpenAI 兼容接口、普通响应和 SSE 流式解析。
- `src/core/llm_engine.py`：后台工作线程及文本、OCR、VLM 流程编排。
- `src/core/local_ocr.py`：本地 CPU OCR，懒加载 RapidOCR + PP-OCRv6 small，串行复用 ONNX Runtime CPU 会话。
- `src/core/translation_services.py`：DeepL、百度、有道和 Google 翻译适配。
- `src/core/listener.py`：Windows/macOS 全局快捷键监听。
- `src/core/screenshot.py`：后台截屏线程、MSS 资源预热与复用、屏幕布局变更后的重新初始化。
- `src/core/selection_capture.py`：异步选中文本读取与剪贴板恢复。
- `src/ui/bubble.py`：翻译气泡及语言、编辑和内容展示状态。
- `src/ui/config_gui.py`：设置、气泡、模型和 API 配置页面。
- `src/ui/overlay.py`：截图选区遮罩。
- `src/ui/selection_tip.py`：选区旁的轻量翻译按钮。

## 翻译流程

### 文本翻译

1. 全局鼠标监听器检测拖选完成，或由 `F2`（可在设置中修改）主动触发。
2. 异步剪贴板读取器模拟复制并完整恢复原剪贴板。
3. 自动划词模式在选区附近显示轻量翻译按钮，点击后才调用接口。
4. 根据当前翻译引擎调用大模型或外部翻译服务。
5. 工作线程通过 Qt 信号发送原文、进度、流式译文和最终结果。

### 截图翻译

1. 截取选区；远程识别时编码为 PNG Base64，本地识别直接使用图像。
2. `LOCAL_CPU` 使用本地 PP-OCRv6 small；`OCR_LLM` 使用独立 OCR API；`VLM` 使用翻译模型 API 识别。
3. 识别出的原文交给当前翻译引擎。
4. 气泡展示译文，编辑模式可查看和修改原文。

### 界面性能

- 启动后延迟准备隐藏的截图窗口和气泡，提前完成字体与窗口初始化。Windows 在后台预热截屏缓冲区，不保存预热截图；macOS 留到用户主动截屏时请求屏幕录制权限。
- MSS 的创建、截屏和释放均在同一个后台线程；BGRA 数据直接转换成具有独立内存的 QImage，界面线程只创建 QPixmap 并显示。
- 截图准备期间忽略重复快捷键；退出时使请求编号失效，丢弃延迟返回的旧截图。
- Windows 退出截图时隐藏并清空窗口内容，下次复用窗口；macOS 继续重建窗口以恢复输入焦点。
- 拖动选区只重绘新旧选框覆盖的区域。裁剪转 PIL 时使用实际行跨度，兼容 RGB 行对齐。
- 流式译文每 40 ms 合并刷新一次，最终结果立即显示；移除内容更新中的嵌套事件循环。

## 配置原则

- OCR API 与翻译模型 API 完全独立。
- 本地 OCR 不读取模型 API 配置，首次下载后可离线识别；模型缓存保存在配置目录下的 `models/cpu_ocr/`，避免写入程序安装目录。
- 新配置默认截图策略为 `LOCAL_CPU`；已有配置不自动切换。
- 每种翻译引擎单独保存原文语言和目标语言。
- 设置窗口使用批量更新，一次保存仅写入配置文件一次。
- 源码默认配置不包含真实密钥；密钥只保存在本地 `config.ini`。

## 测试

`tests/` 使用标准库 `unittest`，覆盖：

- OpenAI 普通与流式响应解析。
- OCR API 和翻译 API 路由。
- 本地 CPU OCR 路由、会话复用、输入图像保护及取消/异常处理。
- 截屏后台线程、资源复用与失败重试、旧请求丢弃、窗口复用、裁剪行对齐及流式刷新合并。
- 图片编码不修改输入对象。
- 百度签名和 Google 响应解析。
- 按引擎独立语言列表。
- 设置窗口批量保存。
