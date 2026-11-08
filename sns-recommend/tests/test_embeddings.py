from sns_recommend.embeddings import embed_texts, normalize


def test_fixture_vectors_preserve_topic_and_shape():
    a, b, c = embed_texts(["Python 백엔드", "PostgreSQL FastAPI", "제주 여행"])

    def dot(x, y):
        return sum(i * j for i, j in zip(x, y, strict=True))

    assert len(a) == 768
    assert dot(a, b) > dot(a, c)
    assert abs(sum(i * i for i in normalize(a)) - 1) < 1e-6
