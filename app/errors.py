import json
import logging
import uuid
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ErrorMessages:
    NOT_FOUND = "Recurso nao encontrado"
    UNAUTHORIZED = "Token invalido ou expirado"
    FORBIDDEN = "Acesso negado"
    INSUFFICIENT_CREDITS = "Creditos insuficientes"
    EMAIL_NOT_VERIFIED = "Verifique seu email antes de continuar"
    RATE_LIMITED = "Muitas tentativas. Aguarde um momento."
    INVALID_INPUT = "Dados invalidos"
    SERVER_ERROR = "Erro interno. Tente novamente."
    DISK_FULL = "Servidor temporariamente indisponivel. Tente mais tarde."
    ARTIFACT_UNAVAILABLE = (
        "O arquivo deste video esta temporariamente indisponivel. "
        "Tente novamente; se persistir, informe o codigo da solicitacao ao suporte."
    )
    PAYLOAD_TOO_LARGE = "Payload muito grande"


def not_found_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorMessages.NOT_FOUND)


def artifact_unavailable_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=ErrorMessages.ARTIFACT_UNAVAILABLE,
    )


def invalid_input_error(detail: str = ErrorMessages.INVALID_INPUT) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def validate_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise invalid_input_error() from exc


def json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def build_validation_error_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part != "body"]
        field = ".".join(location) if location else "body"
        details.append(
            {
                "field": field,
                "message": error.get("msg", ErrorMessages.INVALID_INPUT),
            }
        )
    return details


async def request_validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": ErrorMessages.INVALID_INPUT,
            "errors": build_validation_error_details(exc),
        },
    )


async def pydantic_validation_exception_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": ErrorMessages.INVALID_INPUT,
            "errors": build_validation_error_details(RequestValidationError(exc.errors())),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": ErrorMessages.SERVER_ERROR},
    )
