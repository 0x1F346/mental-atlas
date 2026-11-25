"""Mark system nodes explicitly, and stop reclaiming a job that keeps killing its worker.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

APP_ROLE = "atlas_app"


def upgrade() -> None:
    # Until now a node with no run was taken to be one the system created (the owner's
    # Person node, the therapist). Deleting a source also clears run ids, so that test
    # could turn an ordinary node into a permanent one. The flag says it outright.
    op.execute("ALTER TABLE nodes ADD COLUMN is_system boolean NOT NULL DEFAULT false")
    op.execute("UPDATE nodes SET is_system = true WHERE run_id IS NULL")

    # A job whose lease expires is claimed again, but only up to a number of attempts;
    # after that it is marked failed, with its source, instead of being retried forever.
    op.execute("DROP FUNCTION atlas_claim_job(text, integer)")
    op.execute(
        f"""
        CREATE FUNCTION atlas_claim_job(p_worker text, p_lease_seconds integer, p_max_attempts integer)
        RETURNS TABLE (job_id uuid, user_id uuid)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
        BEGIN
            WITH abandoned AS (
                UPDATE jobs SET status = 'failed', error = 'lease_expired_too_often',
                                locked_at = NULL, locked_by = NULL
                WHERE jobs.status = 'running'
                  AND jobs.locked_at < now() - make_interval(secs => p_lease_seconds)
                  AND jobs.attempts >= p_max_attempts
                RETURNING jobs.source_id
            )
            UPDATE sources SET status = 'failed' WHERE id IN (SELECT source_id FROM abandoned);

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
        REVOKE ALL ON FUNCTION atlas_claim_job(text, integer, integer) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION atlas_claim_job(text, integer, integer) TO {APP_ROLE};
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION atlas_claim_job(text, integer, integer)")
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
        REVOKE ALL ON FUNCTION atlas_claim_job(text, integer) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION atlas_claim_job(text, integer) TO {APP_ROLE};
        """
    )
    op.execute("ALTER TABLE nodes DROP COLUMN is_system")
