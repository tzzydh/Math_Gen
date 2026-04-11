from typing import Any


def extract_text_from_openai_response(response: Any) -> str:
    """Extract plain text from OpenAI-compatible chat or responses payloads."""
    choices = getattr(response, "choices", None)
    if choices:
        message = choices[0].message
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    texts.append(text)
            if texts:
                return "\n".join(texts)

    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    output = getattr(response, "output", None)
    if output:
        texts: list[str] = []
        for item in output:
            contents = getattr(item, "content", None) or []
            for content in contents:
                text = getattr(content, "text", None)
                if text:
                    texts.append(text)
        if texts:
            return "\n".join(texts)

    raise RuntimeError("Unable to extract text from OpenAI-compatible response")


def call_openai_vision_json(
    client: Any,
    model: str,
    prompt: str,
    image_data_url: str,
    timeout: int = 45,
) -> str:
    """Call a vision-capable model and request a JSON object."""
    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }],
            timeout=timeout,
        )
        return extract_text_from_openai_response(response)
    except Exception as exc:
        if not hasattr(client, "responses"):
            raise exc

        response = client.responses.create(
            model=model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }],
            timeout=timeout,
        )
        return extract_text_from_openai_response(response)


def call_openai_text_json(client: Any, model: str, prompt: str, timeout: int = 45) -> str:
    """Call a text model and request JSON output."""
    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[{
                "role": "user",
                "content": prompt,
            }],
            timeout=timeout,
        )
        return extract_text_from_openai_response(response)
    except Exception:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
            }],
            timeout=timeout,
        )
        return extract_text_from_openai_response(response)
