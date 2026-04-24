# Fase B — gpt-image-2 + Novelinha Histórica — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir Pexels por imagens geradas via `gpt-image-2` no novo template `novelinha_historica`, com Ken Burns via FFmpeg zoompan e validação de 3 vídeos end-to-end.

**Architecture:** Nova task Celery `task_generate_images` entre `generate_script` e `synthesize_audio`. Provider `OpenAIImageProvider` com cache SHA-256 e retry exponencial. Template novo com `MediaStrategy.source="ai_image"` e ScriptWriter expandido para pedir `visual_hint` por cena ao Claude. Compositor rota estática via `_prepare_static_image` usando `-loop 1` + `zoompan`.

**Tech Stack:** Python 3.12, Celery (solo pool), OpenAI Python SDK, Anthropic SDK, FFmpeg, pytest.

**Spec:** `docs/superpowers/specs/2026-04-23-phase-b-gpt-image-2-design.md`

---

## File Structure

**Novos arquivos:**
- `app/services/image_provider.py` — cliente gpt-image-2, cache, retry
- `tests/test_image_provider.py` — TDD do provider
- `tests/test_tasks_generate_images.py` — TDD da task Celery
- `tests/test_compositor_ken_burns.py` — TDD do router + `_prepare_static_image`
- `tests/test_scriptwriter_visual_hint.py` — TDD da expansão do scriptwriter
- `scripts/test-phase-b-smoke.py` — smoke test end-to-end
- `docs/reports/phase-b-validation.md` — relatório das 3 rodadas de validação

**Arquivos modificados:**
- `app/config.py` — nova env var `GPT_IMAGE_QUALITY`
- `app/templates.py` — expansão `MediaStrategy`, `ScriptConfig`, novo template
- `app/services/scriptwriter.py` — injeção + validação de `visual_hint`
- `app/worker/tasks.py` — nova task, chain, early return em `task_fetch_media`
- `app/services/compositor.py` — refactor `_prepare_scene`, novo `_prepare_static_image`
- `.env.example` — documentar `GPT_IMAGE_QUALITY`
- `tests/conftest.py` — fixture `tiny_png_b64` compartilhada

---

## Task 1: Config — `GPT_IMAGE_QUALITY`

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Adicionar setting em `app/config.py`**

Após a linha `OPENAI_WHISPER_MODEL: str = "whisper-1"` (linha ~53), adicionar:

```python
    # GPT Image 2
    GPT_IMAGE_QUALITY: str = "medium"  # "low" | "medium" | "high"
```

- [ ] **Step 2: Documentar no `.env.example`**

Adicionar ao final do arquivo (ou na seção OpenAI, se existir):

```
# GPT Image 2 quality (low=$0.005/img, medium=$0.041/img, high=$0.165/img at 1024x1536)
GPT_IMAGE_QUALITY=medium
```

- [ ] **Step 3: Verificar import funciona**

Run: `python -c "from app.config import settings; print(settings.GPT_IMAGE_QUALITY)"`
Expected: `medium`

- [ ] **Step 4: Commit**

```bash
git add app/config.py .env.example
git commit -m "feat(config): add GPT_IMAGE_QUALITY setting for Phase B"
```

---

## Task 2: Scaffold `image_provider.py` com classes de erro

**Files:**
- Create: `app/services/image_provider.py`
- Create: `tests/test_image_provider.py`

- [ ] **Step 1: Escrever teste falhando**

Criar `tests/test_image_provider.py`:

```python
import pytest

from app.services.image_provider import (
    ImageProviderError,
    ModerationBlockedError,
    OpenAIImageProvider,
)


def test_error_classes_exist_and_are_exceptions():
    assert issubclass(ModerationBlockedError, Exception)
    assert issubclass(ImageProviderError, Exception)


def test_provider_can_be_instantiated_with_defaults(tmp_path):
    provider = OpenAIImageProvider(
        api_key="sk-test",
        cache_dir=tmp_path / "cache",
    )
    assert provider.model == "gpt-image-2"
    assert provider.quality == "medium"
    assert provider.size == "1024x1536"
    assert provider.moderation == "low"
    assert provider.max_retries == 3
```

- [ ] **Step 2: Rodar teste — deve falhar com ImportError**

Run: `pytest tests/test_image_provider.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.image_provider'`

- [ ] **Step 3: Criar skeleton**

Criar `app/services/image_provider.py`:

```python
"""OpenAI gpt-image-2 provider with SHA-256 cache and retry policy."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ModerationBlockedError(Exception):
    """Raised when OpenAI content moderation blocks the prompt."""


class ImageProviderError(Exception):
    """Raised after retries are exhausted on transient failures."""


class OpenAIImageProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-image-2",
        quality: str | None = None,
        size: str = "1024x1536",
        moderation: str = "low",
        cache_dir: Path | None = None,
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.quality = quality or settings.GPT_IMAGE_QUALITY
        self.size = size
        self.moderation = moderation
        self.cache_dir = cache_dir or (settings.STORAGE_DIR / "image-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    def generate(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError("implemented in Task 3")
```

- [ ] **Step 4: Rodar teste — deve passar**

Run: `pytest tests/test_image_provider.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/image_provider.py tests/test_image_provider.py
git commit -m "feat(image_provider): scaffold OpenAIImageProvider with error classes"
```

---

## Task 3: `generate()` — caminho básico (API call + write)

**Files:**
- Modify: `app/services/image_provider.py`
- Modify: `tests/test_image_provider.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Adicionar fixture compartilhada `tiny_png_b64`**

Abrir `tests/conftest.py` e adicionar no final:

```python
import base64

import pytest


@pytest.fixture
def tiny_png_b64() -> str:
    """Minimal valid PNG bytes, base64-encoded — for mocking image API responses."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\xc4[\x8d\x9a"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return base64.b64encode(png_bytes).decode()
```

(Se conftest já tem `import pytest`, não dupliquem; se tem `import base64`, idem.)

- [ ] **Step 2: Escrever teste falhando**

Adicionar em `tests/test_image_provider.py`:

```python
from unittest.mock import MagicMock, patch


def test_generate_writes_png_to_output_path(tmp_path, tiny_png_b64):
    output = tmp_path / "scene_1.png"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        mock_openai.return_value.images.generate.return_value = mock_response
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "cache")
        result = provider.generate("retrato sepia de 1912", output)

    assert result == output
    assert output.exists()
    assert output.read_bytes().startswith(b"\x89PNG")


def test_generate_calls_api_with_correct_params(tmp_path, tiny_png_b64):
    output = tmp_path / "scene_1.png"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.return_value = mock_response
        provider = OpenAIImageProvider(
            api_key="sk-test",
            quality="medium",
            size="1024x1536",
            cache_dir=tmp_path / "cache",
        )
        provider.generate("prompt", output)

    gen_mock.assert_called_once()
    kwargs = gen_mock.call_args.kwargs
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["prompt"] == "prompt"
    assert kwargs["size"] == "1024x1536"
    assert kwargs["quality"] == "medium"
    assert kwargs["moderation"] == "low"
    assert kwargs["n"] == 1
```

- [ ] **Step 3: Rodar — deve falhar com NotImplementedError**

Run: `pytest tests/test_image_provider.py::test_generate_writes_png_to_output_path -v`
Expected: FAIL com `NotImplementedError`

- [ ] **Step 4: Implementar `generate()` (caminho feliz, sem cache nem retry ainda)**

Editar `app/services/image_provider.py` — adicionar imports no topo:

```python
import base64
import hashlib
import shutil

from openai import OpenAI
```

Substituir o corpo de `generate()`:

```python
    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, timeout=self.timeout_s)

    def _cache_key(self, prompt: str) -> str:
        raw = f"{prompt}|{self.size}|{self.quality}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        resp = self._client().images.generate(
            model=self.model,
            prompt=prompt,
            size=self.size,
            quality=self.quality,
            moderation=self.moderation,
            n=1,
        )
        b64 = resp.data[0].b64_json
        png_bytes = base64.b64decode(b64)
        output_path.write_bytes(png_bytes)
        return output_path
```

- [ ] **Step 5: Rodar — deve passar**

Run: `pytest tests/test_image_provider.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add app/services/image_provider.py tests/test_image_provider.py tests/conftest.py
git commit -m "feat(image_provider): implement generate() happy path with tiny_png fixture"
```

---

## Task 4: `generate()` — cache SHA-256

**Files:**
- Modify: `app/services/image_provider.py`
- Modify: `tests/test_image_provider.py`

- [ ] **Step 1: Escrever teste falhando**

Adicionar em `tests/test_image_provider.py`:

```python
def test_generate_uses_cache_on_second_identical_call(tmp_path, tiny_png_b64):
    output1 = tmp_path / "scene_1.png"
    output2 = tmp_path / "scene_1_copy.png"
    cache = tmp_path / "cache"
    mock_response = MagicMock()
    mock_response.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.return_value = mock_response
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=cache)
        provider.generate("mesma prompt", output1)
        provider.generate("mesma prompt", output2)

    assert gen_mock.call_count == 1
    assert output1.exists()
    assert output2.exists()
    assert output1.read_bytes() == output2.read_bytes()


def test_cache_key_differs_by_quality(tmp_path):
    provider_low = OpenAIImageProvider(
        api_key="sk-test", quality="low", cache_dir=tmp_path / "c"
    )
    provider_high = OpenAIImageProvider(
        api_key="sk-test", quality="high", cache_dir=tmp_path / "c"
    )
    assert provider_low._cache_key("mesma") != provider_high._cache_key("mesma")


def test_cache_key_differs_by_size(tmp_path):
    p1 = OpenAIImageProvider(api_key="sk-test", size="1024x1536", cache_dir=tmp_path / "c")
    p2 = OpenAIImageProvider(api_key="sk-test", size="1024x1024", cache_dir=tmp_path / "c")
    assert p1._cache_key("mesma") != p2._cache_key("mesma")
```

- [ ] **Step 2: Rodar — deve falhar (chama API 2x)**

Run: `pytest tests/test_image_provider.py::test_generate_uses_cache_on_second_identical_call -v`
Expected: FAIL — `assert 2 == 1` (call_count)

- [ ] **Step 3: Adicionar lógica de cache em `generate()`**

Em `app/services/image_provider.py`, substituir `generate()` por:

```python
    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cache_file = self.cache_dir / f"{self._cache_key(prompt)}.png"
        if cache_file.exists():
            logger.info("Image cache HIT for prompt=%s", prompt[:60])
            shutil.copy(cache_file, output_path)
            return output_path

        resp = self._client().images.generate(
            model=self.model,
            prompt=prompt,
            size=self.size,
            quality=self.quality,
            moderation=self.moderation,
            n=1,
        )
        b64 = resp.data[0].b64_json
        png_bytes = base64.b64decode(b64)

        cache_file.write_bytes(png_bytes)
        shutil.copy(cache_file, output_path)
        return output_path
```

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_image_provider.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/image_provider.py tests/test_image_provider.py
git commit -m "feat(image_provider): cache by SHA-256 of (prompt, size, quality)"
```

---

## Task 5: `generate()` — retry e moderação

**Files:**
- Modify: `app/services/image_provider.py`
- Modify: `tests/test_image_provider.py`

- [ ] **Step 1: Escrever testes falhando**

Adicionar em `tests/test_image_provider.py`:

```python
import httpx
from openai import APIStatusError, APITimeoutError, BadRequestError


def _api_status_error(status_code: int, message: str = "transient") -> APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return APIStatusError(message=message, response=response, body=None)


def _bad_request_moderation() -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/images/generations")
    response = httpx.Response(
        400,
        request=request,
        json={"error": {"message": "moderation_blocked: content violates policy"}},
    )
    return BadRequestError(
        message="moderation_blocked: content violates policy",
        response=response,
        body=None,
    )


def test_generate_retries_on_rate_limit_429(tmp_path, tiny_png_b64, monkeypatch):
    monkeypatch.setattr("app.services.image_provider.time.sleep", lambda *_: None)
    ok = MagicMock()
    ok.data = [MagicMock(b64_json=tiny_png_b64)]

    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = [_api_status_error(429), _api_status_error(429), ok]
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "c")
        provider.generate("prompt", tmp_path / "out.png")

    assert gen_mock.call_count == 3


def test_generate_raises_moderation_blocked(tmp_path):
    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = _bad_request_moderation()
        provider = OpenAIImageProvider(api_key="sk-test", cache_dir=tmp_path / "c")
        with pytest.raises(ModerationBlockedError):
            provider.generate("violência explícita", tmp_path / "out.png")
    assert gen_mock.call_count == 1  # no retry on moderation


def test_generate_raises_provider_error_after_max_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.image_provider.time.sleep", lambda *_: None)
    with patch("app.services.image_provider.OpenAI") as mock_openai:
        gen_mock = mock_openai.return_value.images.generate
        gen_mock.side_effect = _api_status_error(500)
        provider = OpenAIImageProvider(
            api_key="sk-test", cache_dir=tmp_path / "c", max_retries=3
        )
        with pytest.raises(ImageProviderError):
            provider.generate("prompt", tmp_path / "out.png")
    assert gen_mock.call_count == 3
```

- [ ] **Step 2: Rodar — devem falhar (sem retry, sem moderation)**

Run: `pytest tests/test_image_provider.py -v`
Expected: 3 novos testes FAIL

- [ ] **Step 3: Implementar retry + moderation**

Em `app/services/image_provider.py`, adicionar import:

```python
import time

from openai import APIStatusError, APITimeoutError, BadRequestError
```

Substituir a parte da chamada API em `generate()` (mantendo o cache por cima):

```python
    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cache_file = self.cache_dir / f"{self._cache_key(prompt)}.png"
        if cache_file.exists():
            logger.info("Image cache HIT for prompt=%s", prompt[:60])
            shutil.copy(cache_file, output_path)
            return output_path

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client().images.generate(
                    model=self.model,
                    prompt=prompt,
                    size=self.size,
                    quality=self.quality,
                    moderation=self.moderation,
                    n=1,
                )
                b64 = resp.data[0].b64_json
                png_bytes = base64.b64decode(b64)
                cache_file.write_bytes(png_bytes)
                shutil.copy(cache_file, output_path)
                return output_path
            except BadRequestError as e:
                msg = str(e).lower()
                if "moderation" in msg or "content_policy" in msg or "safety" in msg:
                    raise ModerationBlockedError(
                        f"cena bloqueada pela moderação: {prompt[:80]}"
                    ) from e
                raise
            except (APIStatusError, APITimeoutError) as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        "Image API error (attempt %d/%d), sleeping %ds: %s",
                        attempt + 1, self.max_retries, backoff, e,
                    )
                    time.sleep(backoff)

        raise ImageProviderError(
            f"max_retries={self.max_retries} esgotado: {last_exc}"
        ) from last_exc
```

- [ ] **Step 4: Rodar — deve passar tudo**

Run: `pytest tests/test_image_provider.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/image_provider.py tests/test_image_provider.py
git commit -m "feat(image_provider): retry on 429/5xx + ModerationBlockedError on 400"
```

---

## Task 6: Expansão de `MediaStrategy` e `ScriptConfig`

**Files:**
- Modify: `app/templates.py`
- Modify: `tests/test_scriptwriter.py` (garantir não quebra)

- [ ] **Step 1: Editar dataclasses**

Em `app/templates.py`, substituir as duas dataclasses:

```python
@dataclass(frozen=True)
class MediaStrategy:
    source: str  # "pexels" | "local" | "ai_image"
    library_tag: str | None = None
    loop_single: bool = False
    # Campos para source == "ai_image":
    image_quality: str = "medium"
    image_size: str = "1024x1536"
    style_suffix: str = ""
    ken_burns: bool = False


@dataclass(frozen=True)
class ScriptConfig:
    prompt_extra: str
    needs_keywords: bool = True
    needs_visual_hint: bool = False
    word_rate: float = 2.05
```

- [ ] **Step 2: Rodar tests existentes — deve passar (campos novos com default, retrocompat)**

Run: `pytest tests/test_scriptwriter.py -v`
Expected: PASS (suite existente não afetada)

- [ ] **Step 3: Commit**

```bash
git add app/templates.py
git commit -m "refactor(templates): expand MediaStrategy and ScriptConfig for ai_image source"
```

---

## Task 7: Registrar template `novelinha_historica`

**Files:**
- Modify: `app/templates.py`
- Create: `tests/test_template_novelinha.py`

- [ ] **Step 1: Escrever teste falhando**

Criar `tests/test_template_novelinha.py`:

```python
from app.templates import TEMPLATES, get_template


def test_novelinha_historica_is_registered():
    assert "novelinha_historica" in TEMPLATES
    tpl = get_template("novelinha_historica")
    assert tpl.id == "novelinha_historica"


def test_novelinha_uses_ai_image_source():
    tpl = get_template("novelinha_historica")
    assert tpl.media.source == "ai_image"
    assert tpl.media.image_size == "1024x1536"
    assert tpl.media.image_quality == "medium"
    assert tpl.media.ken_burns is True
    assert "fotografia de época" in tpl.media.style_suffix.lower() \
        or "ilustração" in tpl.media.style_suffix.lower()


def test_novelinha_script_needs_visual_hint():
    tpl = get_template("novelinha_historica")
    assert tpl.script.needs_visual_hint is True
    assert tpl.script.needs_keywords is False


def test_novelinha_voice_is_placeholder():
    tpl = get_template("novelinha_historica")
    assert tpl.voice.voice_id == "TODO_VOICE_ID"
```

- [ ] **Step 2: Rodar — deve falhar (template ainda não existe)**

Run: `pytest tests/test_template_novelinha.py -v`
Expected: FAIL — `AssertionError: assert 'novelinha_historica' in TEMPLATES`

- [ ] **Step 3: Registrar template em `app/templates.py`**

Adicionar ao final do dict `TEMPLATES` (antes do `}` de fechamento):

```python
    "novelinha_historica": VideoTemplate(
        id="novelinha_historica",
        name="Drama Histórico",
        description="Fatos reais narrados como trailer cinematográfico, com imagens IA",
        icon="🎭",
        layout=LayoutConfig(type="fullscreen"),
        media=MediaStrategy(
            source="ai_image",
            image_quality="medium",
            image_size="1024x1536",
            style_suffix=(
                "fotografia de época ou ilustração cinematográfica realista, "
                "iluminação dramática, composição vertical 2:3, "
                "sem texto na imagem, sem marca d'água"
            ),
            ken_burns=True,
        ),
        script=ScriptConfig(
            prompt_extra=(
                "\n\nEste vídeo é um DRAMA HISTÓRICO narrado como trailer cinematográfico."
                "\nBase-se em um FATO REAL curioso, macabro ou pouco conhecido."
                "\nArco narrativo obrigatório: GANCHO (cena 1) → CONTEXTO (cenas 2-3) → "
                "CLÍMAX (cenas 4-5) → TWIST/RESOLUÇÃO (cena 6)."
                "\nTom grave, pausado, ligeiramente teatral — narrador de documentário."
                "\nUse EXATAMENTE 6 cenas, ~5 segundos cada."
                "\nNÃO invente fatos — se não sabe, escolha outro evento."
            ),
            needs_keywords=False,
            needs_visual_hint=True,
            word_rate=1.8,
        ),
        voice=VoicePreset(
            voice_id="TODO_VOICE_ID",
            rate=-10,
            pitch=-2,
        ),
    ),
```

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_template_novelinha.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/templates.py tests/test_template_novelinha.py
git commit -m "feat(templates): add novelinha_historica template with ai_image source"
```

---

## Task 8: ScriptWriter — injeção de instrução `visual_hint`

**Files:**
- Modify: `app/services/scriptwriter.py`
- Create: `tests/test_scriptwriter_visual_hint.py`

- [ ] **Step 1: Escrever testes falhando**

Criar `tests/test_scriptwriter_visual_hint.py`:

```python
from unittest.mock import MagicMock, patch

from app.services.scriptwriter import generate_script


FAKE_CLAUDE_RESPONSE = """
{
  "title": "Teste",
  "narration": "Narração de teste completa com seis cenas distintas.",
  "scenes": [
    {"text": "cena 1", "visual_hint": "sala vitoriana", "duration_hint": 5},
    {"text": "cena 2", "visual_hint": "rua londres 1880", "duration_hint": 5},
    {"text": "cena 3", "visual_hint": "porto noturno", "duration_hint": 5},
    {"text": "cena 4", "visual_hint": "manuscrito antigo", "duration_hint": 5},
    {"text": "cena 5", "visual_hint": "retrato sepia homem", "duration_hint": 5},
    {"text": "cena 6", "visual_hint": "lapide no cemiterio", "duration_hint": 5}
  ],
  "hashtags": ["#shorts"]
}
"""


def _mock_anthropic(body: str = FAKE_CLAUDE_RESPONSE):
    msg = MagicMock()
    msg.content = [MagicMock(text=body)]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def test_visual_hint_instruction_appears_for_ai_image_template():
    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic()
        cls.return_value = client
        generate_script("Titanic", "dramático", 30, "novelinha_historica")

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "VISUAL_HINT" in sent_prompt.upper()
    assert "visual_hint" in sent_prompt


def test_visual_hint_instruction_absent_for_stock_template():
    stock_response = FAKE_CLAUDE_RESPONSE.replace(
        '"visual_hint": "sala vitoriana", ', ''
    ).replace('"visual_hint": "rua londres 1880", ', '').replace(
        '"visual_hint": "porto noturno", ', ''
    ).replace('"visual_hint": "manuscrito antigo", ', '').replace(
        '"visual_hint": "retrato sepia homem", ', ''
    ).replace('"visual_hint": "lapide no cemiterio", ', '')

    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic(stock_response)
        cls.return_value = client
        generate_script("teste", "informativo", 30, "stock_narration")

    sent_prompt = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "VISUAL_HINT" not in sent_prompt.upper()


def test_script_preserves_visual_hint_in_output():
    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        cls.return_value = _mock_anthropic()
        script = generate_script("tema", "estilo", 30, "novelinha_historica")

    assert all("visual_hint" in s for s in script["scenes"])
    assert script["scenes"][0]["visual_hint"] == "sala vitoriana"
```

- [ ] **Step 2: Rodar — devem falhar (instrução não existe)**

Run: `pytest tests/test_scriptwriter_visual_hint.py -v`
Expected: FAIL (2 ou 3 testes)

- [ ] **Step 3: Adicionar instrução em `app/services/scriptwriter.py`**

No topo do arquivo (após o `SCRIPT_PROMPT`), adicionar constante:

```python
VISUAL_HINT_INSTRUCTION = """

REGRAS DE VISUAL_HINT:
- Cada cena tem campo "visual_hint": descricao em portugues de uma imagem unica
- Deve ser CONCRETA: objetos, pessoas, ambiente, iluminacao, angulo
- Evite texto, logos, rostos em close extremo
- Cenas diferentes = imagens claramente diferentes (sem repeticao visual)
- Exemplo bom: "salao vitoriano iluminado por velas, mesa comprida, mulher de vestido escuro olhando pela janela"
- Exemplo ruim: "a mulher" (faltam cena, ambiente, composicao)
"""
```

Dentro da função `generate_script`, **após** o bloco `if not template.script.needs_keywords:` e **antes** de `prompt_text += template.script.prompt_extra`, adicionar:

```python
    if template.script.needs_visual_hint:
        prompt_text += VISUAL_HINT_INSTRUCTION
        prompt_text = prompt_text.replace(
            '"duration_hint": 7',
            '"visual_hint": "descricao concreta da cena",\n      "duration_hint": 7',
        )
```

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_scriptwriter_visual_hint.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/scriptwriter.py tests/test_scriptwriter_visual_hint.py
git commit -m "feat(scriptwriter): inject visual_hint instruction when template requires"
```

---

## Task 9: ScriptWriter — validação de `visual_hint` presente

**Files:**
- Modify: `app/services/scriptwriter.py`
- Modify: `tests/test_scriptwriter_visual_hint.py`

- [ ] **Step 1: Escrever teste falhando**

Adicionar em `tests/test_scriptwriter_visual_hint.py`:

```python
EMPTY_HINT_RESPONSE = """
{
  "title": "Teste",
  "narration": "narracao",
  "scenes": [
    {"text": "c1", "visual_hint": "", "duration_hint": 5},
    {"text": "c2", "visual_hint": "x", "duration_hint": 5},
    {"text": "c3", "visual_hint": "y", "duration_hint": 5},
    {"text": "c4", "visual_hint": "z", "duration_hint": 5},
    {"text": "c5", "visual_hint": "w", "duration_hint": 5},
    {"text": "c6", "visual_hint": "v", "duration_hint": 5}
  ],
  "hashtags": []
}
"""


def test_raises_when_visual_hint_empty_for_ai_image():
    from app.services.scriptwriter import ScriptValidationError

    with patch("app.services.scriptwriter.anthropic.Anthropic") as cls:
        client = _mock_anthropic(EMPTY_HINT_RESPONSE)
        cls.return_value = client
        with pytest.raises(ScriptValidationError):
            generate_script("tema", "estilo", 30, "novelinha_historica")
```

E adicionar `import pytest` no topo do arquivo se não tem.

- [ ] **Step 2: Rodar — deve falhar (ScriptValidationError não existe)**

Run: `pytest tests/test_scriptwriter_visual_hint.py::test_raises_when_visual_hint_empty_for_ai_image -v`
Expected: FAIL — `ImportError` ou `NameError`

- [ ] **Step 3: Adicionar validação em `app/services/scriptwriter.py`**

No topo do arquivo (após imports), adicionar:

```python
class ScriptValidationError(Exception):
    """Raised when script output does not meet template requirements."""
```

Em `generate_script()`, antes do `return script`, adicionar:

```python
    if template.script.needs_visual_hint:
        for i, sc in enumerate(script.get("scenes", [])):
            if not sc.get("visual_hint", "").strip():
                raise ScriptValidationError(
                    f"cena {i+1} sem visual_hint (template {template_id} exige)"
                )
```

- [ ] **Step 4: Rodar tudo do scriptwriter**

Run: `pytest tests/test_scriptwriter.py tests/test_scriptwriter_visual_hint.py tests/test_template_novelinha.py -v`
Expected: PASS tudo

- [ ] **Step 5: Commit**

```bash
git add app/services/scriptwriter.py tests/test_scriptwriter_visual_hint.py
git commit -m "feat(scriptwriter): validate visual_hint presence for ai_image templates"
```

---

## Task 10: `task_generate_images` — caminho de skip

**Files:**
- Modify: `app/worker/tasks.py`
- Create: `tests/test_tasks_generate_images.py`

- [ ] **Step 1: Escrever teste falhando**

Criar `tests/test_tasks_generate_images.py`:

```python
from unittest.mock import MagicMock, patch

import pytest


def test_skip_when_template_is_not_ai_image(monkeypatch, tmp_path):
    from app.worker.tasks import task_generate_images

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: tmp_path)

    dummy_self = MagicMock()
    data_in = {"script": {"scenes": [{"text": "x", "duration_hint": 5}]}}

    result = task_generate_images.run(data_in, "job-1", "stock_narration")

    assert result == data_in
    assert "image_paths" not in result
```

- [ ] **Step 2: Rodar — deve falhar (ImportError)**

Run: `pytest tests/test_tasks_generate_images.py -v`
Expected: FAIL — `ImportError: cannot import name 'task_generate_images'`

- [ ] **Step 3: Implementar stub com skip only**

Em `app/worker/tasks.py`, adicionar import no topo:

```python
from app.services.image_provider import (
    ImageProviderError,
    ModerationBlockedError,
    OpenAIImageProvider,
)
from app.templates import get_template
from app.utils.files import get_job_dir
```

(Ajuste se algum já existir. `get_template`, `get_job_dir` e classes de erro são novos aqui.)

Adicionar a task antes de `dispatch_pipeline`:

```python
@celery_app.task(name="generate_images", bind=True)
def task_generate_images(self, data: dict, job_id: str, template_id: str) -> dict:
    try:
        if _check_cancelled(job_id):
            return data

        template = get_template(template_id)
        if template.media.source != "ai_image":
            logger.info("Job %s: template %s nao usa ai_image, skip", job_id, template_id)
            return data

        # Implementacao completa vem em Task 11
        raise NotImplementedError("generate path implemented in Task 11")

    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_images")
        raise
    except NotImplementedError:
        raise
    except Exception as e:
        _fail_job(job_id, f"Falha ao gerar imagens: {e}")
        raise
```

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_tasks_generate_images.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add app/worker/tasks.py tests/test_tasks_generate_images.py
git commit -m "feat(worker): add task_generate_images with skip path for non-ai_image templates"
```

---

## Task 11: `task_generate_images` — caminho de geração completo

**Files:**
- Modify: `app/worker/tasks.py`
- Modify: `tests/test_tasks_generate_images.py`

- [ ] **Step 1: Escrever testes falhando**

Adicionar em `tests/test_tasks_generate_images.py`:

```python
def test_generates_images_and_populates_image_paths(monkeypatch, tmp_path):
    from app.worker.tasks import task_generate_images

    job_dir = tmp_path / "job-42"
    job_dir.mkdir()
    script = {
        "scenes": [
            {"text": f"cena {i}", "visual_hint": f"hint {i}", "duration_hint": 5}
            for i in range(1, 7)
        ]
    }
    (job_dir / "script.json").write_text(
        '{"scenes": [{"text":"x","visual_hint":"h","duration_hint":5}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: job_dir)

    fake_provider = MagicMock()

    def fake_generate(prompt: str, output_path):
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return output_path

    fake_provider.generate = MagicMock(side_effect=fake_generate)
    monkeypatch.setattr(
        "app.worker.tasks.OpenAIImageProvider",
        lambda **kw: fake_provider,
    )
    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    data_in = {"script": script}
    result = task_generate_images.run(data_in, "job-42", "novelinha_historica")

    assert "image_paths" in result
    assert len(result["image_paths"]) == 6
    assert fake_provider.generate.call_count == 6
    for path_str in result["image_paths"]:
        assert (job_dir / "images").resolve() in __import__("pathlib").Path(path_str).resolve().parents


def test_fails_job_on_moderation_block(monkeypatch, tmp_path):
    from app.services.image_provider import ModerationBlockedError
    from app.worker.tasks import task_generate_images

    job_dir = tmp_path / "job-mb"
    job_dir.mkdir()
    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: job_dir)

    fake_provider = MagicMock()
    fake_provider.generate.side_effect = ModerationBlockedError("bloqueada")
    monkeypatch.setattr(
        "app.worker.tasks.OpenAIImageProvider", lambda **kw: fake_provider
    )
    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    failed = {"called": False}
    def fake_fail(jid, err):
        failed["called"] = True
        failed["err"] = err
    monkeypatch.setattr("app.worker.tasks._fail_job", fake_fail)

    script = {"scenes": [{"text": "x", "visual_hint": "y", "duration_hint": 5}]}
    with pytest.raises(ModerationBlockedError):
        task_generate_images.run({"script": script}, "job-mb", "novelinha_historica")

    assert failed["called"] is True
    assert "moderação" in failed["err"].lower() or "moderacao" in failed["err"].lower()
```

- [ ] **Step 2: Rodar — devem falhar (NotImplementedError)**

Run: `pytest tests/test_tasks_generate_images.py -v`
Expected: 2 novos FAIL

- [ ] **Step 3: Implementar corpo completo**

Em `app/worker/tasks.py`, substituir o corpo de `task_generate_images` (remover `NotImplementedError`):

```python
@celery_app.task(name="generate_images", bind=True)
def task_generate_images(self, data: dict, job_id: str, template_id: str) -> dict:
    try:
        if _check_cancelled(job_id):
            return data

        template = get_template(template_id)
        if template.media.source != "ai_image":
            logger.info("Job %s: template %s nao usa ai_image, skip", job_id, template_id)
            return data

        script = data.get("script")
        if not script:
            script_path = get_job_dir(job_id) / "script.json"
            script = json.loads(script_path.read_text(encoding="utf-8"))

        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script sem cenas")

        _update_job(
            job_id, "processing", "generating_images", 0.15,
            detail=f"Gerando {len(scenes)} imagens...",
        )

        quality = settings.GPT_IMAGE_QUALITY or template.media.image_quality
        provider = OpenAIImageProvider(
            quality=quality,
            size=template.media.image_size,
        )

        job_img_dir = get_job_dir(job_id) / "images"
        job_img_dir.mkdir(exist_ok=True, parents=True)

        image_paths: list[str] = []
        for i, scene in enumerate(scenes):
            if _check_cancelled(job_id):
                return data
            hint = scene.get("visual_hint", "").strip()
            if not hint:
                raise ValueError(f"cena {i+1} sem visual_hint")

            full_prompt = f"{hint}, {template.media.style_suffix}"
            out_path = job_img_dir / f"scene_{i+1}.png"
            provider.generate(full_prompt, out_path)

            image_paths.append(str(out_path))
            progress = 0.15 + (0.15 * (i + 1) / len(scenes))
            _update_job(
                job_id, "processing", "generating_images", progress,
                detail=f"Imagem {i+1}/{len(scenes)} OK",
            )

        data["image_paths"] = image_paths
        return data

    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_images")
        raise
    except ModerationBlockedError as e:
        _fail_job(job_id, f"Conteudo bloqueado pela moderacao: {e}")
        raise
    except Exception as e:
        _fail_job(job_id, f"Falha ao gerar imagens: {e}")
        raise
```

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_tasks_generate_images.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/worker/tasks.py tests/test_tasks_generate_images.py
git commit -m "feat(worker): implement generate_images loop with provider, cache, and fail-fast"
```

---

## Task 12: Chain — inserir task + early return em `fetch_media`

**Files:**
- Modify: `app/worker/tasks.py`
- Modify: `tests/test_tasks_generate_images.py`

- [ ] **Step 1: Escrever teste falhando**

Adicionar em `tests/test_tasks_generate_images.py`:

```python
def test_fetch_media_reuses_image_paths_when_ai_image(monkeypatch, tmp_path):
    from app.worker.tasks import task_fetch_media

    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    image_paths = [str(tmp_path / f"scene_{i}.png") for i in range(1, 7)]
    for p in image_paths:
        __import__("pathlib").Path(p).write_bytes(b"\x89PNG")

    data_in = {
        "script": {"scenes": [{"text": f"x{i}"} for i in range(6)]},
        "image_paths": image_paths,
    }

    result = task_fetch_media.run(data_in, "job-am", "novelinha_historica")

    assert result.get("media_paths") == image_paths
```

- [ ] **Step 2: Rodar — deve falhar (fetch_media ainda chama Pexels)**

Run: `pytest tests/test_tasks_generate_images.py::test_fetch_media_reuses_image_paths_when_ai_image -v`
Expected: FAIL (chama Pexels, erra no mock ou retorna errado)

- [ ] **Step 3: Adicionar early return em `task_fetch_media`**

Em `app/worker/tasks.py`, localizar `task_fetch_media`. Imediatamente após a linha que resolve `template = get_template(template_id)` (ou adicionar se não tem), inserir o early return **antes** de qualquer lógica de Pexels/local:

```python
    template = get_template(template_id)
    if template.media.source == "ai_image":
        data["media_paths"] = data.get("image_paths", [])
        _update_job(job_id, "processing", "media", 0.65, detail="Imagens IA ja geradas, skip Pexels.")
        return data
```

(Este bloco vai **antes** do `if template.media.source == "local" and ...` existente.)

- [ ] **Step 4: Inserir `task_generate_images` no chain**

Localizar `pipeline = chain(...)` em `dispatch_pipeline`. Substituir por:

```python
    pipeline = chain(
        task_generate_script.s(job_id, topic, style, duration_target, template_id),
        task_generate_images.s(job_id, template_id),
        task_synthesize_audio.s(job_id, template_id),
        task_transcribe_audio.s(job_id),
        task_fetch_media.s(job_id, template_id),
        task_compose_video.s(job_id, template_id),
        task_finalize.s(job_id),
    )
```

- [ ] **Step 5: Rodar todos os testes de worker**

Run: `pytest tests/test_tasks_generate_images.py tests/test_regression_pipeline.py tests/test_pipeline_resilience.py -v`
Expected: PASS (todos)

- [ ] **Step 6: Commit**

```bash
git add app/worker/tasks.py tests/test_tasks_generate_images.py
git commit -m "feat(worker): wire task_generate_images in chain + fetch_media passthrough for ai_image"
```

---

## Task 13: Compositor — extrair `_prepare_video_scene` (refactor puro)

**Files:**
- Modify: `app/services/compositor.py`

- [ ] **Step 1: Rodar suite de compositor antes do refactor**

Run: `pytest tests/ -k "compose or media or compositor" -v`
Expected: baseline de testes passando

- [ ] **Step 2: Renomear função atual e criar wrapper**

Em `app/services/compositor.py`, localizar a definição atual de `_prepare_scene` (linhas ~92-119). **Renomear** para `_prepare_video_scene`:

```python
def _prepare_video_scene(media_path: str, duration: float, output_clip: str) -> None:
    # ... corpo idêntico ao anterior de _prepare_scene ...
```

Adicionar um novo `_prepare_scene` que por enquanto só delega (router virá em Task 15):

```python
def _prepare_scene(media_path: str, duration: float, output_clip: str, scene_index: int = 0) -> None:
    _prepare_video_scene(media_path, duration, output_clip)
```

- [ ] **Step 3: Rodar suite novamente — comportamento preservado**

Run: `pytest tests/ -k "compose or media or compositor" -v`
Expected: PASS (mesmos que passavam antes)

- [ ] **Step 4: Commit**

```bash
git add app/services/compositor.py
git commit -m "refactor(compositor): extract _prepare_video_scene, add _prepare_scene router placeholder"
```

---

## Task 14: Compositor — `_prepare_static_image` com Ken Burns

**Files:**
- Modify: `app/services/compositor.py`
- Create: `tests/test_compositor_ken_burns.py`

- [ ] **Step 1: Escrever testes falhando**

Criar `tests/test_compositor_ken_burns.py`:

```python
from unittest.mock import patch

import pytest


def test_static_image_uses_loop_and_zoompan(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = str(tmp_path / "clip.mp4")

    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, out, scene_index=0)

    cmd = run.call_args.args[0]
    assert "-loop" in cmd
    assert "1" in cmd[cmd.index("-loop") + 1: cmd.index("-loop") + 2]
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf
    assert "scale=1080:1920" in vf
    assert "crop=1080:1920" in vf


def test_static_image_zooms_in_on_even_index(tmp_path):
    from app.services.compositor import _prepare_static_image

    img = tmp_path / "s.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=0)
    vf_even = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]

    with patch("app.services.compositor.subprocess.run") as run:
        _prepare_static_image(str(img), 5.0, str(tmp_path / "o.mp4"), scene_index=1)
    vf_odd = run.call_args.args[0][run.call_args.args[0].index("-vf") + 1]

    assert "min(zoom" in vf_even  # zoom in: z starts small, grows
    assert "max(1.15" in vf_odd   # zoom out: z starts 1.15, shrinks
```

- [ ] **Step 2: Rodar — devem falhar (função não existe)**

Run: `pytest tests/test_compositor_ken_burns.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implementar `_prepare_static_image`**

Em `app/services/compositor.py`, adicionar após `_prepare_video_scene`:

```python
def _prepare_static_image(
    img_path: str, duration: float, output_clip: str, scene_index: int = 0
) -> None:
    """Convert a still image into a short MP4 clip with Ken Burns (zoompan) effect."""
    fps = 25
    frames = int(round(duration * fps))
    zoom_in = (scene_index % 2) == 0
    if zoom_in:
        z_expr = "min(zoom+0.0012,1.15)"
    else:
        z_expr = "max(1.15-on*0.0012,1.0)"

    vf = (
        f"zoompan=z='{z_expr}':d={frames}:s=1080x1920:fps={fps},"
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,setsar=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-t", str(duration),
        "-i", img_path,
        "-vf", vf,
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-an",
        output_clip,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
```

(Confirme que `subprocess` já está importado no topo do arquivo; se não, adicione `import subprocess`.)

- [ ] **Step 4: Rodar — deve passar**

Run: `pytest tests/test_compositor_ken_burns.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/compositor.py tests/test_compositor_ken_burns.py
git commit -m "feat(compositor): add _prepare_static_image with alternating Ken Burns zoom"
```

---

## Task 15: Compositor — router em `_prepare_scene` + propagar `scene_index`

**Files:**
- Modify: `app/services/compositor.py`
- Modify: `tests/test_compositor_ken_burns.py`

- [ ] **Step 1: Escrever testes falhando**

Adicionar em `tests/test_compositor_ken_burns.py`:

```python
def test_prepare_scene_routes_png_to_static_image(tmp_path):
    from app.services import compositor

    img = tmp_path / "scene.png"
    img.write_bytes(b"\x89PNG")
    out = str(tmp_path / "out.mp4")

    with patch("app.services.compositor._prepare_static_image") as static, \
         patch("app.services.compositor._prepare_video_scene") as video:
        compositor._prepare_scene(str(img), 5.0, out, scene_index=2)

    static.assert_called_once()
    video.assert_not_called()
    assert static.call_args.kwargs.get("scene_index") == 2 \
        or static.call_args.args[-1] == 2


def test_prepare_scene_routes_mp4_to_video_scene(tmp_path):
    from app.services import compositor

    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00")
    out = str(tmp_path / "out.mp4")

    with patch("app.services.compositor._prepare_static_image") as static, \
         patch("app.services.compositor._prepare_video_scene") as video:
        compositor._prepare_scene(str(mp4), 5.0, out, scene_index=0)

    video.assert_called_once()
    static.assert_not_called()
```

- [ ] **Step 2: Rodar — deve falhar (router não despacha)**

Run: `pytest tests/test_compositor_ken_burns.py -v`
Expected: 2 testes novos FAIL

- [ ] **Step 3: Implementar router**

Em `app/services/compositor.py`, substituir o `_prepare_scene` placeholder (criado no Task 13) por:

```python
def _prepare_scene(
    media_path: str, duration: float, output_clip: str, scene_index: int = 0
) -> None:
    ext = Path(media_path).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        _prepare_static_image(media_path, duration, output_clip, scene_index=scene_index)
    else:
        _prepare_video_scene(media_path, duration, output_clip)
```

(Certifique-se que `from pathlib import Path` está no topo.)

- [ ] **Step 4: Propagar `scene_index` do `compose_short`**

Em `app/services/compositor.py`, localizar o loop em `compose_short` (linha ~468). Substituir:

```python
    for i, (scene, dur) in enumerate(zip(scenes, scene_durations)):
        # ... código existente ...
        _prepare_scene(media_paths[i], dur, output_clip)
```

Por:

```python
    for i, (scene, dur) in enumerate(zip(scenes, scene_durations)):
        # ... código existente ...
        _prepare_scene(media_paths[i], dur, output_clip, scene_index=i)
```

- [ ] **Step 5: Rodar toda a suite de compositor**

Run: `pytest tests/test_compositor_ken_burns.py tests/test_regression_pipeline.py -v`
Expected: PASS tudo

- [ ] **Step 6: Commit**

```bash
git add app/services/compositor.py tests/test_compositor_ken_burns.py
git commit -m "feat(compositor): route _prepare_scene by file extension, propagate scene_index"
```

---

## Task 16: Smoke test + primeiro E2E em `low` quality

**Files:**
- Create: `scripts/test-phase-b-smoke.py`

- [ ] **Step 1: Rodar suite completa — baseline verde**

Run: `pytest -q`
Expected: PASS (pelo menos tudo que passava antes + novos)

- [ ] **Step 2: Escrever script smoke end-to-end**

Criar `scripts/test-phase-b-smoke.py`:

```python
"""Phase B smoke test — gera 1 video end-to-end via template novelinha_historica.

Usa quality=low para custo baixo (~$0.03). Requer:
  - Backend running: uvicorn app.main:app --port 8005
  - Worker running: celery -A app.worker.celery_app worker -l info --pool=solo
  - OPENAI_API_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY nas env vars
  - Voice id valido colocado em app/templates.py (substituir TODO_VOICE_ID)

Uso:
    python scripts/test-phase-b-smoke.py "O Inquilino do Quarto 337"
"""
from __future__ import annotations

import os
import sys
import time

import requests

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8005")


def login() -> str:
    email = os.environ.get("ADMIN_EMAIL", "gbbraga.dev@gmail.com")
    with open(".admin-credentials.local", "r", encoding="utf-8") as f:
        pwd_line = next(line for line in f if line.startswith("password"))
    password = pwd_line.split("=", 1)[1].strip().strip('"')

    r = requests.post(f"{BACKEND}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def create_job(token: str, topic: str) -> str:
    r = requests.post(
        f"{BACKEND}/api/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "topic": topic,
            "style": "dramático cinematográfico",
            "duration_target": 30,
            "template_id": "novelinha_historica",
            "voice_provider": "elevenlabs",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def wait_job(token: str, job_id: str, timeout_s: int = 240) -> dict:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        r = requests.get(
            f"{BACKEND}/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        print(f"  status={data['status']} step={data.get('current_step')} detail={data.get('detail')}")
        if data["status"] in {"editable", "completed", "failed", "cancelled"}:
            return data
        time.sleep(3)
    raise TimeoutError(f"job {job_id} nao terminou em {timeout_s}s")


def main() -> int:
    topic = sys.argv[1] if len(sys.argv) > 1 else "O hospede que nunca saiu do quarto 337"
    os.environ["GPT_IMAGE_QUALITY"] = "low"

    token = login()
    print(f"[+] Autenticado.")
    jid = create_job(token, topic)
    print(f"[+] Job criado: {jid}")
    result = wait_job(token, jid)
    print(f"[+] Resultado: {result['status']}")
    if result["status"] == "editable":
        print(f"[+] Video em: storage/output/{jid}.mp4")
        return 0
    print(f"[!] Erro: {result.get('error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Substituir `TODO_VOICE_ID` por voice id real ElevenLabs**

Gui: abra `app/templates.py`, encontre o template `novelinha_historica`, substitua `voice_id="TODO_VOICE_ID"` por o `voice_id` real (ex: `"21m00Tcm4TlvDq8ikWAM"`).

```bash
# Valide depois
python -c "from app.templates import get_template; print(get_template('novelinha_historica').voice.voice_id)"
```

- [ ] **Step 4: Subir stack e rodar smoke**

Em 3 terminais diferentes (ou via `scripts/start-all.ps1`):

```powershell
# terminal 1
uvicorn app.main:app --host 127.0.0.1 --port 8005

# terminal 2
$env:GPT_IMAGE_QUALITY = "low"
celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo

# terminal 3
python scripts/test-phase-b-smoke.py "O Inquilino do Quarto 337"
```

Expected: script termina com exit 0 e imprime `[+] Video em: storage/output/<jid>.mp4`

- [ ] **Step 5: Verificar artefatos**

```bash
ls -la storage/jobs/<jid>/images/
ls -la storage/image-cache/
ffprobe storage/output/<jid>.mp4 2>&1 | grep -E "Duration|Stream"
```

Expected:
- 6 arquivos `scene_N.png` no job dir
- 6 arquivos `{sha256}.png` no image-cache
- Video 1080x1920, H.264+AAC, ~30s

- [ ] **Step 6: Commit script (mesmo se smoke falhar — script em si é artefato)**

```bash
git add scripts/test-phase-b-smoke.py app/templates.py
git commit -m "feat(scripts): Phase B smoke test + real ElevenLabs voice_id"
```

---

## Task 17: 3 vídeos de validação em `medium` + relatório

**Files:**
- Create: `docs/reports/phase-b-validation.md`

- [ ] **Step 1: Rodar 3 vídeos production em medium**

```powershell
$env:GPT_IMAGE_QUALITY = "medium"
python scripts/test-phase-b-smoke.py "A carta de suicidio que chegou 40 anos depois"
python scripts/test-phase-b-smoke.py "O navio fantasma do Atlantico em 1872"
python scripts/test-phase-b-smoke.py "A datilografa que previu sua propria morte"
```

Expected: 3 vídeos em `storage/output/*.mp4`, budget total ~$0.74.

- [ ] **Step 2: Assistir os 3 vídeos e dar nota 1-5**

Gui assiste cada vídeo em VLC ou player. Para cada um, anota:
- Nota geral (1-5)
- Qualidade visual das imagens (1-5)
- Hook de 3s é forte o suficiente? (sim/não)
- Narração prende? (sim/não)
- Quantas cenas tiveram moderation block (0-6)

- [ ] **Step 3: Escrever `docs/reports/phase-b-validation.md`**

Criar com template:

```markdown
# Fase B — Validação

**Data:** 2026-04-__
**Commit:** `<hash>`
**Quality:** medium
**Budget gasto:** $__

## Vídeos gerados

### 1. "A carta de suicidio que chegou 40 anos depois"
- Job ID: `<uuid>`
- Nota geral: _/5
- Qualidade visual: _/5
- Hook 3s: sim/não
- Narração prende: sim/não
- Blocks moderation: _/6
- Observações: ...

### 2. "O navio fantasma do Atlantico em 1872"
- ... (mesmos campos)

### 3. "A datilografa que previu sua propria morte"
- ... (mesmos campos)

## Critérios go/no-go

1. Pipeline E2E sem erro em 3 consecutivos: [sim/não]
2. ≥2 de 3 com nota geral ≥4: [sim/não]
3. Nenhum com 6/6 blocks: [sim/não]
4. Custo médio entre $0.15-$0.35: [sim/não — custo real: $_]
5. Latência ≤90s por vídeo: [sim/não — média: _s]

## Decisão

**[ ] GO** — abrir Fase B.2 (novos templates + polimento)
**[ ] NO-GO** — congelar Fase B, documentar aprendizado, seguir para Fase C com `stock_narration`

## Justificativa

(1-3 parágrafos explicando o que funcionou / não funcionou e por quê)
```

- [ ] **Step 4: Commit relatório**

```bash
git add docs/reports/phase-b-validation.md
git commit -m "docs: Phase B validation report"
```

- [ ] **Step 5: Rodar toda a suite pytest — gate final**

Run: `pytest -q`
Expected: baseline verde + todos os novos testes passando (≥210 tests).

- [ ] **Step 6: Rodar npm typecheck do frontend (nenhuma mudança mas confere que não quebrou)**

```powershell
cd frontend
npx next typegen
npx tsc --noEmit
cd ..
```

Expected: zero erros TS.

---

## Checklist de conclusão

- [ ] Task 1 — Config
- [ ] Task 2 — Scaffold provider
- [ ] Task 3 — generate() happy path
- [ ] Task 4 — Cache SHA-256
- [ ] Task 5 — Retry + moderation
- [ ] Task 6 — Dataclass expansion
- [ ] Task 7 — Template novelinha_historica
- [ ] Task 8 — ScriptWriter visual_hint injection
- [ ] Task 9 — ScriptWriter visual_hint validation
- [ ] Task 10 — task_generate_images skip
- [ ] Task 11 — task_generate_images generate
- [ ] Task 12 — Chain + fetch_media passthrough
- [ ] Task 13 — Compositor refactor
- [ ] Task 14 — _prepare_static_image
- [ ] Task 15 — Router + propagate scene_index
- [ ] Task 16 — Smoke test
- [ ] Task 17 — 3 validation videos + report
