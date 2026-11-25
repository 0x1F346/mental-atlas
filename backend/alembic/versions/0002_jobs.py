"""Job queue, and per-word timings on segments.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "atlas_app"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE jobs (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            stage text NOT NULL,
            status text NOT NULL DEFAULT 'queued',
            attempts integer NOT NULL DEFAULT 0,
            run_after timestamptz NOT NULL DEFAULT now(),
            locked_at timestamptz,
            locked_by text,
            payload jsonb NOT NULL DEFAULT '{}',
            error text,
            CONSTRAINT ck_jobs_status CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_jobs_ready ON jobs (run_after) WHERE status IN ('queued', 'running')"
    )
    op.execute("CREATE INDEX ix_jobs_source ON jobs (source_id)")
    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY jobs_owner ON jobs USING (user_id = atlas_current_user_id()) "
        "WITH CHECK (user_id = atlas_current_user_id())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO {APP_ROLE}")

    # The worker serves every user, so claiming runs as the owner. It hands back one job
    # and its user; all further work happens in a session scoped to that user.
    # A running job whose lease has expired belonged to a worker that died, and is claimed again.
    op.execute(
        f"""
        CREATE FUNCTION atlas_claim_job(p_worker text, p_lease_seconds integer)
        RETURNS TABLE (job_id uuid, user_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        BEGIN
            RETURN QUERY
            UPDATE jobs SET status = 'running', locked_at = now(), locked_by = p_worker,
                            attempts = jobs.attempts + 1
            WHERE jobs.id = (
                SELECT j.id FROM jobs j
                WHERE (j.status = 'queued' AND j.run_after <= now())
                   OR (j.status = 'running'
                       AND j.locked_at < now() - make_interval(secs => p_lease_seconds))
                ORDER BY j.run_after, j.id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING jobs.id, jobs.user_id;
        END;
        $$;

        -- A worker that restarts gives back whatever it was holding when it stopped.
        CREATE FUNCTION atlas_release_jobs(p_worker text) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        DECLARE released integer;
        BEGIN
            UPDATE jobs SET status = 'queued', locked_at = NULL, locked_by = NULL, run_after = now()
            WHERE status = 'running' AND locked_by = p_worker;
            GET DIAGNOSTICS released = ROW_COUNT;
            RETURN released;
        END;
        $$;

        REVOKE ALL ON FUNCTION atlas_claim_job(text, integer) FROM PUBLIC;
        REVOKE ALL ON FUNCTION atlas_release_jobs(text) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION atlas_claim_job(text, integer) TO {APP_ROLE};
        GRANT EXECUTE ON FUNCTION atlas_release_jobs(text) TO {APP_ROLE};
        """
    )
    op.execute("ALTER TABLE segments ADD COLUMN words jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE segments DROP COLUMN words")
    op.execute("DROP FUNCTION atlas_release_jobs(text)")
    op.execute("DROP FUNCTION atlas_claim_job(text, integer)")
    op.execute("DROP TABLE jobs")
