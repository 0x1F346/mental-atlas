"""API errors: a code and a message, never content (design rule 9)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from atlas.logging import get_logger

log = get_logger("atlas.api")


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


def _response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, error: ApiError) -> JSONResponse:
        return _response(error.status_code, error.code, error.message)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed"}
        code = codes.get(error.status_code, "http_error")
        return _response(error.status_code, code, code.replace("_", " ").capitalize() + ".")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        # Name the fields at fault but never echo what was sent: it may be transcript text.
        fields = sorted({".".join(str(part) for part in e["loc"][1:]) for e in error.errors()})
        listed = ", ".join(field for field in fields if field) or "body"
        return _response(422, "invalid_request", f"Invalid or missing fields: {listed}.")

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        log.error("api.unhandled", error=error, method=request.method)
        return _response(500, "internal_error", "Something went wrong.")
