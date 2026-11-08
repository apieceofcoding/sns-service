import torch

from sns_recommend.dataset import CANDIDATES, HISTORY
from sns_recommend.model import Ranker, load, save, score

TABLE = torch.randn(10, 8, generator=torch.Generator().manual_seed(0))
TABLE[0] = 0  # padding


def batch(candidates, history=(1, 2)):
    out = {
        "table": TABLE,
        "history": torch.zeros(1, HISTORY, dtype=torch.long),
        "actions": torch.zeros(1, HISTORY, dtype=torch.long),
        "history_age": torch.zeros(1, HISTORY),
        "candidates": torch.zeros(1, CANDIDATES, dtype=torch.long),
        "candidate_age": torch.zeros(1, CANDIDATES),
    }
    for j, post in enumerate(history):
        out["history"][0, HISTORY - len(history) + j] = post
        out["actions"][0, HISTORY - len(history) + j] = 1
    for j, post in enumerate(candidates):
        out["candidates"][0, j] = post
    return out


def test_a_candidate_score_does_not_depend_on_the_other_candidates():
    torch.manual_seed(0)
    model = Ranker(dims=8)
    alone = score(model, batch([5]))[0, 0]
    together = score(model, batch([5, 6, 7, 8]))[0, 0]
    assert torch.allclose(alone, together, atol=1e-5)


def test_empty_history_still_gives_finite_scores():
    scores = score(Ranker(dims=8), batch([3, 4], history=()))
    assert torch.isfinite(scores).all()


def test_saved_model_scores_the_same(tmp_path):
    model = Ranker(dims=8)
    save(model, tmp_path / "m.pt", {"trained_until": "t"})
    loaded, info = load(tmp_path / "m.pt")
    data = batch([3, 4])
    assert info == {"trained_until": "t"}
    assert torch.allclose(score(model, data), score(loaded, data))
