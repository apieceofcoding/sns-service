"""Shared contracts for recommend inputs, outputs and stored jobs."""

from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict
from uuid import UUID

from psycopg import Connection

type DatabaseRow = dict[str, Any]
type DatabaseConnection = Connection[DatabaseRow]
type ModelMode = Literal["fixture", "live", "record", "replay"]
type JobKind = Literal["index", "profile", "build"]
type JobStatus = Literal["pending", "running", "done", "failed", "superseded"]


class Candidate(TypedDict):
    id: int
    author_id: int
    body: str
    created_at: str
    topic: NotRequired[str]  # Evaluation files only. The SNS database has no topic column.
    version: NotRequired[int]
    likes: NotRequired[int]
    similarity: NotRequired[float | None]
    sources: NotRequired[list[str]]


class Action(TypedDict):
    kind: str
    post_id: int
    user_id: NotRequired[int]
    at: NotRequired[str]


class RankingInput(TypedDict):
    interests: str
    history: list[Action]
    candidates: list[Candidate]
    model: str
    mode: ModelMode
    prompt_version: str
    user_id: NotRequired[int]


class TokenUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class RankingResult(TypedDict):
    ordered_ids: list[int]
    mode: ModelMode
    usage: TokenUsage


class FeedResponse(TypedDict):
    ready: bool
    post_ids: list[int]
    next_cursor: str | None
    snapshot_id: NotRequired[str]
    strategy: NotRequired[str]
    created_at: NotRequired[float]
    stale: NotRequired[bool]
    refresh_job: NotRequired[str | None]


class GenerationResult(TypedDict):
    strategy: str
    post_ids: list[int]
    published: bool


class GraphResult(GenerationResult):
    job_id: str


class PausedResult(TypedDict):
    paused: Literal[True]
    job_id: str
    next: str


class EventResult(TypedDict):
    accepted: bool
    duplicate: bool


class Job(TypedDict):
    id: UUID
    kind: JobKind
    user_id: int | None
    post_id: int | None
    generation: int
    payload: dict[str, Any]
    status: JobStatus
    attempts: int
    available_at: datetime
    lease_until: datetime | None
    owner: UUID | None
    error: str | None
    created_at: datetime


class IndexResult(TypedDict):
    indexed: int
    mode: ModelMode
    space: str


class MetricsReport(TypedDict):
    model_calls: list[DatabaseRow]
    recent_generations: list[DatabaseRow]
    note: str


class QualityRow(TypedDict):
    user_id: int
    strategy: str
    recall_at_k: float
    ndcg_at_k: float
    author_count_at_k: int
    topic_count_at_k: int


class StabilityRow(TypedDict):
    user_id: int
    top_k_overlap: float
    same_order: bool


class EvaluationReport(TypedDict):
    dataset: str
    model_mode: ModelMode
    k: int
    context_cutoff: str
    evaluation_time: str
    rows: list[QualityRow]
    input_order_stability: list[StabilityRow]
    interpretation: str


class BenchmarkReport(MetricsReport):
    scope: str
    mode: ModelMode
    requests: int
    read_p95_ms: float
    read_mean_ms: float
    cache_hit_rate: float
    mean_list_age_seconds: float | None
