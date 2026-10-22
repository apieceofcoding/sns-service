import hashlib
import json
import math
from pathlib import Path
from langchain_core.embeddings import Embeddings
from psycopg.types.json import Jsonb
from .config import settings
from .db import connection

KEYWORDS = [
    ["python", "fastapi", "postgresql", "백엔드", "데이터베이스"],
    ["서울", "제주", "여행", "사진", "맛집"],
    ["운동", "러닝", "건강", "근력", "훈련"],
    ["음악", "기타", "공연", "앨범"],
    ["저축", "예산", "가계부", "경제"],
]


def normalize(vector):
    norm = math.sqrt(sum(x*x for x in vector)) or 1
    return [x/norm for x in vector]


def space():
    cfg = settings()
    family = "fixture" if cfg.model_mode == "fixture" else "api-" + hashlib.sha256(cfg.model_base_url.rstrip("/").encode()).hexdigest()[:12]
    return f"{family}:{cfg.embedding_model}:{cfg.dimensions}"


class FixtureEmbeddings(Embeddings):
    """Synthetic topic features, not model output or learned semantic embeddings."""
    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            value = text.lower()
            v = [float(sum(word in value for word in group)) for group in KEYWORDS]
            v += [0.01] * (settings().dimensions-len(v))
            vectors.append(normalize(v))
        return vectors

    def embed_query(self, text):
        return self.embed_documents([text])[0]


class CachedEmbeddings(Embeddings):
    def embed_documents(self, texts):
        cfg = settings()
        keys = [hashlib.sha256((space()+t).encode()).hexdigest() for t in texts]
        result = [None] * len(texts)
        with connection() as conn:
            for i, key in enumerate(keys):
                row = conn.execute("SELECT embedding FROM embedding_cache WHERE key=%s", (key,)).fetchone()
                if row:
                    result[i] = row["embedding"]
        missing = [i for i, value in enumerate(result) if value is None]
        if missing:
            source = [texts[i] for i in missing]
            path = Path(cfg.recordings_dir) / (hashlib.sha256(json.dumps(source,ensure_ascii=False).encode()).hexdigest()+"-emb.json")
            if cfg.model_mode == "fixture":
                vectors = FixtureEmbeddings().embed_documents(source)
            elif cfg.model_mode == "replay":
                data = json.loads(path.read_text())
                if data["space"] != space() or data["texts"] != source:
                    raise ValueError("recording input/model mismatch")
                vectors = data["vectors"]
            else:
                from .model_api import embed
                vectors = embed(source)
                if cfg.model_mode == "record":
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"space":space(),"texts":source,"vectors":vectors}))
            if len(vectors) != len(missing) or any(len(v)!=cfg.dimensions for v in vectors):
                raise ValueError("embedding count/dimensions mismatch")
            with connection() as conn:
                for i, vector in zip(missing, vectors, strict=True):
                    result[i] = normalize(vector)
                    conn.execute("INSERT INTO embedding_cache VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                 (keys[i], Jsonb(result[i])))
        return result

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def vector_sql(vector):
    return "[" + ",".join(str(float(x)) for x in vector) + "]"
