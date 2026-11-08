from __future__ import annotations

import time
from statistics import mean
from time import perf_counter

from .feed import read_feed
from .measurement import metrics


def benchmark(user_id: int = 7, requests: int = 100) -> dict:
    """Redis read path only. Excludes HTTP, Spring and the network between services."""
    latencies, ages = [], []
    for _ in range(requests):
        start = perf_counter()
        result = read_feed(user_id)
        latencies.append((perf_counter() - start) * 1000)
        if result["ready"]:
            ages.append(time.time() - result["created_at"])
    ordered = sorted(latencies)
    return {
        "scope": "local Redis read only; not end-to-end SNS latency",
        "requests": requests,
        "read_p95_ms": round(ordered[int((requests - 1) * 0.95)], 3),
        "read_mean_ms": round(mean(latencies), 3),
        "ready_rate": len(ages) / requests,
        "list_age_seconds": round(mean(ages), 1) if ages else None,
        **metrics(),
    }
