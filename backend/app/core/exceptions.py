"""Domain exceptions raised by services, plus the single handler that maps
them to the one error shape used everywhere.

Services raise these. Routers never catch them; the handler registered in
main.py does the translation to HTTP.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base for every error a service can raise. Not used directly."""

    code = "INTERNAL_ERROR"
    status_code = 500
    message = "Something went wrong."

    def __init__(self, message: str | None = None, fields: dict | None = None):
        self.message = message or self.message
        self.fields = fields
        super().__init__(self.message)


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    status_code = 422
    message = "The request was invalid."


class InvalidCredentialsError(DomainError):
    code = "INVALID_CREDENTIALS"
    status_code = 401
    message = "Incorrect email or password."


class TokenInvalidError(DomainError):
    code = "TOKEN_INVALID"
    status_code = 401
    message = "Your session has expired. Log in again."


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404
    message = "Not found."


class FileTooLargeError(DomainError):
    code = "FILE_TOO_LARGE"
    status_code = 413
    message = "File exceeds the 5 MB limit."


class UnsupportedFileError(DomainError):
    code = "UNSUPPORTED_FILE"
    status_code = 415
    message = "Only PDF and DOCX files are supported."


class ExtractionFailedError(DomainError):
    code = "EXTRACTION_FAILED"
    status_code = 422
    message = (
        "No readable text was found in this file. It looks like a scanned "
        "image; upload a text-based PDF or DOCX instead."
    )


class PdfRenderError(DomainError):
    code = "PDF_RENDER_FAILED"
    status_code = 500
    message = "The PDF could not be generated. Try again."


class LLMUnavailableError(DomainError):
    code = "LLM_UNAVAILABLE"
    status_code = 503
    message = "Analysis failed. Try again."


class RateLimitedError(DomainError):
    code = "RATE_LIMITED"
    status_code = 429
    message = "You have hit the analysis limit. Try again later."


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    body: dict = {"error": {"code": exc.code, "message": exc.message}}
    if exc.fields:
        body["error"]["fields"] = exc.fields
    return JSONResponse(status_code=exc.status_code, content=body)


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic body/form failures otherwise come back as FastAPI's default
    {"detail": [...]} list, which the frontend cannot map to a message.
    Fold them into the same VALIDATION_ERROR shape with one line per field."""
    fields = {}
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query", "path")]
        fields[".".join(loc) or "body"] = err.get("msg", "invalid")
    body = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "The request was invalid.",
            "fields": fields,
        }
    }
    return JSONResponse(status_code=422, content=body)
