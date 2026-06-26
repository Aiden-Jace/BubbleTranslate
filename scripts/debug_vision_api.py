import argparse
import base64

from src import config
from src.core.openai_client import request_chat_completion


def test_payload(name, payload):
    print(f"\n--- Testing Payload: {name} ---")
    try:
        result = request_chat_completion(
            config.OCR_BASE_URL,
            config.OCR_API_KEY,
            payload,
            timeout=config.TIMEOUT,
        )
        print(result[:500])
    except Exception as error:
        print(f"Exception: {error}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="需要测试的图片路径")
    args = parser.parse_args()

    with open(args.image, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("ascii")

    prompt = "Identify all visible text in this image."
    image_content = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
    }
    text_content = {"type": "text", "text": prompt}

    for name, content in (
        ("Text first", [text_content, image_content]),
        ("Image first", [image_content, text_content]),
    ):
        test_payload(
            name,
            {
                "model": config.OCR_MODEL,
                "messages": [{"role": "user", "content": content}],
            },
        )


if __name__ == "__main__":
    main()
