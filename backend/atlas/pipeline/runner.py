"""Runs one claimed job: the life cycle of a `runs` row, retries and stage hand-over.

A stage does all its database work in one transaction. If it fails, nothing it
wrote is kept, so running it again is safe (design rule 7).
"""

import datetime
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from atlas.db import atlas_store
from atlas.db.models import Job, Run, Source
from atlas.db.session import user_session
from atlas.domain.generated.vocabulary import VOCABULARY_VERSION, SourceStatus
from atlas.domain.rules import RuleViolation
from atlas.logging import get_logger
from atlas.pipeline import queue
from atlas.pipeline.queue import ClaimedJob
from atlas.pipeline.stages import (
    PIPELINE_VERSION,
    STATUS_DURING,
    Defer,
    Outcome,
    Stage,
    StageError,
    Wait,
)
from atlas.providers.base import Providers
from atlas.settings import Settings

log = get_logger("atlas.pipeline")

HEARTBEAT_SECONDS = 60.0
RETRY_BASE_SECONDS = 5.0


@dataclass
class StageContext:
    session: Session
    user_id: uuid.UUID
    source: Source
    run: Run
    job: Job
    providers: Providers
    settings: Settings
    workdir: Path

    def remember(self, **values: object) -> None:
        """Keep values on the job between deferred attempts of the same stage."""
        self.job.payload = {**self.job.payload, **values}


type Handler = Callable[[StageContext], Outcome]


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


def _begin(claimed: ClaimedJob) -> tuple[Stage, uuid.UUID, uuid.UUID] | None:
    """Create the run row for this attempt, or reuse the one a deferred attempt left."""
    with user_session(claimed.user_id) as session:
        job = session.get(Job, claimed.job_id)
        if job is None or job.status != "running":
            return None
        stage = Stage(job.stage)
        run_id = job.payload.get("run_id")
        run = session.get(Run, uuid.UUID(run_id)) if run_id else None
        if run is None or run.status != "running":
            run = Run(
                user_id=claimed.user_id,
                source_id=job.source_id,
                kind=stage.value,
                pipeline_version=PIPELINE_VERSION,
                schema_version=VOCABULARY_VERSION,
            )
            session.add(run)
            session.flush()
            job.payload = {**job.payload, "run_id": str(run.id)}
        session.execute(
            update(Source)
            .where(Source.id == job.source_id)
            .values(status=STATUS_DURING[stage].value)
        )
        return stage, job.source_id, run.id


def _retract_previous(
    session: Session, source_id: uuid.UUID, stage: Stage, keep: uuid.UUID
) -> None:
    """Running a stage again first retracts the earlier run for the same key."""
    previous = session.scalars(
        select(Run.id).where(
            Run.source_id == source_id,
            Run.kind == stage.value,
            Run.pipeline_version == PIPELINE_VERSION,
            Run.id != keep,
            Run.status != "retracted",
        )
    ).all()
    for run_id in previous:
        atlas_store.retract_run(session, run_id)


class Cancelled(Exception):
    """The job was cancelled while its stage ran; everything the stage did is discarded."""


def _finish(ctx: StageContext, stage: Stage, outcome: Outcome) -> None:
    # A reprocess or a retraction may have cancelled this job while the stage ran.
    still_running = ctx.session.scalar(
        select(Job.status).where(Job.id == ctx.job.id).with_for_update()
    )
    if still_running != "running":
        raise Cancelled
    if isinstance(outcome, Defer):
        ctx.job.status = "queued"
        ctx.job.attempts = max(ctx.job.attempts - 1, 0)  # Waiting on a provider is not a failure.
        ctx.job.run_after = _now() + datetime.timedelta(seconds=outcome.seconds)
        ctx.job.locked_at = ctx.job.locked_by = None
        return
    ctx.run.status = "succeeded"
    ctx.run.finished_at = _now()
    ctx.job.status = "succeeded"
    ctx.job.locked_at = ctx.job.locked_by = None
    if isinstance(outcome, Wait):
        ctx.source.status = outcome.status.value
        return
    ctx.run.usage = outcome.usage or None
    ctx.run.raw_output = outcome.raw_output
    ctx.run.model = outcome.model
    ctx.run.prompt_version = outcome.prompt_version
    if outcome.stage is None:
        ctx.source.status = SourceStatus.READY.value
    else:
        queue.enqueue(ctx.session, ctx.user_id, ctx.source.id, outcome.stage)
        ctx.source.status = STATUS_DURING[outcome.stage].value


def _fail(
    claimed: ClaimedJob, run_id: uuid.UUID, code: str, retryable: bool, max_attempts: int
) -> bool:
    """Record a failure. Returns True when the job will be tried again."""
    with user_session(claimed.user_id) as session:
        job = session.get(Job, claimed.job_id, with_for_update=True)
        if job is None or job.status != "running":
            return False  # Cancelled meanwhile; leave it as the canceller set it.
        job.locked_at = job.locked_by = None
        job.error = code
        if retryable and job.attempts < max_attempts:
            job.status = "queued"
            job.run_after = _now() + datetime.timedelta(
                seconds=RETRY_BASE_SECONDS * 2 ** (job.attempts - 1)
            )
            return True
        job.status = "failed"
        session.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(status="failed", error=code, finished_at=func.now())
        )
        session.execute(
            update(Source)
            .where(Source.id == job.source_id)
            .values(status=SourceStatus.FAILED.value)
        )
        return False


class _Heartbeat:
    """Renews the job's lease while a long stage runs, so no other worker claims it."""

    def __init__(self, claimed: ClaimedJob) -> None:
        self._claimed = claimed
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._beat, daemon=True)

    def _beat(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                with user_session(self._claimed.user_id) as session:
                    session.execute(
                        update(Job)
                        .where(Job.id == self._claimed.job_id, Job.status == "running")
                        .values(locked_at=func.now())
                    )
            except Exception as error:
                # One missed beat must not end the heartbeat; the next one renews the lease.
                log.warning("job.heartbeat_failed", job_id=self._claimed.job_id, error=error)

    def __enter__(self) -> None:
        self._thread.start()

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)


def run_job(
    claimed: ClaimedJob, handlers: dict[Stage, Handler], providers: Providers, settings: Settings
) -> None:
    begun = _begin(claimed)
    if begun is None:
        return
    stage, source_id, run_id = begun
    started = _now()
    try:
        with (
            _Heartbeat(claimed),
            tempfile.TemporaryDirectory(prefix="atlas-") as workdir,
            user_session(claimed.user_id) as session,
        ):
            job = session.get(Job, claimed.job_id)
            source = session.get(Source, source_id)
            run = session.get(Run, run_id)
            if job is None or source is None or run is None:
                return
            _retract_previous(session, source_id, stage, keep=run_id)
            ctx = StageContext(
                session, claimed.user_id, source, run, job, providers, settings, Path(workdir)
            )
            outcome = handlers[stage](ctx)
            _finish(ctx, stage, outcome)
    except Cancelled:
        log.info("stage.cancelled", stage=stage, source_id=source_id, run_id=run_id)
        return
    except Exception as error:
        if isinstance(error, StageError):
            code, retryable = error.code, error.retryable
        elif isinstance(error, RuleViolation):
            code, retryable = error.code, False
        else:
            code, retryable = "unexpected_error", True
        again = _fail(claimed, run_id, code, retryable, settings.job_max_attempts)
        log.error(
            "stage.failed",
            stage=stage,
            source_id=source_id,
            run_id=run_id,
            code=code,
            error=error,
            will_retry=again,
        )
        return
    elapsed_ms = int((_now() - started).total_seconds() * 1000)
    log.info(
        "stage.finished",
        stage=stage,
        source_id=source_id,
        run_id=run_id,
        outcome=type(outcome).__name__.lower(),
        duration_ms=elapsed_ms,
    )


def work_once(handlers: dict[Stage, Handler], providers: Providers, settings: Settings) -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    claimed = queue.claim(
        settings.worker_name, settings.job_lease_seconds, settings.job_max_attempts
    )
    if claimed is None:
        return False
    run_job(claimed, handlers, providers, settings)
    return True


def drain(
    handlers: dict[Stage, Handler], providers: Providers, settings: Settings, limit: int = 100
) -> int:
    """Run jobs until none is ready. Used by tests and by the evaluation harness."""
    done = 0
    while done < limit and work_once(handlers, providers, settings):
        done += 1
    return done
