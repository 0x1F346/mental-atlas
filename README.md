# Mental Atlas

A personal atlas of the owner's mind, built from therapy recordings and writing. V1 takes one source through upload, transcription, extraction and placement on a map of six life areas, with every item traceable to the quotes behind it.

- Specification: `docs/plan/IMPLEMENTATION_PLAN.md` (text of `IMPLEMENTATION_PLAN.pdf`, which is authoritative)
- Current state and what needs the owner: `docs/PROGRESS.md`
- Decisions made after the plan: `docs/DECISIONS.md`
- Vocabulary: `ontology/atlas.yaml`, readable copy in `docs/ONTOLOGY.md`

## Running it

Requires Docker, [uv](https://docs.astral.sh/uv/), Node 24 with pnpm, and ffmpeg.

    make install
    make dev        # Postgres, MinIO, migrations, API on :8000, worker, web on :5173

Open http://localhost:5173. In development the seeded user is `owner@example.com` with the password `atlas-dev`, unless `ATLAS_SEED_USER_PASSWORD` is set. Outside development, set a password with `cd backend && uv run python -m atlas.cli set-password`.

With no configuration the app uses fake providers: no outside call is made, the transcriber returns a fixed invented dialogue, and extraction is a keyword stand-in. That is enough to try every screen. To use real providers, copy `.env.example` to a local env file, set `ATLAS_PROVIDERS=live` and the keys, and read "Before real data" below.

## Commands

| Command | What it does |
| --- | --- |
| `make verify` | Lint, types, tests and the generated-file check. Must pass before every commit. |
| `make e2e` | Browser tests against the local stack with fake providers. |
| `make generate` | Regenerate code from the vocabulary and the API schema. |
| `make migrate` | Apply database migrations. |
| `make eval-fake` | The extraction scorecard with each fixture's expected output replayed. No outside call. |
| `make eval` | The extraction scorecard against the live model. Costs money. |
| `make smoke` | One live call per provider adapter, using invented material. Costs money. |
| `make backup`, `make restore-check` | Dump the local database; confirm the newest dump restores. |
| `make bucket-versioning` | Turn on object versioning for the storage bucket. |

## Layout

- `backend/atlas/api`: routes, sign-in, request and response schemas
- `backend/atlas/domain`: generated vocabulary, commit-time rules
- `backend/atlas/db`: table models, user-scoped sessions, retraction and recompute
- `backend/atlas/pipeline`: stages, validators, prompts
- `backend/atlas/providers`: transcriber, extraction model, embedder, blob store, fakes
- `backend/atlas/graph`: GraphStore, map geometry and layout
- `backend/atlas/evaluation`: fixture loader, scorecard
- `web/src`: map, sources, generated API client
- `evals`: synthetic fixtures and the scorecard runner

## Before real data

Real recordings and transcripts never enter this repository. Local copies live in `data/`, which is git-ignored and which Claude Code is denied from reading.

Before uploading a real session:

1. Run `make smoke` and `make eval`, and check the scorecard meets its targets. No prompt or adapter has been run against a live service yet.
2. Confirm retention settings with ElevenLabs, Anthropic and the embedding provider.
3. Choose an embedding provider and set the `ATLAS_EMBEDDING_*` variables.
4. Set a real password, and `ATLAS_COOKIE_SECURE=true` if the app is served over HTTPS.
5. Run `make bucket-versioning`, schedule `make backup`, and run `make restore-check` once.

Before hosting on the public internet, also add a second sign-in factor (not built in V1).
