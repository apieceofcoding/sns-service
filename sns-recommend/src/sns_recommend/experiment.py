from __future__ import annotations

import hashlib
from collections import Counter
from datetime import UTC, datetime
from random import Random

from . import simulator, source
from .db import connection
from .event_worker import drain
from .events import excluded_ids
from .feed import read_feed
from .measurement import record_served
from .registry import active, newest_candidate, promote, reject, version_row

ARMS = ("control", "treatment")
NEW_POSTS = 12
LIKE_TOLERANCE = 0.95


def arm(user_id: int, name: str) -> str:
    digest = hashlib.sha256(f"{name}:{user_id}".encode()).digest()
    return ARMS[digest[0] % 2]


def running() -> dict | None:
    with connection() as conn:
        return conn.execute("SELECT * FROM experiments WHERE stopped_at IS NULL").fetchone()


def assigned(user_id: int) -> dict | None:
    current = running()
    if current is None:
        return None
    group = arm(user_id, current["name"])
    treated = group == "treatment"
    return {
        "experiment": current["name"],
        "arm": group,
        "model": current["treatment_model" if treated else "control_model"],
        "spread": current["treatment_spread"] if treated else True,
    }


def start(name: str, spread: bool = True, min_impressions: int = 3000) -> dict:
    if running():
        raise ValueError("another experiment is running")
    serving, candidate = active(), newest_candidate()
    control = serving["id"] if serving else None
    treatment = candidate["id"] if candidate and spread else control
    if treatment == control and spread:
        raise ValueError("nothing to compare: train a candidate first")
    with connection() as conn:
        return conn.execute(
            """INSERT INTO experiments(name,control_model,treatment_model,treatment_spread,
            min_impressions) VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (name, control, treatment, spread, min_impressions),
        ).fetchone()


def simulate_feed(rounds: int = 3, users: int = 300) -> dict:
    from .generation import generate

    if running() is None:
        raise LookupError("start an experiment first")
    rnd = Random(f"feed:{datetime.now(UTC):%Y%m%d%H%M}")
    reader_ids = simulator.readers(users)
    hourly_cost = simulator.age_cost()
    tastes = {u: simulator.taste(u) for u in reader_ids}
    moods = {u: max(t, key=t.get) for u, t in tastes.items()}
    for _ in range(rounds):
        simulator.publish_posts(NEW_POSTS)
        drain()
        posts = {p["id"]: p for p in simulator.visible_posts()}
        rows: tuple[list, list, list] = ([], [], [])
        for user_id in reader_ids:
            try:
                generate(user_id)
            except (LookupError, RuntimeError):
                continue
            feed = read_feed(
                user_id, simulator.SHOWN, excluded=excluded_ids(user_id), alive=source.alive_ids
            )
            record_served(user_id, feed)
            moods[user_id] = simulator.drift(rnd, tastes[user_id], moods[user_id])
            shown = [posts[i] for i in feed["post_ids"] if i in posts]
            simulator.visit(
                rnd,
                user_id,
                shown,
                datetime.now(UTC),
                tastes[user_id],
                moods[user_id],
                hourly_cost,
                rows,
            )
        simulator.write(*rows)
    drain()
    return {"rounds": rounds, **report()}


def compare_readers(control: list[tuple[int, int]], treatment: list[tuple[int, int]]) -> dict:
    def gap(groups: list[int]) -> float:
        clicks, shown = [0, 0], [0, 0]
        for (c, n), g in zip(readers, groups, strict=True):
            clicks[g] += c
            shown[g] += n
        return clicks[1] / shown[1] - clicks[0] / shown[0] if shown[0] and shown[1] else 0.0

    readers = control + treatment
    labels = [0] * len(control) + [1] * len(treatment)
    shown = [sum(n for _, n in group) for group in (control, treatment)]
    if not all(shown):
        return {"lift": None, "p_value": None}
    observed = gap(labels)
    rnd, trials, extreme = Random(0), 2000, 0
    for _ in range(trials):
        rnd.shuffle(labels)
        extreme += abs(gap(labels)) >= abs(observed)
    base = sum(c for c, _ in control) / shown[0]
    return {
        "lift": round(observed / base, 3) if base else None,
        "p_value": round((extreme + 1) / (trials + 1), 4),
    }


def report(name: str | None = None) -> dict:
    with connection() as conn:
        exp = conn.execute(
            """SELECT * FROM experiments WHERE %s::text IS NULL OR name=%s
            ORDER BY started_at DESC LIMIT 1""",
            (name, name),
        ).fetchone()
        if exp is None:
            raise LookupError("no experiment")
        rows = conn.execute(
            """SELECT s.arm,s.user_id,count(*) FILTER (WHERE e.action='impression') AS shown,
            count(*) FILTER (WHERE e.action='click') AS clicks,
            count(*) FILTER (WHERE e.action='like') AS likes
            FROM served_posts s JOIN user_events e ON e.user_id=s.user_id AND e.post_id=s.post_id
            AND e.action IN ('impression','click','like') AND e.removed_at IS NULL
            WHERE s.experiment=%s GROUP BY s.arm,s.user_id""",
            (exp["name"],),
        ).fetchall()
        served = conn.execute(
            """SELECT arm,snapshot_id,array_agg(post_id) AS posts FROM served_posts
            WHERE experiment=%s GROUP BY arm,snapshot_id""",
            (exp["name"],),
        ).fetchall()
    authors = source.authors({post for row in served for post in row["posts"]})
    arms = {}
    readers = {}
    for group in ARMS:
        mine = [r for r in rows if r["arm"] == group and r["shown"]]
        shown = sum(r["shown"] for r in mine)
        shares = [
            Counter(authors.get(p) for p in row["posts"]).most_common(1)[0][1] / len(row["posts"])
            for row in served
            if row["arm"] == group
        ]
        readers[group] = [(r["clicks"], r["shown"]) for r in mine]
        arms[group] = {
            "model": exp[f"{group}_model"],
            "readers": len(mine),
            "impressions": shown,
            "click_rate": round(sum(r["clicks"] for r in mine) / shown, 4) if shown else None,
            "like_rate": round(sum(r["likes"] for r in mine) / shown, 4) if shown else None,
            "one_author_share": round(sum(shares) / len(shares), 3) if shares else None,
        }
    clicks = compare_readers(readers["control"], readers["treatment"])
    ready = all(a["impressions"] >= exp["min_impressions"] for a in arms.values())
    return {
        "experiment": exp["name"],
        "treatment_spread": exp["treatment_spread"],
        "arms": arms,
        "click_rate": clicks,
        "ready": ready,
        "verdict": exp["decision"] or verdict(arms, clicks, ready),
    }


def verdict(arms: dict, clicks: dict, ready: bool) -> str:
    if not ready or clicks["p_value"] is None:
        return "wait: planned impressions not reached"
    if clicks["p_value"] >= 0.05:
        return "no clear difference"
    if clicks["lift"] < 0:
        return "control wins"
    if arms["treatment"]["like_rate"] < arms["control"]["like_rate"] * LIKE_TOLERANCE:
        return "control wins: treatment lowers the like rate"
    return "treatment wins"


def stop() -> dict:
    current = running()
    if current is None:
        raise LookupError("no running experiment")
    result = report(current["name"])
    decision = result["verdict"].replace("wait", "inconclusive")
    candidate = version_row(current["treatment_model"]) if current["treatment_model"] else None
    if candidate and candidate["status"] == "candidate" and not decision.startswith("inconclusive"):
        if decision == "treatment wins":
            promote(candidate["id"])
        else:
            reject(candidate["id"])
    with connection() as conn:
        conn.execute(
            "UPDATE experiments SET stopped_at=now(),decision=%s WHERE name=%s",
            (decision, current["name"]),
        )
    return {**result, "verdict": decision, "active_model": (active() or {}).get("id")}
