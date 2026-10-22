from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from sns_recommend.core.types import DatabaseConnection
from sns_recommend.storage import source
from sns_recommend.storage.postgres import source_connection


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    action: Literal[
        "post.updated",
        "post.deleted",
        "impression",
        "click",
        "like",
        "not_interested",
    ]
    occurred_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: int | None = Field(default=None, gt=0, le=2**63 - 1, strict=True)
    post_id: int | None = Field(default=None, gt=0, le=2**63 - 1, strict=True)
    version: int | None = Field(default=None, ge=1, le=2**63 - 1, strict=True)

    @model_validator(mode="after")
    def validate_fields(self) -> Self:
        if self.action.startswith("post."):
            if self.post_id is None or self.version is None:
                raise ValueError("post_id and version required")
        else:
            if self.user_id is None or self.version is not None:
                raise ValueError("user_id required; version is only for post changes")
            if self.post_id is None:
                raise ValueError("post_id required")
        return self


def accept_event(event: Event) -> dict[str, bool]:
    if event.user_id is not None and not source.user_exists(event.user_id):
        raise LookupError("unknown user")
    with source_connection() as conn:
        row = conn.execute(
            """INSERT INTO recommend_events(id,action,user_id,post_id,version,created_at)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id""",
            (
                event.event_id,
                event.action,
                event.user_id,
                event.post_id,
                event.version,
                event.occurred_at,
            ),
        ).fetchone()
    return {"accepted": bool(row), "duplicate": not bool(row)}


def excluded_ids(conn: DatabaseConnection, user_id: int) -> set[int]:
    # Read the original event history, including events not consumed yet.
    with source_connection() as original:
        rows = original.execute(
            """SELECT DISTINCT post_id FROM recommend_events WHERE user_id=%s
            AND action IN ('impression','not_interested') AND created_at<=now()""",
            (user_id,),
        ).fetchall()
    return {row["post_id"] for row in rows}
