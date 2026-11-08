import random
from datetime import UTC, datetime, timedelta

from sns_recommend.dataset import encode
from sns_recommend.trainer import gate
from sns_recommend.training import compare, fit, split

T0 = datetime(2026, 11, 8, tzinfo=UTC)


def synthetic_sessions(n=400, seed=1):
    """Readers click the topic they reacted to last, which the mean vector blurs."""
    rnd = random.Random(seed)
    features = {
        p: {
            "vector": [1.0 if p % 4 == t else 0.0 for t in range(4)] + [rnd.random() * 0.1],
            "created_at": T0,
        }
        for p in range(1, 41)
    }
    sessions = []
    for i in range(n):
        older, latest = rnd.sample(range(4), 2)
        earlier = rnd.sample([p for p in features if p % 4 == older], 3)
        history = [(p, "click", T0 - timedelta(hours=1)) for p in earlier]
        history.append((rnd.choice([p for p in features if p % 4 == latest]), "click", T0))
        candidates = rnd.sample(list(features), 10)
        labels = [[float(p % 4 == latest), 0.0] for p in candidates]
        sessions.append(
            {
                "start": T0 + timedelta(minutes=i),
                "history": history,
                "candidates": candidates,
                "labels": labels,
            }
        )
    return sessions, features


def test_the_model_learns_what_the_mean_vector_misses():
    sessions, features = synthetic_sessions()
    train, valid = split(sessions)
    assert train[-1]["start"] < valid[0]["start"]
    model = fit(encode(train, features), epochs=20, batch_size=16)
    report = compare(encode(valid, features), {"model": model})
    assert report["model"] > report["embedding"] + 0.05


def test_gate_promotes_only_a_clear_improvement():
    assert gate({"candidate": 0.70, "embedding": 0.60})[0]
    assert not gate({"candidate": 0.605, "embedding": 0.60})[0]
    assert not gate({"candidate": 0.70, "embedding": 0.60, "active": 0.72})[0]
    assert not gate({"candidate": None, "embedding": 0.60})[0]
