"""OpenAI-compatible model API. Ollama is the course default."""
from __future__ import annotations

import base64
import math
from typing import Any

import httpx

from .config import settings


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    cfg = settings()
    response = httpx.post(
        cfg.model_base_url.rstrip("/") + "/" + path,
        headers={"Authorization": "Bearer " + cfg.model_api_key.get_secret_value()},
        json=payload,
        timeout=httpx.Timeout(cfg.model_timeout_seconds, connect=5),
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError("invalid model API response")
    return result


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    cfg = settings()
    result = _post("embeddings", {
        "model": cfg.embedding_model, "input": texts,
        "dimensions": cfg.dimensions, "encoding_format": "float",
    })
    rows = result.get("data")
    if not isinstance(rows, list) or len(rows) != len(texts):
        raise ValueError("invalid embedding response count")
    if any(not isinstance(row, dict) or type(row.get("index")) is not int for row in rows):
        raise ValueError("invalid embedding response indices")
    rows = sorted(rows, key=lambda row: row["index"])
    if [row["index"] for row in rows] != list(range(len(texts))):
        raise ValueError("invalid embedding response indices")
    vectors = [row.get("embedding") for row in rows]
    if any(not isinstance(v, list) or len(v) != cfg.dimensions
           or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
           or not any(v) for v in vectors):
        raise ValueError("invalid embedding dimensions or values")
    return vectors


def chat(messages: list[dict[str, Any]], model: str, *, json_output: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": False,
                               "temperature": 0, "max_tokens": 1024}
    if json_output:
        payload["response_format"] = {"type": "json_object"}
    response = _post("chat/completions", payload)
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("invalid chat response")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str) or not message["content"].strip():
        raise ValueError("empty chat response")
    raw_usage = response.get("usage") or {}
    usage = {}
    if isinstance(raw_usage, dict):
        for source, target in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
            value = raw_usage.get(source)
            if type(value) is int and value >= 0:
                usage[target] = value
    return {"content": message["content"], "usage": usage}


def describe(image: bytes, mime_type: str) -> str:
    if mime_type not in {"image/jpeg", "image/png", "image/webp"} or not image or len(image) > 5 * 1024 * 1024:
        raise ValueError("use a JPEG, PNG or WebP image up to 5 MB")
    encoded = base64.b64encode(image).decode("ascii")
    messages = [{"role": "user", "content": [
        {"type": "text", "text": "이미지에 보이는 장면과 주제를 한국어 두 문장으로 설명하세요. 보이지 않는 정보는 추측하지 마세요."},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
    ]}]
    return chat(messages, settings().rerank_model, json_output=False)["content"]
