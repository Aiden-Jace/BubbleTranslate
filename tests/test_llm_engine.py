import unittest
from unittest.mock import patch

from PIL import Image

from src import config
from src.core.llm_engine import LLMTextWorker, LLMVisionWorker, pil_to_base64


class LLMEngineTests(unittest.TestCase):
    def test_image_encoding_does_not_mutate_input(self):
        image = Image.new("RGBA", (2000, 1000), "white")
        original_mode = image.mode
        original_size = image.size

        encoded = pil_to_base64(image)

        self.assertTrue(encoded)
        self.assertEqual(image.mode, original_mode)
        self.assertEqual(image.size, original_size)

    def test_text_worker_uses_selected_external_provider(self):
        worker = LLMTextWorker("hello", source_lang="英语", target_lang="中文")
        results = []
        worker.result_ready.connect(results.append)

        with (
            patch.object(config, "TRANSLATION_MODE", "GOOGLE"),
            patch(
                "src.core.llm_engine.translation_services.translate",
                return_value="你好",
            ) as translate,
        ):
            worker.run()

        translate.assert_called_once_with(
            "hello",
            source_lang="英语",
            target_lang="中文",
        )
        self.assertEqual(results, ["你好"])

    def test_ocr_strategy_uses_ocr_api_then_translation_api(self):
        worker = LLMVisionWorker(
            Image.new("RGB", (20, 20), "white"),
            source_lang="英语",
            target_lang="中文",
        )
        calls = []

        def request(base_url, api_key, payload, **kwargs):
            calls.append((base_url, api_key, payload["model"]))
            return "hello" if len(calls) == 1 else "你好"

        with (
            patch.object(config, "SCREENSHOT_STRATEGY", "OCR_LLM"),
            patch.object(config, "TRANSLATION_MODE", "LLM"),
            patch.object(config, "OCR_BASE_URL", "https://ocr.test"),
            patch.object(config, "OCR_API_KEY", "ocr-key"),
            patch.object(config, "OCR_MODEL", "ocr-model"),
            patch.object(config, "BASE_URL", "https://chat.test"),
            patch.object(config, "API_KEY", "chat-key"),
            patch.object(config, "CHAT_MODEL", "chat-model"),
            patch(
                "src.core.llm_engine.openai_client.request_chat_completion",
                side_effect=request,
            ),
        ):
            worker.run()

        self.assertEqual(
            calls,
            [
                ("https://ocr.test", "ocr-key", "ocr-model"),
                ("https://chat.test", "chat-key", "chat-model"),
            ],
        )

    def test_local_cpu_strategy_uses_google_without_model_api_or_image_encoding(self):
        image = Image.new("RGB", (20, 20), "white")
        worker = LLMVisionWorker(image, source_lang="英语", target_lang="中文")
        sources, results = [], []
        worker.source_ready.connect(sources.append)
        worker.result_ready.connect(results.append)
        with (
            patch.object(config, "SCREENSHOT_STRATEGY", "LOCAL_CPU"),
            patch.object(config, "TRANSLATION_MODE", "GOOGLE"),
            patch("src.core.llm_engine.local_ocr.recognize_text", return_value="hello") as recognize,
            patch("src.core.llm_engine.translation_services.translate", return_value="你好") as translate,
            patch("src.core.llm_engine.openai_client.request_chat_completion") as remote,
            patch("src.core.llm_engine.pil_to_base64") as encode,
        ):
            worker.run()
        self.assertIs(recognize.call_args.args[0], image)
        translate.assert_called_once_with("hello", source_lang="英语", target_lang="中文")
        remote.assert_not_called()
        encode.assert_not_called()
        self.assertEqual(sources, ["hello"])
        self.assertEqual(results, ["你好"])

    def test_local_cpu_empty_or_failed_ocr_does_not_translate(self):
        for result in ("", RuntimeError("CPU OCR model unavailable")):
            with self.subTest(result=result):
                worker = LLMVisionWorker(Image.new("RGB", (20, 20)))
                errors = []
                worker.error_occurred.connect(errors.append)
                with (
                    patch.object(config, "SCREENSHOT_STRATEGY", "LOCAL_CPU"),
                    patch("src.core.llm_engine.local_ocr.recognize_text", side_effect=result if isinstance(result, Exception) else None, return_value=""),
                    patch.object(worker, "_translate_text") as translate,
                ):
                    worker.run()
                translate.assert_not_called()
                self.assertEqual(len(errors), 1)

    def test_local_cpu_cancelled_ocr_does_not_emit_source_or_translate(self):
        worker = LLMVisionWorker(Image.new("RGB", (20, 20)))
        sources = []
        worker.source_ready.connect(sources.append)

        def recognize(*args, **kwargs):
            worker.stop()
            return "stale text"

        with (
            patch.object(config, "SCREENSHOT_STRATEGY", "LOCAL_CPU"),
            patch("src.core.llm_engine.local_ocr.recognize_text", side_effect=recognize),
            patch.object(worker, "_translate_text") as translate,
        ):
            worker.run()
        self.assertEqual(sources, [])
        translate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
