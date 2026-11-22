from __future__ import annotations

import httpx

from .config import settings


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    cfg = settings()
    response = httpx.post(
        cfg.model_base_url.rstrip("/") + "/embeddings",
        headers={"Authorization": "Bearer " + cfg.model_api_key.get_secret_value()},
        json={
            "model": cfg.embedding_model,
            "input": texts,
            "dimensions": cfg.dimensions,
            "encoding_format": "float",
        },
        timeout=httpx.Timeout(cfg.model_timeout_seconds, connect=5),
    )
    response.raise_for_status()
    vectors = [
        row["embedding"] for row in sorted(response.json()["data"], key=lambda row: row["index"])
    ]
    if len(vectors) != len(texts) or any(len(v) != cfg.dimensions for v in vectors):
        raise ValueError("invalid embedding response")
    return vectors
