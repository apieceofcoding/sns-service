import httpx
import pytest

from sns_recommend.config import Settings, settings
from sns_recommend.model_api import embed


@pytest.fixture(autouse=True)
def model_settings(monkeypatch):
    monkeypatch.setenv("MODEL_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MODEL_API_KEY", "ollama")
    settings.cache_clear()
    yield
    settings.cache_clear()


def test_default_is_real_local_model():
    assert Settings.model_fields["model_mode"].default == "live"
    cfg = Settings(_env_file=None)
    assert cfg.model_base_url == "http://localhost:11434/v1"
    assert cfg.embedding_model == "qwen3-embedding:0.6b"


def test_embedding_api_restores_input_order(monkeypatch):
    def post(url, **kwargs):
        assert url.endswith("/v1/embeddings")
        assert kwargs["json"]["dimensions"] == 768
        assert kwargs["json"]["input"] == ["개발", "여행"]
        vectors = [{"index": 1, "embedding": [2.0] * 768}, {"index": 0, "embedding": [1.0] * 768}]
        return httpx.Response(200, json={"data": vectors}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    assert embed(["개발", "여행"])[0][0] == 1.0


@pytest.mark.parametrize(
    "data",
    [
        [{"index": 0, "embedding": [0.0] * 768}],
        [{"index": 1, "embedding": [1.0] * 768}],
        [{"index": 0, "embedding": [True] * 768}],
    ],
)
def test_invalid_embedding_response_is_rejected(monkeypatch, data):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, json={"data": data}, request=httpx.Request("POST", url)
        ),
    )
    with pytest.raises(ValueError):
        embed(["test"])


def test_provider_error_is_not_treated_as_success(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(503, request=httpx.Request("POST", url))
    )
    with pytest.raises(httpx.HTTPStatusError):
        embed(["test"])
