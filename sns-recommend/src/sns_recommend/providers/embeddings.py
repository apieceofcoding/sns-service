from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from sns_recommend.core.config import settings
from sns_recommend.core.measurement import measured_call
from sns_recommend.providers.recordings import recording_path, write_recording

KEYWORDS = [
    ["python", "fastapi", "postgresql", "백엔드", "데이터베이스"],
    ["서울", "제주", "여행", "사진", "맛집"],
    ["운동", "러닝", "건강", "근력", "훈련"],
    ["음악", "기타", "공연", "앨범"],
    ["저축", "예산", "가계부", "경제"],
]


def normalize(vector: Sequence[float]) -> list[float]:
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm == 0:
        raise ValueError("embedding must be finite and nonzero")
    return [x / norm for x in vector]


def space() -> str:
    cfg = settings()
    family = (
        "fixture"
        if cfg.model_mode == "fixture"
        else "api-" + hashlib.sha256(cfg.model_base_url.rstrip("/").encode()).hexdigest()[:12]
    )
    return f"{family}:{cfg.embedding_model}:{cfg.dimensions}"


class FixtureEmbeddings(Embeddings):
    """Synthetic topic features, not model output or learned semantic embeddings."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            value = text.lower()
            v = [float(sum(word in value for word in group)) for group in KEYWORDS]
            v += [0.01] * (settings().dimensions - len(v))
            vectors.append(normalize(v))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class ModelEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cfg = settings()
        encoded = json.dumps({"space": space(), "texts": texts}, ensure_ascii=False, sort_keys=True)
        path = recording_path("emb", encoded)
        if cfg.model_mode == "replay":
            data = json.loads(path.read_text())
            if data["space"] != space() or data["texts"] != texts:
                raise ValueError("recording input/model mismatch")
            return checked_vectors(data["vectors"], len(texts))
        result = self._embed(texts)
        if cfg.model_mode == "record":
            write_recording(path, {"space": space(), "texts": texts, "vectors": result})
        return result

    def _embed(self, texts: list[str]) -> list[list[float]]:
        cfg = settings()
        if cfg.model_mode == "fixture":
            return FixtureEmbeddings().embed_documents(texts)
        from sns_recommend.providers.model_api import embed

        vectors = measured_call("embedding", cfg.embedding_model, lambda: embed(texts))
        return checked_vectors(vectors, len(texts))

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def checked_vectors(vectors: object, count: int) -> list[list[float]]:
    if (
        not isinstance(vectors, list)
        or len(vectors) != count
        or any(
            not isinstance(v, list)
            or len(v) != settings().dimensions
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
            for v in vectors
        )
    ):
        raise ValueError("invalid embedding count, dimensions or values")
    return [normalize(v) for v in vectors]


def vector_sql(vector: Sequence[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vector) + "]"
