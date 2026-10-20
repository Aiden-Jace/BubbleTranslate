import base64
import io

from PIL import Image
from PySide6.QtCore import QThread, Signal

from src import config
from src.core import local_ocr, openai_client, translation_services


def pil_to_base64(pil_image):
    """将截图编码为适合文字识别的 PNG Base64。"""
    image = pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image.copy()
    max_size = config.MAX_IMAGE_SIZE
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=3)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _translation_prompt(source_language, target_language, from_ocr=False):
    languages = dict(source_language=source_language, target_language=target_language)
    context = config.render_prompt('OCR_CONTEXT', **languages) if from_ocr else ""
    return config.render_prompt(
        'TRANSLATION_SYSTEM', ocr_context=context, **languages,
    )


def _friendly_request_error(error):
    message = str(error)
    lowered = message.lower()
    if "invalidchunklength" in lowered or "connection broken" in lowered:
        return "远程服务器连接中断，请检查模型服务状态或显存占用。"
    if "timeout" in lowered:
        return "请求超时，请稍后重试或检查网络与模型服务。"
    if "404" in message:
        return "接口地址无效 (404)，请检查 Base URL。"
    if "401" in message:
        return "认证失败 (401)，请检查 API Key。"
    return message


class TranslationWorkerBase(QThread):
    result_ready = Signal(str)
    stream_ready = Signal(str)
    source_ready = Signal(str)
    error_occurred = Signal(str)
    status_msg = Signal(str)

    def __init__(self, target_lang=None, source_lang=None):
        super().__init__()
        self.target_lang = target_lang or config.DEFAULT_TARGET_LANGUAGE
        self.source_lang = source_lang or "自动检测"
        self._is_running = True

    def stop(self):
        self._is_running = False

    def _is_cancelled(self):
        return not self._is_running

    def _emit_result(self, text, empty_message="模型未返回有效结果"):
        if self._is_running and text:
            self.result_ready.emit(text)
            return True
        if self._is_running:
            self.error_occurred.emit(empty_message)
        return False

    def _translate_with_selected_provider(self, text):
        return translation_services.translate(
            text,
            source_lang=self.source_lang,
            target_lang=self.target_lang,
        )

    def _request_llm_translation(self, text, from_ocr=False):
        payload = {
            "model": config.CHAT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": _translation_prompt(
                        self.source_lang,
                        self.target_lang,
                        from_ocr=from_ocr,
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": config.CHAT_TEMPERATURE,
            "stream": config.STREAM_OUTPUT,
        }
        return openai_client.request_chat_completion(
            config.BASE_URL,
            config.API_KEY,
            payload,
            timeout=config.TIMEOUT,
            stream=config.STREAM_OUTPUT,
            on_stream=self.stream_ready.emit,
            is_cancelled=self._is_cancelled,
        )

    def _translate_text(self, text, from_ocr=False):
        if config.TRANSLATION_MODE == "LLM":
            return self._request_llm_translation(text, from_ocr=from_ocr)
        return self._translate_with_selected_provider(text)


class LLMTextWorker(TranslationWorkerBase):
    """纯文本翻译工作线程。"""

    def __init__(self, text, target_lang=None, source_lang=None):
        super().__init__(target_lang=target_lang, source_lang=source_lang)
        self.text = text

    def run(self):
        try:
            if self._is_cancelled():
                return
            self.source_ready.emit(self.text)
            self.status_msg.emit(f"正在通过 {config.TRANSLATION_MODE} 翻译文本...")
            result = self._translate_text(self.text)
            self._emit_result(result, f"{config.TRANSLATION_MODE} 翻译返回空结果")
        except Exception as error:
            if self._is_running:
                self.error_occurred.emit(f"文本翻译失败: {_friendly_request_error(error)}")


class LLMVisionWorker(TranslationWorkerBase):
    """截图识别与翻译工作线程。"""

    def __init__(self, pil_img, target_lang=None, source_lang=None):
        super().__init__(target_lang=target_lang, source_lang=source_lang)
        self.pil_img = pil_img

    def run(self):
        try:
            if self._is_cancelled():
                return

            if config.SCREENSHOT_STRATEGY == "LOCAL_CPU":
                source_text = local_ocr.recognize_text(
                    self.pil_img,
                    status_callback=self.status_msg.emit,
                    is_cancelled=self._is_cancelled,
                )
                if not self._is_cancelled() and not source_text.strip():
                    self.error_occurred.emit("图片中似乎没有可识别的文字")
                    return
            else:
                image_base64 = pil_to_base64(self.pil_img)
                if config.SCREENSHOT_STRATEGY == "VLM":
                    source_text = self._recognize_with_vlm(image_base64)
                else:
                    source_text = self._recognize_with_ocr(image_base64)

            if self._is_cancelled() or not source_text:
                return

            self.source_ready.emit(source_text)
            self.status_msg.emit(f"正在将识别结果翻译为 {self.target_lang}...")
            translated_text = self._translate_text(source_text, from_ocr=True)
            self._emit_result(
                translated_text,
                f"{config.TRANSLATION_MODE} 翻译返回空结果",
            )
        except Exception as error:
            if self._is_running:
                self.error_occurred.emit(
                    f"处理失败: {_friendly_request_error(error)}"
                )

    def _recognize_with_vlm(self, image_base64):
        self.status_msg.emit("VLM 正在识别截图原文...")
        payload = {
            "model": config.CHAT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": config.render_prompt(
                        'VLM_SYSTEM',
                        source_language=self.source_lang,
                        target_language=self.target_lang,
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": config.render_prompt(
                                'VLM_USER',
                                source_language=self.source_lang,
                                target_language=self.target_lang,
                            ),
                        },
                    ],
                },
            ],
            "temperature": config.OCR_TEMPERATURE,
            "stream": False,
        }
        source_text = openai_client.request_chat_completion(
            config.BASE_URL,
            config.API_KEY,
            payload,
            timeout=config.TIMEOUT,
        )
        return self._validate_source_text(source_text, "VLM")

    def _recognize_with_ocr(self, image_base64):
        self.status_msg.emit("正在精准识别文字...")
        payload = {
            "model": config.OCR_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": config.render_prompt(
                                'OCR_USER',
                                source_language=self.source_lang,
                                target_language=self.target_lang,
                            ),
                        },
                    ],
                }
            ],
            "temperature": config.OCR_TEMPERATURE,
            "stream": False,
        }
        source_text = openai_client.request_chat_completion(
            config.OCR_BASE_URL,
            config.OCR_API_KEY,
            payload,
            timeout=config.TIMEOUT,
        )
        return self._validate_source_text(source_text, "OCR")

    def _validate_source_text(self, content, source_name):
        source_text = self._clean_model_text(content)
        if len(source_text) < 2:
            self.error_occurred.emit("图片中似乎没有可识别的文字")
            return ""
        print(f"{source_name} 识别原始结果: {source_text}")
        return source_text

    @staticmethod
    def _clean_model_text(content):
        normalized = content.strip()
        if not normalized.startswith("```"):
            return normalized

        lines = normalized.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines.pop(0)
        if lines and lines[-1].strip() == "```":
            lines.pop()
        return "\n".join(lines).strip()


class LLMVisionEngine:
    """管理单个活动翻译工作线程。"""

    def __init__(self):
        self.worker = None
        self._workers = set()

    def _stop_existing_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()

    def _cleanup_worker(self, worker):
        self._workers.discard(worker)
        if self.worker is worker:
            self.worker = None

    def _start_worker(
        self,
        worker,
        callback,
        error_callback=None,
        status_callback=None,
        stream_callback=None,
        source_callback=None,
    ):
        self._stop_existing_worker()
        self.worker = worker
        self._workers.add(worker)
        worker.finished.connect(
            lambda current=worker: self._cleanup_worker(current)
        )
        self.worker.result_ready.connect(callback)
        if error_callback:
            self.worker.error_occurred.connect(error_callback)
        if status_callback:
            self.worker.status_msg.connect(status_callback)
        if stream_callback:
            self.worker.stream_ready.connect(stream_callback)
        if source_callback:
            self.worker.source_ready.connect(source_callback)
        self.worker.start()

    def translate_image(
        self,
        pil_img,
        callback,
        error_callback=None,
        status_callback=None,
        stream_callback=None,
        source_callback=None,
        target_lang=None,
        source_lang=None,
    ):
        worker = LLMVisionWorker(
            pil_img,
            target_lang=target_lang,
            source_lang=source_lang,
        )
        self._start_worker(
            worker,
            callback,
            error_callback,
            status_callback,
            stream_callback,
            source_callback,
        )

    def stop(self, wait_ms=1000):
        """停止所有活动任务，用于应用退出。"""
        workers = list(self._workers)
        for worker in workers:
            worker.stop()
        for worker in workers:
            if worker.isRunning() and not worker.wait(wait_ms):
                worker.terminate()
                worker.wait()
        self._workers.clear()
        self.worker = None

    def translate_text(
        self,
        text,
        callback,
        error_callback=None,
        status_callback=None,
        stream_callback=None,
        source_callback=None,
        target_lang=None,
        source_lang=None,
    ):
        worker = LLMTextWorker(
            text,
            target_lang=target_lang,
            source_lang=source_lang,
        )
        self._start_worker(
            worker,
            callback,
            error_callback,
            status_callback,
            stream_callback,
            source_callback,
        )
