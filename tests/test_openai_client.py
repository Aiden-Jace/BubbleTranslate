import unittest
from unittest.mock import Mock, patch

from src.core import openai_client


class OpenAIClientTests(unittest.TestCase):
    def test_non_stream_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "translated"}}]
        }

        with patch(
            "src.core.openai_client.requests.post",
            return_value=response,
        ):
            result = openai_client.request_chat_completion(
                "https://example.test/v1/chat/completions",
                "key",
                {"model": "model"},
                timeout=10,
            )

        self.assertEqual(result, "translated")

    def test_stream_response_accumulates_content(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"A"}}]}',
            b'data: {"choices":[{"delta":{"content":"B"}}]}',
            b"data: [DONE]",
        ]
        updates = []

        with patch(
            "src.core.openai_client.requests.post",
            return_value=response,
        ):
            result = openai_client.request_chat_completion(
                "https://example.test/v1/chat/completions",
                "key",
                {"model": "model"},
                timeout=10,
                stream=True,
                on_stream=updates.append,
            )

        self.assertEqual(result, "AB")
        self.assertEqual(updates, ["A", "AB"])


if __name__ == "__main__":
    unittest.main()
