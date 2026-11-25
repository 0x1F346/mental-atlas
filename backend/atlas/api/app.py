"""FastAPI application factory. All routes sit under /api/v1."""

from fastapi import APIRouter, FastAPI

from atlas.api.errors import ErrorResponse, install_error_handlers
from atlas.api.routes import auth, sources

API_PREFIX = "/api/v1"

health_router = APIRouter()


@health_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mental Atlas",
        version="0.1.0",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        responses={"4XX": {"model": ErrorResponse}},
    )
    install_error_handlers(app)
    app.include_router(health_router, prefix=API_PREFIX, tags=["health"])
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(sources.router, prefix=API_PREFIX)
    return app


app = create_app()
