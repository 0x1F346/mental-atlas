"""The Postgres-backed job queue: one job per pipeline stage per source."""

import datetime
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text, update
from sqlalchemy.orm import Session

from atlas.db.models import Job
from atlas.db.session import anonymous_session
from atlas.pipeline.stages import Stage


@dataclass(frozen=True)
class ClaimedJob:
    job_id: uuid.UUID
    user_id: uuid.UUID


def enqueue(
    session: Session,
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    stage: Stage,
    *,
    delay_seconds: float = 0,
    payload: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        user_id=user_id,
        source_id=source_id,
        stage=stage.value,
        payload=payload or {},
        run_after=datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=delay_seconds),
    )
    session.add(job)
    session.flush()
    return job


def cancel_pending(session: Session, source_id: uuid.UUID) -> None:
    """Drop queued work for a source, before reprocessing or retracting it."""
    session.execute(
        update(Job)
        .where(Job.source_id == source_id, Job.status.in_(["queued", "running"]))
        .values(status="failed", error="cancelled", locked_at=None, locked_by=None)
    )


def claim(worker: str, lease_seconds: int, max_attempts: int = 3) -> ClaimedJob | None:
    with anonymous_session() as session:
        row = session.execute(
            text("SELECT job_id, user_id FROM atlas_claim_job(:worker, :lease, :attempts)"),
            {"worker": worker, "lease": lease_seconds, "attempts": max_attempts},
        ).one_or_none()
    return ClaimedJob(job_id=row.job_id, user_id=row.user_id) if row else None


def release(worker: str) -> int:
    with anonymous_session() as session:
        released = session.execute(
            text("SELECT atlas_release_jobs(:worker)"), {"worker": worker}
        ).scalar_one()
    return int(released)
