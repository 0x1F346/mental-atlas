.PHONY: dev infra api worker web test lint types generate generate-check migrate eval smoke verify install

BACKEND := backend
WEB := web

install:
	cd $(BACKEND) && uv sync
	cd $(WEB) && pnpm install

# Postgres and MinIO run in Docker; the API, worker and web app run on the host.
infra:
	docker compose up -d --wait

dev: infra migrate
	$(MAKE) -j3 api worker web

api:
	cd $(BACKEND) && uv run uvicorn atlas.api.app:app --reload --port 8000

worker:
	cd $(BACKEND) && uv run python -m atlas.worker

web:
	cd $(WEB) && pnpm dev

migrate:
	@echo "no migrations yet (M1-T3)"

generate:
	cd $(BACKEND) && uv run python ../ontology/generate.py

generate-check:
	cd $(BACKEND) && uv run python ../ontology/generate.py --check

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(WEB) && pnpm lint

types:
	cd $(BACKEND) && uv run mypy
	cd $(WEB) && pnpm typecheck

test:
	cd $(BACKEND) && uv run pytest
	cd $(WEB) && pnpm test

eval:
	@echo "no evaluation harness yet (M3-T2)"

verify: lint types test generate-check
