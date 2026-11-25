.PHONY: eval-fake e2e dev infra api worker web test lint types generate generate-check migrate eval smoke verify install

BACKEND := backend
WEB := web

install:
	cd $(BACKEND) && uv sync
	cd $(WEB) && pnpm install

# Postgres and MinIO run in Docker; the API, worker and web app run on the host.
infra:
	docker compose up -d --wait

dev: infra migrate
	cd $(BACKEND) && uv run python -m atlas.cli dev-password
	$(MAKE) -j3 api worker web

api:
	cd $(BACKEND) && uv run uvicorn atlas.api.app:app --reload --port 8000

worker:
	cd $(BACKEND) && uv run python -m atlas.worker

web:
	cd $(WEB) && pnpm dev

migrate:
	cd $(BACKEND) && uv run alembic upgrade head

API_GENERATED := src/api/generated

generate:
	cd $(BACKEND) && uv run python ../ontology/generate.py
	cd $(BACKEND) && uv run python -m atlas.api.openapi ../$(WEB)/$(API_GENERATED)/openapi.json
	cd $(WEB) && pnpm exec openapi-typescript $(API_GENERATED)/openapi.json -o $(API_GENERATED)/schema.d.ts

# Regenerates into a scratch directory and fails if the committed files differ.
generate-check:
	cd $(BACKEND) && uv run python ../ontology/generate.py --check
	@tmp=$$(mktemp -d) && \
	(cd $(BACKEND) && uv run python -m atlas.api.openapi $$tmp/openapi.json) && \
	(cd $(WEB) && pnpm exec openapi-typescript $$tmp/openapi.json -o $$tmp/schema.d.ts > /dev/null) && \
	diff -q $$tmp/openapi.json $(WEB)/$(API_GENERATED)/openapi.json && \
	diff -q $$tmp/schema.d.ts $(WEB)/$(API_GENERATED)/schema.d.ts && \
	rm -rf $$tmp || (echo "stale generated API client: run make generate" && exit 1)

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(WEB) && pnpm lint

types:
	cd $(BACKEND) && uv run mypy
	cd $(WEB) && pnpm typecheck

test:
	cd $(BACKEND) && uv run pytest
	cd $(WEB) && pnpm test

# Browser test against the local stack with fake providers. Starts the stack if it is not running.
e2e:
	cd $(WEB) && pnpm e2e

# Live extraction scorecard. Calls the paid model: ask the owner first.
eval:
	cd $(BACKEND) && uv run python ../evals/run_eval.py --providers live

# The same scorecard with each fixture's expected output replayed. No outside call.
eval-fake:
	cd $(BACKEND) && uv run python ../evals/run_eval.py --providers oracle --no-history

verify: lint types test generate-check
