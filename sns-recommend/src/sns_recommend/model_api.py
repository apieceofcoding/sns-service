"""OpenAI-compatible model API. Ollama is the course default."""

from __future__ import annotations

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
    result = _post(
        "embeddings",
        {
            "model": cfg.embedding_model,
            "input": texts,
            "dimensions": cfg.dimensions,
            "encoding_format": "float",
        },
    )
    rows = result.get("data")
    if not isinstance(rows, list) or len(rows) != len(texts):
        raise ValueError("invalid embedding response count")
    if any(not isinstance(row, dict) or type(row.get("index")) is not int for row in rows):
        raise ValueError("invalid embedding response indices")
    rows = sorted(rows, key=lambda row: row["index"])
    if [row["index"] for row in rows] != list(range(len(texts))):
        raise ValueError("invalid embedding response indices")
    vectors = [row.get("embedding") for row in rows]
    if any(
        not isinstance(v, list)
        or len(v) != cfg.dimensions
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
        or not any(v)
        for v in vectors
    ):
        raise ValueError("invalid embedding dimensions or values")
    return vectors
