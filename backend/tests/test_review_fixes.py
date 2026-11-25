"""Regression tests for defects found in review. Invented data only."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from atlas.api.security import RateLimiter
from atlas.db.models import Job, Node, Run, Source
from atlas.db.session import user_session
from atlas.evaluation.fixtures import Fixture, ingest
from atlas.pipeline import queue, sources
from atlas.pipeline.handlers import HANDLERS
from atlas.pipeline.runner import StageContext, drain
from atlas.pipeline.stages import Next, Outcome, Stage
from atlas.providers.base import Providers
from atlas.settings import get_settings
from tests.conftest import run_pipeline
from tests.test_extraction import JOURNAL, concept, node, process, scripted, statement, status_of
from tests.test_ingestion import add_journal


def test_a_job_cancelled_while_its_stage_runs_leaves_nothing_behind(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    source_id = add_journal(user_id, providers)

    def reprocess_mid_stage(ctx: StageContext) -> Outcome:
        # The owner asks to reprocess while this stage is still working.
        with user_session(user_id) as other:
            source = other.get(Source, source_id)
            assert source is not None
            sources.reprocess(other, source, Stage.SEGMENT_TEXT)
        return Next(Stage.COMMIT)

    handlers = {**HANDLERS, Stage.SPEAKERS: reprocess_mid_stage}
    for _ in range(3):  # media, segment_text, then the interrupted speakers stage
        drain(handlers, providers, get_settings(), limit=1)

    jobs = db.scalars(select(Job).where(Job.source_id == source_id).order_by(Job.created_at)).all()
    speakers_job = next(job for job in jobs if job.stage == "speakers")
    assert (speakers_job.status, speakers_job.error) == ("failed", "cancelled")
    # The cancelled stage queued nothing; only the reprocess's own job is waiting.
    assert [(j.stage, j.status) for j in jobs if j.status == "queued"] == [
        ("segment_text", "queued")
    ]
    run = db.scalars(select(Run).where(Run.source_id == source_id, Run.kind == "speakers")).one()
    assert run.status != "succeeded"

    run_pipeline(providers)
    assert status_of(db, source_id) == "ready"


def test_a_diagnosis_must_be_named_in_the_speakers_own_words(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    low = {"segment": "S0", "quote": "I could not sit still all day", "kind": "report",
           "text": "The owner has depression and could not sit still."}  # fmt: skip
    scripted(
        providers,
        [low],
        {
            "concepts": [
                concept("c1", "trait", "depression", kind="diagnosis"),
                concept("c2", "trait", "depression", kind="diagnosis", attributes={"nope": 1}),
                concept("c3", "behaviour", "restlessness"),
            ]
        },
    )
    process(user_id, providers, JOURNAL)
    stored = db.scalars(select(Node).where(Node.is_system.is_(False))).all()
    # Not as a diagnosis, and not salvaged into the unsorted pile either.
    assert [(n.type, n.name) for n in stored] == [("behaviour", "restlessness")]


def test_a_feeling_is_stated_only_if_the_quote_names_it(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    restated = {"segment": "S0", "quote": "I could not sit still all day", "kind": "feeling",
                "text": "The owner felt anxious and enjoyed nothing all day."}  # fmt: skip
    scripted(
        providers,
        [restated, statement("I felt dread about the review", "feeling")],
        {
            "concepts": [
                concept("c1", "feeling", "anxiety"),  # Named only in the model's restatement.
                concept("c2", "feeling", "still"),  # A real word of the quote.
                concept("c3", "feeling", "read", cites="T2"),  # Inside "dread", not a word of it.
            ]
        },
    )
    process(user_id, providers, JOURNAL)
    assert node(db, "anxiety").status == "hypothesis"
    assert node(db, "still").status == "stated"
    assert (
        db.scalars(select(Node).where(Node.normalized_name == "read")).one().status == "hypothesis"
    )


def test_two_sources_matched_before_either_commits_share_their_concepts(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    scripted(
        providers,
        [statement("I felt dread about the review", "feeling")],
        {"concepts": [concept("c1", "feeling", "dread")]},
    )
    second = Fixture("second", "journal", "Second", JOURNAL.occurred_at, JOURNAL.turns, {})
    with user_session(user_id) as session:
        first_id = ingest(session, user_id, JOURNAL)
        second_id = ingest(session, user_id, second)
    # statements and concepts for both sources run before either commit.
    run_pipeline(providers)

    assert status_of(db, first_id) == status_of(db, second_id) == "ready"
    dread = db.scalars(select(Node).where(Node.normalized_name == "dread")).one()
    assert dread.evidence_count == 2


def test_a_reused_concept_that_has_gone_is_matched_again(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    scripted(
        providers,
        [statement("I felt dread about the review", "feeling")],
        {"concepts": [concept("c1", "feeling", "dread")]},
    )
    first_id = process(user_id, providers, JOURNAL)
    second = Fixture("second", "journal", "Second", JOURNAL.occurred_at, JOURNAL.turns, {})
    with user_session(user_id) as session:
        second_id = ingest(session, user_id, second)
    drain(HANDLERS, providers, get_settings(), limit=2)  # statements, concepts: matched to "dread"
    with user_session(user_id) as session:
        sources.retract(session, first_id)  # The matched node is deleted before the commit.
    run_pipeline(providers)

    assert status_of(db, second_id) == "ready"
    dread = db.scalars(select(Node).where(Node.normalized_name == "dread")).one()
    assert dread.evidence_count == 1


def test_a_job_that_keeps_outliving_its_lease_is_given_up(
    db: Session, user_id: uuid.UUID, providers: Providers
) -> None:
    source_id = add_journal(user_id, providers)
    assert queue.claim("worker-a", 900, max_attempts=3) is not None
    with user_session(user_id) as session:
        session.execute(update(Job).where(Job.source_id == source_id).values(attempts=3))

    assert queue.claim("worker-b", 0, max_attempts=3) is None
    job = db.scalars(select(Job).where(Job.source_id == source_id)).one()
    assert (job.status, job.error) == ("failed", "lease_expired_too_often")
    assert status_of(db, source_id) == "failed"


def test_attempts_are_counted_before_they_are_checked() -> None:
    limiter = RateLimiter(3)
    for _ in range(3):
        assert not limiter.blocked("client")
        limiter.record_attempt("client")
    assert limiter.blocked("client")  # Three guesses in flight already fill the limit.
    limiter.forgive("client")
    assert not limiter.blocked("client")
    assert not limiter.blocked("someone-else")
