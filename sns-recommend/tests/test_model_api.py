import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from sns_recommend.core.config import Settings, settings
from sns_recommend.providers.model_api import chat, describe, embed


@pytest.fixture(autouse=True)
def model_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MODEL_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MODEL_API_KEY", "ollama")
    settings.cache_clear()
    yield
    settings.cache_clear()


def test_default_is_real_local_model() -> None:
    assert Settings.model_fields["model_mode"].default == "live"
    cfg = Settings(_env_file=None)
    assert cfg.model_base_url == "http://localhost:11434/v1"
    assert cfg.embedding_model == "qwen3-embedding:0.6b"
    assert cfg.rerank_model == "sns-reranker"


def test_embedding_api_restores_input_order(monkeypatch: pytest.MonkeyPatch) -> None:
    def post(url: str, *, json: dict[str, Any], **_kwargs: object) -> httpx.Response:
        assert url.endswith("/v1/embeddings")
        assert json["dimensions"] == 768
        assert json["input"] == ["개발", "여행"]
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
def test_invalid_embedding_response_is_rejected(
    monkeypatch: pytest.MonkeyPatch, data: list[dict[str, Any]]
) -> None:
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, json={"data": data}, request=httpx.Request("POST", url)
        ),
    )
    with pytest.raises(ValueError):
        embed(["test"])


def test_chat_preserves_usage_and_requests_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def post(url: str, *, json: dict[str, Any], **_kwargs: object) -> httpx.Response:
        assert url.endswith("/v1/chat/completions")
        assert json["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ordered_ids":[7,8]}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", post)
    result = chat([{"role": "user", "content": "Return JSON"}], "sns-reranker")
    assert json.loads(result["content"])["ordered_ids"] == [7, 8]
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 8}


def test_vision_sends_image_bytes_not_internal_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def post(url: str, *, json: dict[str, Any], **_kwargs: object) -> httpx.Response:
        payload = json
        assert "response_format" not in payload
        assert (
            payload["messages"][0]["content"][1]["image_url"]["url"] == "data:image/png;base64,YWJj"
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "여행 풍경"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", post)
    assert describe(b"abc", "image/png") == "여행 풍경"


def test_provider_error_is_not_treated_as_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(503, request=httpx.Request("POST", url))
    )
    with pytest.raises(httpx.HTTPStatusError):
        chat([], "sns-reranker")
