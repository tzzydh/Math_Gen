from typing import Any


def extract_text_from_openai_response(response: Any) -> str:
    """兼容 chat.completions 与 responses 两类返回结构，提取文本。"""
    # chat.completions 常见结构
    choices = getattr(response, "choices", None)
    if choices:
        msg = choices[0].message
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                txt = getattr(item, "text", None)
                if txt:
                    texts.append(txt)
            if texts:
                return "\n".join(texts)

    # responses API 常见结构
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    output = getattr(response, "output", None)
    if output:
        texts = []
        for out_item in output:
            contents = getattr(out_item, "content", None) or []
            for c in contents:
                txt = getattr(c, "text", None)
                if txt:
                    texts.append(txt)
        if texts:
            return "\n".join(texts)

    raise RuntimeError("无法从 OpenAI 响应中提取文本，请检查 API 返回结构。")


def call_openai_vision_json(client: Any, model: str, prompt: str, image_data_url: str, timeout: int = 45) -> str:
    """优先 chat.completions，失败后自动降级到 responses API。"""
    try:
        resp = client.chat.completions.create(
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
        return extract_text_from_openai_response(resp)
    except Exception:
        resp = client.responses.create(
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
        return extract_text_from_openai_response(resp)
