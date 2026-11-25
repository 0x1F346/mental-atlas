# Mental Atlas

A personal atlas of the owner's mind, built from therapy recordings and writing.

- Specification: `docs/plan/IMPLEMENTATION_PLAN.md`
- Current state: `docs/PROGRESS.md`
- Decisions made after the plan: `docs/DECISIONS.md`

## Running it

Requires Docker, [uv](https://docs.astral.sh/uv/), Node 24 with pnpm, and ffmpeg.

    make install
    cp .env.example .env
    make dev        # Postgres, MinIO, API on :8000, worker, web on :5173
    make verify     # lint, types, tests, generated-file check

In development the seeded user is `owner@example.com` with the password `atlas-dev`, unless
`ATLAS_SEED_USER_PASSWORD` is set. Outside development, set a password with
`cd backend && uv run python -m atlas.cli set-password`.

Real recordings and transcripts never enter this repository. Local copies live in `data/`, which is git-ignored.
