import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from src.core import local_ocr


class LocalOCRTests(unittest.TestCase):
    def test_cpu_model_configuration_and_writable_cache(self):
        rapidocr = Mock()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(sys.modules, {"rapidocr": rapidocr, "onnxruntime": Mock()}),
            patch.object(local_ocr.config, "CONFIG_DIR", directory),
        ):
            local_ocr._create_engine()
            params = rapidocr.RapidOCR.call_args.kwargs["params"]
            self.assertEqual(params["Global.model_root_dir"], str(local_ocr.Path(directory) / "models" / "cpu_ocr"))
            self.assertTrue(local_ocr.Path(params["Global.model_root_dir"]).is_dir())
            for provider in ("cuda", "dml", "cann", "coreml"):
                self.assertFalse(params[f"EngineConfig.onnxruntime.use_{provider}"])
            self.assertIs(params["Det.engine_type"], rapidocr.EngineType.ONNXRUNTIME)
            self.assertIs(params["Rec.ocr_version"], rapidocr.OCRVersion.PPOCRV6)
            self.assertIs(params["Rec.model_type"], rapidocr.ModelType.SMALL)

    def test_model_is_reused_and_input_is_not_resized_or_mutated(self):
        image = Image.new("RGBA", (2200, 100), "white")
        engine = Mock(return_value=SimpleNamespace(txts=(" Hello ", "", "你好")))
        with patch.object(local_ocr, "_engine", None), patch.object(local_ocr, "_create_engine", return_value=engine) as create:
            self.assertEqual(local_ocr.recognize_text(image), "Hello\n你好")
            self.assertEqual(local_ocr.recognize_text(image), "Hello\n你好")
            create.assert_called_once_with()
        self.assertEqual(image.mode, "RGBA")
        self.assertEqual(engine.call_args.args[0].mode, "RGB")
        self.assertEqual(engine.call_args.args[0].size, image.size)

    def test_blank_result_returns_empty_text(self):
        with patch.object(local_ocr, "_engine", Mock(return_value=SimpleNamespace(txts=None))):
            self.assertEqual(local_ocr.recognize_text(Image.new("RGB", (20, 20))), "")

    def test_cancelled_request_does_not_initialize_model(self):
        with patch.object(local_ocr, "_create_engine") as create:
            self.assertEqual(local_ocr.recognize_text(None, is_cancelled=lambda: True), "")
            create.assert_not_called()

    def test_cancellation_during_inference_discards_output(self):
        cancelled = False

        def inference(image):
            nonlocal cancelled
            cancelled = True
            return SimpleNamespace(txts=("stale output",))

        with patch.object(local_ocr, "_engine", Mock(side_effect=inference)):
            result = local_ocr.recognize_text(Image.new("RGB", (20, 20)), is_cancelled=lambda: cancelled)
        self.assertEqual(result, "")

    def test_missing_dependencies_have_an_actionable_error(self):
        with patch.dict(sys.modules, {"rapidocr": None}), self.assertRaisesRegex(local_ocr.LocalOCRError, "requirements.txt"):
            local_ocr._create_engine()

    def test_inference_failure_explains_model_download_and_cache(self):
        with patch.object(local_ocr, "_engine", Mock(side_effect=RuntimeError("download timeout"))):
            with self.assertRaisesRegex(local_ocr.LocalOCRError, "模型缓存目录"):
                local_ocr.recognize_text(Image.new("RGB", (20, 20)))


if __name__ == "__main__":
    unittest.main()
