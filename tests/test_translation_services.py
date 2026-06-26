import hashlib
import unittest
from unittest.mock import Mock, patch

from src import config
from src.core import translation_services


class TranslationServiceTests(unittest.TestCase):
    def test_provider_language_lists_are_independent(self):
        counts = {
            provider: len(translation_services.get_language_options(provider)[1])
            for provider in translation_services.PROVIDERS
        }
        self.assertGreaterEqual(len(set(counts.values())), 4)

    def test_baidu_signature(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "trans_result": [{"dst": "你好"}]
        }

        with (
            patch.object(config, "BAIDU_APP_ID", "app"),
            patch.object(config, "BAIDU_SECRET_KEY", "secret"),
            patch.object(config, "BAIDU_API_URL", "https://baidu.test"),
            patch(
                "src.core.translation_services.random.randint",
                return_value=12345,
            ),
            patch(
                "src.core.translation_services.requests.post",
                return_value=response,
            ) as request,
        ):
            result = translation_services.translate(
                "hello",
                "英语",
                "中文",
                provider="BAIDU",
            )

        payload = request.call_args.kwargs["data"]
        expected = hashlib.md5(
            "apphello12345secret".encode("utf-8")
        ).hexdigest()
        self.assertEqual(result, "你好")
        self.assertEqual(payload["sign"], expected)

    def test_deepl_uses_configured_endpoint(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "translations": [{"text": "你好"}]
        }

        with (
            patch.object(config, "DEEPL_API_KEY", "key"),
            patch.object(config, "DEEPL_API_URL", "https://deepl.test"),
            patch(
                "src.core.translation_services.requests.post",
                return_value=response,
            ) as request,
        ):
            result = translation_services.translate(
                "hello",
                "英语",
                "中文",
                provider="DEEPL",
            )

        self.assertEqual(result, "你好")
        self.assertEqual(request.call_args.args[0], "https://deepl.test")
        self.assertEqual(
            request.call_args.kwargs["data"]["source_lang"],
            "EN",
        )

    def test_google_response_segments_are_joined(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [[["你", "you"], ["好", "good"]]]

        with patch(
            "src.core.translation_services.requests.get",
            return_value=response,
        ):
            result = translation_services.translate(
                "hello",
                "自动检测",
                "中文",
                provider="GOOGLE",
            )

        self.assertEqual(result, "你好")

    def test_youdao_v3_signature(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "errorCode": "0",
            "translation": ["翻译结果"],
        }
        text = "abcdefghijklmnopqrstuvwxyz"

        with (
            patch.object(config, "YOUDAO_APP_KEY", "app"),
            patch.object(config, "YOUDAO_APP_SECRET", "secret"),
            patch.object(config, "YOUDAO_API_URL", "https://youdao.test"),
            patch(
                "src.core.translation_services.uuid.uuid4",
                return_value="salt",
            ),
            patch(
                "src.core.translation_services.time.time",
                return_value=100,
            ),
            patch(
                "src.core.translation_services.requests.post",
                return_value=response,
            ) as request,
        ):
            result = translation_services.translate(
                text,
                "英语",
                "中文",
                provider="YOUDAO",
            )

        sign_input = "abcdefghij26qrstuvwxyz"
        expected = hashlib.sha256(
            f"app{sign_input}salt100secret".encode("utf-8")
        ).hexdigest()
        self.assertEqual(result, "翻译结果")
        self.assertEqual(request.call_args.kwargs["data"]["sign"], expected)


if __name__ == "__main__":
    unittest.main()
