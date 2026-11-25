"""Initial schema: four layers, run log, accounts, row-level security, seed data.

Revision ID: 0001
Revises:
"""

import math
import os

from alembic import op
from sqlalchemy import text

from atlas.db.generated.constraints import CHECK_CONSTRAINTS, EDGE_ENDPOINT_FUNCTION_SQL
from atlas.db.ids import new_id

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "atlas_app"

COMMON = """
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now()"""

TABLES: dict[str, str] = {
    "users": """
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED,
    created_at timestamptz NOT NULL DEFAULT now(),
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    CONSTRAINT ck_users_self CHECK (user_id = id)""",
    "sessions": COMMON
    + """,
    token_hash text NOT NULL UNIQUE,
    csrf_token text NOT NULL,
    expires_at timestamptz NOT NULL""",
    "sources": COMMON
    + """,
    kind text NOT NULL,
    title text NOT NULL,
    occurred_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'uploaded',
    language text,
    metadata jsonb NOT NULL DEFAULT '{}'""",
    "runs": COMMON
    + """,
    source_id uuid REFERENCES sources(id) ON DELETE CASCADE,
    kind text NOT NULL,
    pipeline_version integer NOT NULL,
    prompt_version text,
    schema_version integer,
    model text,
    status text NOT NULL DEFAULT 'running',
    raw_output jsonb,
    usage jsonb,
    error text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CONSTRAINT ck_runs_status CHECK (status IN ('running', 'succeeded', 'failed', 'retracted'))""",
    "life_areas": COMMON
    + """,
    key text NOT NULL,
    name text NOT NULL,
    position integer NOT NULL,
    anchor_x double precision NOT NULL,
    anchor_y double precision NOT NULL,
    CONSTRAINT uq_life_areas_key UNIQUE (user_id, key)""",
    "nodes": COMMON
    + """,
    type text NOT NULL,
    name text NOT NULL,
    normalized_name text NOT NULL,
    description text,
    kind text,
    attributes jsonb NOT NULL DEFAULT '{}',
    life_area_id uuid REFERENCES life_areas(id) ON DELETE SET NULL,
    life_area_weights jsonb NOT NULL DEFAULT '{}',
    noticed_by text[] NOT NULL DEFAULT '{}',
    status text NOT NULL,
    first_seen_at timestamptz,
    last_seen_at timestamptz,
    evidence_count integer NOT NULL DEFAULT 0,
    confidence double precision,
    state text NOT NULL DEFAULT 'active',
    merged_into_id uuid REFERENCES nodes(id) ON DELETE SET NULL,
    schema_version integer NOT NULL,
    run_id uuid REFERENCES runs(id) ON DELETE SET NULL,
    embedding vector,
    embedding_model text,
    embedding_dimension integer,
    -- The AI never creates a diagnosis: an active diagnosis can never rest on inference alone.
    CONSTRAINT ck_nodes_no_hypothesised_diagnosis CHECK (
        NOT (type = 'trait' AND kind = 'diagnosis' AND status = 'hypothesis' AND state = 'active')
    )""",
    "media_files": COMMON
    + """,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    storage_key text NOT NULL,
    mime_type text NOT NULL,
    bytes bigint,
    duration_ms integer,
    sha256 text,
    role text NOT NULL,
    CONSTRAINT ck_media_files_role CHECK (role IN ('original', 'audio'))""",
    "transcripts": COMMON
    + """,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    provider text NOT NULL,
    model text NOT NULL,
    raw_response_key text,
    pipeline_version integer NOT NULL,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE""",
    "speakers": COMMON
    + """,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    provider_label text NOT NULL,
    role text,
    person_node_id uuid REFERENCES nodes(id) ON DELETE SET NULL,
    method text,
    confidence double precision,
    CONSTRAINT uq_speakers_label UNIQUE (source_id, provider_label)""",
    "segments": COMMON
    + """,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    speaker_id uuid NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
    idx integer NOT NULL,
    start_ms integer,
    end_ms integer,
    start_char integer NOT NULL,
    end_char integer NOT NULL,
    text text NOT NULL,
    CONSTRAINT uq_segments_idx UNIQUE (source_id, idx)""",
    "statements": COMMON
    + """,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    segment_id uuid NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    speaker_role text NOT NULL,
    quote text NOT NULL,
    quote_start_char integer NOT NULL,
    quote_end_char integer NOT NULL,
    start_ms integer,
    end_ms integer,
    text text NOT NULL,
    kind text NOT NULL,
    said_at timestamptz NOT NULL,
    about_time_text text,
    about_from date,
    about_to date,
    confidence double precision,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    embedding vector,
    embedding_model text,
    embedding_dimension integer""",
    "node_aliases": COMMON
    + """,
    node_id uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    alias text NOT NULL,
    normalized_alias text NOT NULL,
    run_id uuid REFERENCES runs(id) ON DELETE SET NULL,
    CONSTRAINT uq_node_aliases UNIQUE (node_id, normalized_alias)""",
    "edges": COMMON
    + """,
    type text NOT NULL,
    from_node_id uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    to_node_id uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    context_event_id uuid REFERENCES nodes(id) ON DELETE SET NULL,
    attributes jsonb NOT NULL DEFAULT '{}',
    noticed_by text[] NOT NULL DEFAULT '{}',
    status text NOT NULL,
    valid_from date,
    valid_to date,
    first_seen_at timestamptz,
    last_seen_at timestamptz,
    evidence_count integer NOT NULL DEFAULT 0,
    confidence double precision,
    state text NOT NULL DEFAULT 'active',
    run_id uuid REFERENCES runs(id) ON DELETE SET NULL""",
    "evidence": COMMON
    + """,
    statement_id uuid NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    target_kind text NOT NULL,
    target_id uuid NOT NULL,
    stance text NOT NULL,
    basis text NOT NULL,
    confidence double precision,
    life_area_weights jsonb,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    CONSTRAINT ck_evidence_target_kind CHECK (target_kind IN ('node', 'edge')),
    CONSTRAINT uq_evidence UNIQUE (statement_id, target_kind, target_id, stance)""",
    "resolution_decisions": COMMON
    + """,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    proposed jsonb NOT NULL,
    candidate_ids uuid[] NOT NULL DEFAULT '{}',
    decision text NOT NULL,
    matched_node_id uuid REFERENCES nodes(id) ON DELETE SET NULL,
    reason text""",
    "map_layouts": COMMON
    + """,
    version integer NOT NULL,
    parameters jsonb NOT NULL,
    CONSTRAINT uq_map_layouts_version UNIQUE (user_id, version)""",
    "map_positions": COMMON
    + """,
    node_id uuid NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    layout_id uuid NOT NULL REFERENCES map_layouts(id) ON DELETE CASCADE,
    x double precision NOT NULL,
    y double precision NOT NULL,
    placed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_map_positions UNIQUE (layout_id, node_id)""",
}

INDEXES = [
    "CREATE INDEX ix_sessions_user ON sessions (user_id)",
    "CREATE INDEX ix_runs_source ON runs (source_id, kind)",
    "CREATE UNIQUE INDEX uq_media_original_hash ON media_files (user_id, sha256) WHERE role = 'original'",
    "CREATE INDEX ix_media_files_source ON media_files (source_id)",
    "CREATE INDEX ix_segments_source ON segments (source_id, idx)",
    "CREATE INDEX ix_statements_source ON statements (source_id)",
    "CREATE INDEX ix_statements_run ON statements (run_id)",
    "CREATE INDEX ix_nodes_lookup ON nodes (user_id, type, normalized_name)",
    "CREATE INDEX ix_nodes_run ON nodes (run_id)",
    # Exactly one Person node per user is the owner.
    "CREATE UNIQUE INDEX uq_nodes_self ON nodes (user_id) "
    "WHERE type = 'person' AND attributes ->> 'is_self' = 'true' AND state = 'active'",
    "CREATE INDEX ix_node_aliases_lookup ON node_aliases (user_id, normalized_alias)",
    "CREATE INDEX ix_edges_from ON edges (from_node_id)",
    "CREATE INDEX ix_edges_to ON edges (to_node_id)",
    "CREATE INDEX ix_edges_run ON edges (run_id)",
    "CREATE UNIQUE INDEX uq_edges_active ON edges (user_id, type, from_node_id, to_node_id, "
    "COALESCE(context_event_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE state = 'active'",
    "CREATE INDEX ix_evidence_target ON evidence (target_kind, target_id)",
    "CREATE INDEX ix_evidence_run ON evidence (run_id)",
    "CREATE INDEX ix_evidence_statement ON evidence (statement_id)",
    "CREATE INDEX ix_resolution_decisions_run ON resolution_decisions (run_id)",
    "CREATE INDEX ix_map_positions_node ON map_positions (node_id)",
]

FUNCTIONS = f"""
-- The user for the current transaction, set by atlas.db.session with set_config().
CREATE FUNCTION atlas_current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('atlas.user_id', true), '')::uuid
$$;

-- Sign-in happens before any user is set, so these two lookups run as the owner.
-- They return one row for an exact match and nothing else.
CREATE FUNCTION atlas_login_lookup(p_email text)
RETURNS TABLE (user_id uuid, password_hash text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT u.id, u.password_hash FROM users u WHERE u.email = lower(p_email)
$$;

CREATE FUNCTION atlas_session_lookup(p_token_hash text)
RETURNS TABLE (session_id uuid, user_id uuid, csrf_token text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT s.id, s.user_id, s.csrf_token FROM sessions s
    WHERE s.token_hash = p_token_hash AND s.expires_at > now()
$$;

REVOKE ALL ON FUNCTION atlas_login_lookup(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION atlas_session_lookup(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION atlas_login_lookup(text) TO {APP_ROLE};
GRANT EXECUTE ON FUNCTION atlas_session_lookup(text) TO {APP_ROLE};
"""

LIFE_AREAS = [
    ("love", "Love"),
    ("family", "Family"),
    ("friendships", "Friendships"),
    ("work", "Work"),
    ("body_health", "Body and health"),
    ("self", "Self"),
]


def life_area_anchor(position: int) -> tuple[float, float]:
    """Self sits at the centre; the other five are wedge centres, clockwise from the top."""
    if position == 5:
        return 500.0, 500.0
    angle = math.radians(-90 + 36 + 72 * position)
    return round(500 + 330 * math.cos(angle), 3), round(500 + 330 * math.sin(angle), 3)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS;
            END IF;
        END $$"""
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    for name, body in TABLES.items():
        op.execute(f"CREATE TABLE {name} ({body}\n)")
    for table, constraints in CHECK_CONSTRAINTS.items():
        for name, sql in constraints.items():
            op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({sql})")
    for statement in INDEXES:
        op.execute(statement)

    op.execute(EDGE_ENDPOINT_FUNCTION_SQL)
    op.execute(
        "CREATE TRIGGER trg_edges_endpoints BEFORE INSERT OR UPDATE OF type, from_node_id, to_node_id "
        "ON edges FOR EACH ROW EXECUTE FUNCTION atlas_check_edge_endpoints()"
    )
    op.execute(FUNCTIONS)

    # Row-level security: every table, in the migration that creates it.
    for name in TABLES:
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {name}_owner ON {name} "
            "USING (user_id = atlas_current_user_id()) "
            "WITH CHECK (user_id = atlas_current_user_id())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name} TO {APP_ROLE}")

    seed()


def seed() -> None:
    """One user, their six life areas and their own Person node.

    The password hash is unusable until `python -m atlas.cli set-password` is run.
    """
    connection = op.get_bind()
    email = os.environ.get("ATLAS_SEED_USER_EMAIL", "owner@example.com").lower()
    user_id = new_id()
    connection.execute(
        text(
            "INSERT INTO users (id, user_id, email, password_hash) VALUES (:id, :id, :email, '!')"
        ),
        {"id": user_id, "email": email},
    )
    self_area_id = None
    for position, (key, name) in enumerate(LIFE_AREAS):
        area_id = new_id()
        x, y = life_area_anchor(position)
        connection.execute(
            text(
                "INSERT INTO life_areas (id, user_id, key, name, position, anchor_x, anchor_y) "
                "VALUES (:id, :user_id, :key, :name, :position, :x, :y)"
            ),
            {
                "id": area_id,
                "user_id": user_id,
                "key": key,
                "name": name,
                "position": position,
                "x": x,
                "y": y,
            },
        )
        if key == "self":
            self_area_id = area_id
    connection.execute(
        text(
            "INSERT INTO nodes (id, user_id, type, name, normalized_name, description, attributes, "
            "life_area_id, life_area_weights, noticed_by, status, schema_version) "
            "VALUES (:id, :user_id, 'person', 'Me', 'me', 'The owner of this atlas.', "
            "'{\"is_self\": true}', :area, '{\"self\": 1.0}', '{self}', 'stated', 1)"
        ),
        {"id": new_id(), "user_id": user_id, "area": self_area_id},
    )


def downgrade() -> None:
    for name in reversed(list(TABLES)):
        op.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS atlas_check_edge_endpoints() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS atlas_login_lookup(text)")
    op.execute("DROP FUNCTION IF EXISTS atlas_session_lookup(text)")
    op.execute("DROP FUNCTION IF EXISTS atlas_current_user_id()")
