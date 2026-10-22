import json
import math
from datetime import datetime
from pathlib import Path
from .config import settings
from .embeddings import CachedEmbeddings, FixtureEmbeddings, normalize
from .ranking import rerank_candidates, validate_ranking, diversify, PROMPT_VERSION


def recall_at_k(ids, labels, k):
    relevant = {int(i) for i,v in labels.items() if v>0}
    return len(set(ids[:k]) & relevant)/len(relevant) if relevant else 0.0


def ndcg_at_k(ids, labels, k):
    gains = [labels.get(str(i),0) for i in ids[:k]]
    dcg = sum((2**v-1)/math.log2(i+2) for i,v in enumerate(gains))
    ideal = sorted(labels.values(),reverse=True)[:k]
    idcg = sum((2**v-1)/math.log2(i+2) for i,v in enumerate(ideal))
    return dcg/idcg if idcg else 0.0


def evaluate(path="data/evaluation.json", k=10):
    data = json.loads(Path(path).read_text())
    cutoff = datetime.fromisoformat(data["context_cutoff"])
    observed = datetime.fromisoformat(data["evaluation_time"])
    past = [a for a in data["actions"] if datetime.fromisoformat(a["at"])<=cutoff]
    corpus = [p for p in data["posts"] if cutoff<datetime.fromisoformat(p["created_at"])<=observed]
    embedding = FixtureEmbeddings() if settings().model_mode=="fixture" else CachedEmbeddings()
    vectors = embedding.embed_documents([p["body"] for p in data["posts"]])
    index = {p["id"]:v for p,v in zip(data["posts"],vectors,strict=True)}
    rows, stability = [], []
    for user in data["users"]:
        profile = embedding.embed_query(user["interests"])
        history = [a for a in past if a["user_id"]==user["id"]]
        liked = [index[a["post_id"]] for a in history if a["action"]=="like"]
        if liked:
            profile = normalize([0.7*x+0.3*sum(v[i] for v in liked)/len(liked)
                                 for i,x in enumerate(profile)])
        semantic = sorted(corpus,key=lambda p:sum(x*y for x,y in zip(profile,index[p["id"]],strict=True)),reverse=True)
        candidates = semantic[:30]
        inputs = {"interests":user["interests"],"history":history,"candidates":candidates,
                  "model":settings().rerank_model,"mode":settings().model_mode,
                  "prompt_version":PROMPT_VERSION}
        response = rerank_candidates(inputs)
        ordered = validate_ranking(candidates,response["ordered_ids"])
        orders = {
            "latest":[p["id"] for p in sorted(corpus,key=lambda p:p["created_at"],reverse=True)],
            "popular":[p["id"] for p in sorted(corpus,key=lambda p:p["likes"],reverse=True)],
            "embedding":[p["id"] for p in semantic],
            "fixture_llm" if settings().model_mode=="fixture" else "llm":diversify(candidates,ordered),
        }
        labels = {str(p["id"]):int(p["topic"]==user["topic"]) for p in corpus}
        lookup = {p["id"]:p for p in corpus}
        for strategy,ids in orders.items():
            rows.append({"user_id":user["id"],"strategy":strategy,
                         "recall_at_k":round(recall_at_k(ids,labels,k),4),
                         "ndcg_at_k":round(ndcg_at_k(ids,labels,k),4),
                         "author_count_at_k":len({lookup[i]["author_id"] for i in ids[:k]}),
                         "topic_count_at_k":len({lookup[i]["topic"] for i in ids[:k]})})
        second = rerank_candidates({**inputs,"candidates":list(reversed(candidates))})
        other = validate_ranking(candidates,second["ordered_ids"])
        stability.append({"user_id":user["id"],"top_k_overlap":len(set(ordered[:k])&set(other[:k]))/k,
                          "same_order":ordered==other})
    report = {"dataset":"synthetic","model_mode":settings().model_mode,"k":k,
              "context_cutoff":data["context_cutoff"],"evaluation_time":data["evaluation_time"],
              "rows":rows,"input_order_stability":stability,
              "interpretation":"Offline synthetic relevance; not real CTR or user satisfaction."}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/evaluation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report
