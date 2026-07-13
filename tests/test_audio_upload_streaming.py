from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.services.audio_uploads import (
    parse_limited_multipart,
    read_limited_audio,
    validate_audio_magic,
)


class ChunkedUpload:
    def __init__(self, content: bytes, chunk_size: int = 4):
        self.content = content
        self.chunk_size = chunk_size
        self.offset = 0
        self.read_calls = 0

    async def read(self, _size: int = -1) -> bytes:
        self.read_calls += 1
        chunk = self.content[self.offset : self.offset + self.chunk_size]
        self.offset += len(chunk)
        return chunk


@pytest.mark.parametrize(
    ("extension", "content"),
    [
        (".wav", b"RIFF\x10\x00\x00\x00WAVEfmt "),
        (".mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00"),
        (".webm", b"\x1aE\xdf\xa3\x9fB\x86\x81"),
        (".ogg", b"OggS\x00\x02\x00\x00"),
    ],
)
def test_audio_magic_matches_declared_format(extension, content):
    validate_audio_magic(content, extension)


def test_audio_magic_rejects_executable_disguised_as_wav():
    with pytest.raises(ValueError, match="conteudo"):
        validate_audio_magic(b"MZ\x90\x00not-a-wave", ".wav")


@pytest.mark.asyncio
async def test_limited_audio_reader_stops_after_the_limit():
    upload = ChunkedUpload(b"RIFF\x10\x00\x00\x00WAVE" + b"x" * 100)

    with pytest.raises(ValueError, match="grande"):
        await read_limited_audio(upload, max_bytes=16, extension=".wav", chunk_size=4)

    assert upload.offset < len(upload.content)


@pytest.mark.asyncio
async def test_multipart_parser_rejects_chunked_file_before_consuming_the_tail():
    boundary = "clipia-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + b"RIFF\x10\x00\x00\x00WAVE"
        + b"x" * 128
        + f"\r\n--{boundary}--\r\n".encode()
    )
    chunks = [body[index : index + 8] for index in range(0, len(body), 8)]
    calls = 0

    async def receive():
        nonlocal calls
        chunk = chunks[calls]
        calls += 1
        return {"type": "http.request", "body": chunk, "more_body": calls < len(chunks)}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/upload",
            "headers": [(b"content-type", f"multipart/form-data; boundary={boundary}".encode())],
        },
        receive,
    )

    with pytest.raises(HTTPException) as exc:
        await parse_limited_multipart(
            request,
            max_file_bytes=16,
            max_total_bytes=len(body) + 1,
            max_files=1,
            max_fields=1,
        )

    assert exc.value.status_code == 413
    assert calls < len(chunks)
