"""无需 GPU 或模型 API 的本地截图文字识别。"""

import os
from pathlib import Path
from threading import Lock

from src import config


class LocalOCRError(RuntimeError):
    pass


_engine = None
_engine_lock = Lock()


def _create_engine():
    try:
        from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR
        import onnxruntime  # noqa: F401 — 提前检查 CPU 推理依赖。
    except ImportError as error:
        raise LocalOCRError(
            "缺少本地 CPU OCR 依赖，请安装项目 requirements.txt 中的 rapidocr 和 onnxruntime。"
        ) from error

    model_dir = Path(config.CONFIG_DIR) / "models" / "cpu_ocr"
    model_dir.mkdir(parents=True, exist_ok=True)
    return RapidOCR(params={
        "Global.model_root_dir": str(model_dir),
        "Global.use_cls": False,
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "EngineConfig.onnxruntime.use_cann": False,
        "EngineConfig.onnxruntime.use_coreml": False,
        "EngineConfig.onnxruntime.intra_op_num_threads": min(4, os.cpu_count() or 1),
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Det.ocr_version": OCRVersion.PPOCRV6,
        "Det.model_type": ModelType.SMALL,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "Rec.ocr_version": OCRVersion.PPOCRV6,
        "Rec.model_type": ModelType.SMALL,
    })


def recognize_text(image, status_callback=None, is_cancelled=None):
    """懒加载并复用 CPU 模型，串行推理；取消后不返回过期识别结果。"""
    global _engine
    cancelled = is_cancelled or (lambda: False)
    if cancelled():
        return ""
    with _engine_lock:
        if cancelled():
            return ""
        if _engine is None:
            if status_callback:
                status_callback("正在准备本地 CPU OCR，首次使用可能需要联网下载模型...")
            try:
                _engine = _create_engine()
            except LocalOCRError:
                raise
            except Exception as error:
                raise LocalOCRError(f"本地 CPU OCR 初始化失败：{error}") from error
        if cancelled():
            return ""
        if status_callback:
            status_callback("本地 CPU OCR 正在识别截图，首次识别可能需要下载模型...")
        try:
            result = _engine(image.convert("RGB"))
        except Exception as error:
            raise LocalOCRError(
                "本地 CPU OCR 识别失败。首次使用请保持联网以下载模型；"
                f"模型缓存目录：{Path(config.CONFIG_DIR) / 'models' / 'cpu_ocr'}。详情：{error}"
            ) from error
        if cancelled():
            return ""
        texts = getattr(result, "txts", None)
        if texts is None:
            return ""
        return "\n".join(text.strip() for text in texts if text and text.strip())
