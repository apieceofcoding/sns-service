from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings
from psycopg.types.json import Jsonb

from sns_recommend.core.config import settings
from sns_recommend.core.measurement import measured_call
from sns_recommend.providers.recordings import recording_path, write_recording
from sns_recommend.storage.postgres import connection

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


class CachedEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cfg = settings()
        encoded = json.dumps({"space": space(), "texts": texts}, ensure_ascii=False, sort_keys=True)
        path = recording_path("emb", encoded)
        keys = [hashlib.sha256((space() + "\0" + t).encode()).hexdigest() for t in texts]
        to_cache: Sequence[int]
        if cfg.model_mode == "replay":
            # Replay must verify the recording even when the live cache is warm.
            data = json.loads(path.read_text())
            if data["space"] != space() or data["texts"] != texts:
                raise ValueError("recording input/model mismatch")
            result = checked_vectors(data["vectors"], len(texts))
            to_cache = range(len(texts))
        else:
            with connection() as conn:
                rows = conn.execute(
                    "SELECT key,embedding FROM embedding_cache WHERE key=ANY(%s)", (keys,)
                ).fetchall()
            cached = {r["key"]: r["embedding"] for r in rows}
            pending = [cached.get(key) for key in keys]
            missing = [i for i, value in enumerate(pending) if value is None]
            if missing:
                source = list(dict.fromkeys(texts[i] for i in missing))
                vectors = self._embed_missing(source)
                by_text = dict(zip(source, vectors, strict=True))
                for i in missing:
                    pending[i] = by_text[texts[i]]
            result = checked_vectors(pending, len(texts))
            to_cache = missing
        if to_cache:
            with connection() as conn:
                for i in to_cache:
                    conn.execute(
                        "INSERT INTO embedding_cache VALUES (%s,%s) ON CONFLICT DO NOTHING",
                        (keys[i], Jsonb(result[i])),
                    )
        if cfg.model_mode == "record":
            # Store the whole request so cold-cache replay uses the same input.
            write_recording(path, {"space": space(), "texts": texts, "vectors": result})
        return result

    def _embed_missing(self, texts: list[str]) -> list[list[float]]:
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
