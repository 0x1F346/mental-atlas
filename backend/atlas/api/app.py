"""FastAPI application factory. All routes sit under /api/v1."""

from fastapi import APIRouter, FastAPI

API_PREFIX = "/api/v1"

health_router = APIRouter()


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(title="Mental Atlas", version="0.1.0", openapi_url=f"{API_PREFIX}/openapi.json")
    app.include_router(health_router, prefix=API_PREFIX, tags=["health"])
    return app


app = create_app()
