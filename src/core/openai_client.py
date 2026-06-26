import json

import requests


def build_headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def request_chat_completion(
    base_url,
    api_key,
    payload,
    timeout,
    stream=False,
    on_stream=None,
    is_cancelled=None,
):
    response = requests.post(
        base_url,
        headers=build_headers(api_key),
        json=payload,
        timeout=timeout,
        stream=stream,
    )
    response.raise_for_status()

    if stream:
        return _read_stream(response, on_stream, is_cancelled)
    return extract_message_content(response.json())


def extract_message_content(payload):
    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    if not choices:
        return ""
    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip()


def _read_stream(response, on_stream, is_cancelled):
    full_content = ""
    for raw_line in response.iter_lines():
        if is_cancelled and is_cancelled():
            break
        if not raw_line:
            continue

        line = raw_line.decode("utf-8")
        if not line.startswith("data: "):
            continue

        data = line[6:]
        if data == "[DONE]":
            break

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue

        choices = payload.get("choices", [])
        if not choices:
            continue
        content = choices[0].get("delta", {}).get("content", "")
        if not content:
            continue

        full_content += content
        if on_stream:
            on_stream(full_content)

    return full_content
