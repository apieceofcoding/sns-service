import math

from .config import settings

# Fixture mode only: keyword counts stand in for model vectors in tests.
KEYWORDS = [
    ["python", "fastapi", "postgresql", "백엔드", "데이터베이스"],
    ["서울", "제주", "여행", "사진", "맛집"],
    ["운동", "러닝", "건강", "근력", "훈련"],
    ["llm", "ai", "모델", "프롬프트", "임베딩"],
    ["영상", "브이로그", "촬영", "편집"],
    ["식단", "단백질", "밀프렙", "닭가슴살"],
]


def normalize(vector):
    norm = math.sqrt(sum(x * x for x in vector)) or 1
    return [x / norm for x in vector]


def embedding_model():
    """Model name and dimensions. Fixture vectors get a prefix so they never mix."""
    cfg = settings()
    name = f"{cfg.embedding_model}:{cfg.dimensions}"
    return "fixture:" + name if cfg.model_mode == "fixture" else name


def fixture_vector(text):
    value = text.lower()
    v = [float(sum(word in value for word in group)) for group in KEYWORDS]
    return normalize(v + [0.01] * (settings().dimensions - len(v)))


def embed_texts(texts):
    if settings().model_mode == "fixture":
        return [fixture_vector(text) for text in texts]
    from .model_api import embed

    return [normalize(vector) for vector in embed(texts)]


def vector_sql(vector):
    return "[" + ",".join(str(float(x)) for x in vector) + "]"
