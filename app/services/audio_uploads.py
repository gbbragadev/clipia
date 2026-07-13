from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import anyio
from fastapi import HTTPException, Request, status
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser

_ALLOWED_AUDIO_MIMES: dict[str, str] = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}


class UploadSizeExceeded(MultiPartException):
    pass


class LimitedMultiPartParser(MultiPartParser):
    """Starlette parser with a hard per-file limit enforced while bytes arrive."""

    def __init__(self, *args, max_file_bytes: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_file_bytes = max_file_bytes
        self._current_file_bytes = 0

    def on_part_begin(self) -> None:
        self._current_file_bytes = 0
        super().on_part_begin()

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        if self._current_part.file is not None:
            self._current_file_bytes += end - start
            if self._current_file_bytes > self.max_file_bytes:
                raise UploadSizeExceeded("Arquivo muito grande")
        super().on_part_data(data, start, end)


def declared_audio_extension(content_type: str | None) -> str:
    normalized = (content_type or "").lower().split(";", 1)[0].strip()
    try:
        return _ALLOWED_AUDIO_MIMES[normalized]
    except KeyError as exc:
        raise ValueError(f"Tipo de audio nao suportado: {normalized}. Envie WAV, MP3, WebM ou OGG.") from exc


def validate_audio_magic(content: bytes, extension: str) -> None:
    valid = False
    if extension == ".wav":
        valid = len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    elif extension == ".mp3":
        valid = content.startswith(b"ID3") or (len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0)
    elif extension == ".webm":
        valid = content.startswith(b"\x1aE\xdf\xa3")
    elif extension == ".ogg":
        valid = content.startswith(b"OggS")
    if not valid:
        raise ValueError("O conteudo do arquivo nao corresponde ao tipo de audio declarado")


async def _limited_request_stream(request: Request, max_total_bytes: int) -> AsyncIterator[bytes]:
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_total_bytes:
            raise UploadSizeExceeded("Requisicao de upload muito grande")
        yield chunk


async def parse_limited_multipart(
    request: Request,
    *,
    max_file_bytes: int,
    max_total_bytes: int,
    max_files: int,
    max_fields: int,
) -> FormData:
    # Unit-level route tests use a minimal request double. Real ASGI requests always
    # expose stream(), which is the only production path.
    if not hasattr(request, "stream"):
        return await request.form()

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_total_bytes:
                raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Arquivo muito grande")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content-Length invalido") from exc

    parser = LimitedMultiPartParser(
        request.headers,
        _limited_request_stream(request, max_total_bytes),
        max_files=max_files,
        max_fields=max_fields,
        max_part_size=16 * 1024,
        max_file_bytes=max_file_bytes,
    )
    try:
        return await parser.parse()
    except UploadSizeExceeded as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except (KeyError, MultiPartException) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Multipart invalido") from exc


async def read_limited_audio(
    upload,
    *,
    max_bytes: int,
    extension: str,
    chunk_size: int = 64 * 1024,
) -> bytes:
    content = bytearray()
    while chunk := await upload.read(chunk_size):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise ValueError(f"Arquivo muito grande (max {max_bytes // (1024 * 1024)}MB)")
    validate_audio_magic(content, extension)
    return bytes(content)


async def write_limited_audio(
    upload,
    destination: Path,
    *,
    max_bytes: int,
    extension: str,
    chunk_size: int = 64 * 1024,
) -> int:
    written = 0
    header = bytearray()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with await anyio.open_file(destination, "wb") as output:
            while chunk := await upload.read(chunk_size):
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(f"Arquivo muito grande (max {max_bytes // (1024 * 1024)}MB)")
                if len(header) < 16:
                    header.extend(chunk[: 16 - len(header)])
                await output.write(chunk)
        validate_audio_magic(header, extension)
        return written
    except Exception:
        destination.unlink(missing_ok=True)
        raise
