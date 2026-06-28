# Áudio Rico por Job + Vozes pt-BR no Diálogo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao creator controle por-vídeo de SFX e música (toggles no dashboard), fazer o whoosh e a música sobreviverem ao export editado, e trocar as vozes do diálogo para pt-BR.

**Architecture:** Flags de geração por-job vivem no **hash Redis do job** (mesmo canal de `template_id`) — sem migration. Os workers e o `/composition` resolvem cada flag via um helper único com fallback para `settings`. A fidelidade editor==export é fechada re-mixando o SFX no re-render com as durações atuais e aplicando a música do mood como default quando o `editor_state` não a sobrescreve. Vozes de diálogo são só config.

**Tech Stack:** Python 3.12 + FastAPI + Celery (solo) + Redis + SQLAlchemy; Next.js 16 + React 19 + Remotion 4; ElevenLabs SDK; pytest; ffmpeg.

## Global Constraints

- pt-BR sempre (UI, comentários, mensagens). Mensagens de commit em ASCII (convenção do repo).
- **Worktree isolado** `C:\Dev\clipia\.claude\worktrees\audio-voices` (branch `feat/audio-rico-vozes-ptbr`, em cima do `ai_video`). NÃO tocar na feature `ai_video`. NÃO integrar no `main` nesta sessão.
- **Sem migration Alembic** — flags por-job são Redis-only (Postgres é compartilhado com a outra sessão).
- Celery `--pool=solo` sem hot-reload → reiniciar worker + backend após mudar código/config Python.
- Next.js 16: rodar `npx next typegen` antes de `npx tsc --noEmit`. Ler guias em `frontend/node_modules/next/dist/docs/` antes de mexer em padrões Next.
- ElevenLabs é no-op-safe sem `ELEVENLABS_API_KEY` (SFX/diálogo degradam graciosamente).
- Venv do worktree (NÃO o `.venv312` do main, que importa `app` do main tree).
- Comandos rodam a partir da raiz do worktree salvo indicação contrária.

---

### Task 0: Setup do worktree + baseline verde

**Files:** nenhum (ambiente).

- [ ] **Step 1: Criar venv isolado do worktree**

```powershell
& $env:CLIPIA_PYTHON312_EXE -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -e ".[dev]"
```

- [ ] **Step 2: Rodar a baseline e registrar a contagem**

Run: `pytest -q`
Expected: PASS (todos verdes; anotar o número de testes, ex. "NNN passed"). Se algo falhar, PARAR e reportar — não prosseguir sobre baseline vermelha.

- [ ] **Step 3: Confirmar typecheck do frontend limpo**

Run: `cd frontend; npm install; npx next typegen; npx tsc --noEmit; cd ..`
Expected: sem erros de tipo.

---

### Task 1: Flags de áudio por-job (request → Redis) + resolvedor

**Files:**
- Create: `app/job_config.py`
- Modify: `app/models.py:10-30` (GenerateRequest)
- Modify: `app/api/routes.py:195-206` (hset do job no endpoint generate)
- Test: `tests/test_audio_flags.py`

**Interfaces:**
- Produces: `resolve_job_flag(redis_client, job_id: str, key: str, default: bool) -> bool`
- Produces: `GenerateRequest.sfx_enabled: bool | None`, `GenerateRequest.music_enabled: bool | None`
- Produces: hash Redis `job:{id}` ganha campos `sfx_enabled`/`music_enabled` = `"1"`/`"0"` (ausentes se None)

- [ ] **Step 1: Escrever o teste do resolvedor (falha)**

Create `tests/test_audio_flags.py`:

```python
from app.job_config import resolve_job_flag


class _StubRedis:
    def __init__(self, fields):
        self._fields = fields

    def hget(self, key, field):
        return self._fields.get(field)


def test_resolve_job_flag_reads_overrides():
    r = _StubRedis({"sfx_enabled": "1", "music_enabled": "0"})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=False) is True
    assert resolve_job_flag(r, "job1", "music_enabled", default=True) is False


def test_resolve_job_flag_falls_back_to_default_when_absent():
    r = _StubRedis({})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=True) is True
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=False) is False


def test_resolve_job_flag_handles_bytes():
    r = _StubRedis({"sfx_enabled": b"0"})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=True) is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_audio_flags.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.job_config'`.

- [ ] **Step 3: Criar `app/job_config.py`**

```python
"""Overrides de geracao por job (SFX/musica) guardados no hash Redis do job.

Os workers e o endpoint /composition leem essas flags do mesmo hash onde mora o
template_id, para decidir POR-VIDEO o que antes so existia global em settings.
"""


def resolve_job_flag(redis_client, job_id: str, key: str, default: bool) -> bool:
    """Le um override booleano por-job ("1"/"0") do hash Redis; cai no default se ausente."""
    raw = redis_client.hget(f"job:{job_id}", key)
    if isinstance(raw, bytes):
        raw = raw.decode()
    if raw == "1":
        return True
    if raw == "0":
        return False
    return default
```

- [ ] **Step 4: Rodar o teste do resolvedor (passa)**

Run: `pytest tests/test_audio_flags.py -q`
Expected: PASS (3 testes).

- [ ] **Step 5: Adicionar os campos ao `GenerateRequest`**

Em `app/models.py`, dentro de `class GenerateRequest`, após a linha `trend_context` (linha ~23), acrescentar:

```python
    sfx_enabled: bool | None = Field(
        default=None, description="Liga/desliga SFX (whoosh) por video. None = usar settings.SFX_ENABLED"
    )
    music_enabled: bool | None = Field(
        default=None, description="Liga/desliga musica de fundo por video. None = usar settings.AUTO_MUSIC_ENABLED"
    )
```

- [ ] **Step 6: Gravar as flags no hash Redis do job (endpoint generate)**

Em `app/api/routes.py`, substituir o bloco `_redis.hset(...)` das linhas 195-206 por:

```python
    job_meta = {
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "detail": "",
        "template_id": req.template_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if req.sfx_enabled is not None:
        job_meta["sfx_enabled"] = "1" if req.sfx_enabled else "0"
    if req.music_enabled is not None:
        job_meta["music_enabled"] = "1" if req.music_enabled else "0"
    _redis.hset(f"job:{job_id}", mapping=job_meta)
```

- [ ] **Step 7: Escrever o teste HTTP de /generate (append em `tests/test_audio_flags.py`)**

```python
import pytest


@pytest.mark.asyncio
async def test_generate_persists_audio_flags_in_redis(client, app, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={
            "topic": "cinco curiosidades sobre o oceano profundo",
            "style": "educational",
            "duration_target": 30,
            "template_id": "stock_narration",
            "voice_provider": "edge",
            "sfx_enabled": False,
            "music_enabled": True,
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert app.state.fake_redis.hget(f"job:{job_id}", "sfx_enabled") == "0"
    assert app.state.fake_redis.hget(f"job:{job_id}", "music_enabled") == "1"


@pytest.mark.asyncio
async def test_generate_without_flags_leaves_them_absent(client, app, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={
            "topic": "cinco curiosidades sobre o oceano profundo",
            "style": "educational",
            "duration_target": 30,
            "template_id": "stock_narration",
            "voice_provider": "edge",
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert app.state.fake_redis.hget(f"job:{job_id}", "sfx_enabled") is None
```

- [ ] **Step 8: Rodar a suíte do arquivo (passa)**

Run: `pytest tests/test_audio_flags.py -q`
Expected: PASS (5 testes).

- [ ] **Step 9: Commit**

```powershell
git add app/job_config.py app/models.py app/api/routes.py tests/test_audio_flags.py
git commit -m "feat(audio): flags sfx_enabled/music_enabled por job no hash Redis"
```

---

### Task 2: Geração inicial honra as flags

**Files:**
- Modify: `app/services/music.py` (helpers sem o gate global)
- Modify: `app/worker/tasks.py:677-695` (task_compose_video)
- Test: `tests/test_music_resolve.py`

**Interfaces:**
- Consumes: `resolve_job_flag` (Task 1)
- Produces: `resolve_music_path(template_id: str) -> str | None` (path FS, sem gate global)
- Produces: `auto_music_url(template_id: str) -> str | None` (URL `/music/<mood>.mp3`, sem gate global)

- [ ] **Step 1: Escrever o teste dos helpers de música (falha)**

Create `tests/test_music_resolve.py`:

```python
from app.services import music


def test_resolve_music_path_returns_path_when_file_exists(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") == str(tmp_path / "inspirational.mp3")


def test_resolve_music_path_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") is None


def test_auto_music_url_uses_mood(tmp_path, monkeypatch):
    (tmp_path / "lofi-chill.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.auto_music_url("dialogue_duo") == "/music/lofi-chill.mp3"


def test_resolve_auto_music_respects_global_flag(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", False)
    assert music.resolve_auto_music("stock_narration") is None
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", True)
    assert music.resolve_auto_music("stock_narration") == str(tmp_path / "inspirational.mp3")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_music_resolve.py -q`
Expected: FAIL com `AttributeError: module 'app.services.music' has no attribute 'resolve_music_path'`.

- [ ] **Step 3: Adicionar os helpers em `app/services/music.py`**

Substituir a função `resolve_auto_music` (linhas 25-31) por:

```python
def _mood_for(template_id: str) -> str:
    return TEMPLATE_MOODS.get(template_id, DEFAULT_MOOD)


def resolve_music_path(template_id: str) -> str | None:
    """Path FS do mp3 do mood do template (SEM checar a flag global; o caller decide)."""
    path = _MUSIC_DIR / f"{_mood_for(template_id)}.mp3"
    return str(path) if path.exists() else None


def auto_music_url(template_id: str) -> str | None:
    """URL relativa (/music/<mood>.mp3) do mood do template, ou None se a faixa nao existe."""
    mood = _mood_for(template_id)
    return f"/music/{mood}.mp3" if (_MUSIC_DIR / f"{mood}.mp3").exists() else None


def resolve_auto_music(template_id: str) -> str | None:
    """Path FS da musica do template respeitando a flag global AUTO_MUSIC_ENABLED."""
    if not settings.AUTO_MUSIC_ENABLED:
        return None
    return resolve_music_path(template_id)
```

- [ ] **Step 4: Rodar o teste dos helpers (passa)**

Run: `pytest tests/test_music_resolve.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Aplicar as flags em `task_compose_video`**

Em `app/worker/tasks.py`, substituir o bloco das linhas 677-695 por:

```python
        from app.job_config import resolve_job_flag

        audio_path = data["audio_path"]
        if resolve_job_flag(_redis, job_id, "sfx_enabled", settings.SFX_ENABLED):
            from app.services.sfx import mix_transitions

            scene_durs = [s.get("duration_hint", 0) for s in data["script"]["scenes"]]
            audio_path = mix_transitions(audio_path, scene_durs, str(job_dir / "narration_sfx.wav"))

        from app.services.music import resolve_music_path

        music_enabled = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
        music_path = resolve_music_path(template_id) if music_enabled else None
        compose_short(
            scenes=data["script"]["scenes"],
            media_paths=data["media_paths"],
            audio_path=audio_path,
            words=data["words"],
            output_path=output_path,
            layout=template.layout,
            music_path=music_path,
            music_volume=settings.AUTO_MUSIC_VOLUME,
        )
```

(Usa `resolve_music_path` em vez de `resolve_auto_music`: a decisão de ligar/desligar é a flag por-job, não o gate global.)

- [ ] **Step 6: Rodar a suíte inteira (nada quebrou)**

Run: `pytest -q`
Expected: PASS (baseline + novos). `task_compose_video` é validado fim-a-fim no Task 7 (E2E).

- [ ] **Step 7: Commit**

```powershell
git add app/services/music.py app/worker/tasks.py tests/test_music_resolve.py
git commit -m "feat(audio): geracao inicial respeita sfx/music por job"
```

---

### Task 3: Fidelidade do export — SFX sobrevive + música default no re-render

**Files:**
- Modify: `app/services/remotion.py:70-153` (build_composition_props + invoke_remotion_render)
- Modify: `app/worker/tasks.py:768-863` (task_rerender_video)
- Test: `tests/test_remotion_props.py`

**Interfaces:**
- Consumes: `resolve_job_flag` (Task 1), `auto_music_url` (Task 2), `mix_transitions(audio, durs, out) -> str` (existente em `app/services/sfx.py`)
- Produces: `build_composition_props(job_id, backend_url=None, audio_filename="narration.wav", default_music_url=None) -> dict`
- Produces: `invoke_remotion_render(job_id, output_path, on_progress=None, timeout=None, audio_filename="narration.wav", default_music_url=None) -> str`

- [ ] **Step 1: Escrever o teste de build_composition_props (falha)**

Create `tests/test_remotion_props.py`:

```python
import json

from app.services import remotion


def _make_job(tmp_path, with_state=None):
    job_dir = tmp_path / "jobs" / "job1"
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"title": "t", "scenes": [{"text": "a", "duration_hint": 5}]}))
    (job_dir / "words.json").write_text(json.dumps([]))
    if with_state is not None:
        (job_dir / "editor_state.json").write_text(json.dumps({"composition": with_state}))
    return job_dir


def test_audio_filename_overrides_audio_url(tmp_path, monkeypatch):
    _make_job(tmp_path)
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", audio_filename="narration_sfx.wav")
    assert props["audioUrl"].endswith("/storage/jobs/job1/narration_sfx.wav")


def test_default_music_url_applied_when_no_editor_state(tmp_path, monkeypatch):
    _make_job(tmp_path)
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] == "/music/lofi-chill.mp3"


def test_editor_state_null_music_is_respected(tmp_path, monkeypatch):
    _make_job(tmp_path, with_state={"musicUrl": None})
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] is None  # usuario removeu a musica no editor -> respeitar


def test_editor_state_track_overrides_default(tmp_path, monkeypatch):
    _make_job(tmp_path, with_state={"musicUrl": "/music/happy-pop.mp3"})
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] == "/music/happy-pop.mp3"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_remotion_props.py -q`
Expected: FAIL (audio_filename é argumento inesperado / musicUrl default None).

- [ ] **Step 3: Editar `build_composition_props` em `app/services/remotion.py`**

Mudar a assinatura (linha 70) para:

```python
def build_composition_props(
    job_id: str,
    backend_url: str | None = None,
    audio_filename: str = "narration.wav",
    default_music_url: str | None = None,
) -> dict:
```

Trocar a linha 111 `"audioUrl": url("narration.wav"),` por:

```python
        "audioUrl": url(audio_filename),
```

Trocar a linha 119 `"musicUrl": None,` por:

```python
        "musicUrl": default_music_url,
```

Substituir o bloco de overlay do editor_state (linhas 125-130) por (respeita `musicUrl: null` explícito):

```python
    state_path = job_dir / "editor_state.json"
    if state_path.exists():
        comp = (_read_json(state_path) or {}).get("composition", {}) or {}
        for key in _EDITABLE_KEYS:
            if key == "musicUrl":
                if "musicUrl" in comp:  # respeita None explicito (usuario tirou a musica)
                    props["musicUrl"] = comp["musicUrl"]
            elif comp.get(key) is not None:
                props[key] = comp[key]
```

- [ ] **Step 4: Rodar o teste de props (passa)**

Run: `pytest tests/test_remotion_props.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Propagar os params em `invoke_remotion_render`**

Em `app/services/remotion.py`, mudar a assinatura (linha 138) para:

```python
def invoke_remotion_render(
    job_id: str,
    output_path: str,
    on_progress=None,
    timeout: int | None = None,
    audio_filename: str = "narration.wav",
    default_music_url: str | None = None,
) -> str:
```

E a chamada interna (linha 151) para:

```python
    props = build_composition_props(job_id, audio_filename=audio_filename, default_music_url=default_music_url)
```

- [ ] **Step 6: Re-mixar SFX + música default no `task_rerender_video`**

Em `app/worker/tasks.py`, logo após o bloco que valida `narration.wav` (linha 790-792), inserir:

```python
        from app.job_config import resolve_job_flag
        from app.services.music import auto_music_url, resolve_music_path

        template_id = _redis_hget(f"job:{job_id}", "template_id") or "stock_narration"

        audio_basename = "narration.wav"
        if resolve_job_flag(_redis, job_id, "sfx_enabled", settings.SFX_ENABLED):
            from app.services.sfx import mix_transitions

            scene_durs = [s.get("duration_hint", 0) for s in script.get("scenes", [])]
            audio_path = mix_transitions(audio_path, scene_durs, str(job_dir / "narration_sfx.wav"))
            audio_basename = Path(audio_path).name  # narration_sfx.wav se mixou; senao narration.wav

        music_enabled = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
        default_music_url = auto_music_url(template_id) if music_enabled else None
```

Na branch Remotion, mudar a chamada `invoke_remotion_render(...)` (linha 824-834) para passar os novos params:

```python
            invoke_remotion_render(
                job_id,
                output_path,
                audio_filename=audio_basename,
                default_music_url=default_music_url,
                on_progress=lambda p: _update_job(
                    job_id,
                    "rendering",
                    "encoding",
                    0.2 + (p / 100) * 0.7,
                    detail=f"Renderizando com Remotion... {p}%",
                ),
            )
```

Na branch FFmpeg fallback (linhas 836-863), substituir a resolução de música/template por (reusa `template_id`/`audio_path` já calculados; aplica o default de mood quando o editor não sobrescreveu):

```python
            # FFmpeg+NVENC fallback path
            music_path = None
            music_url = comp_data.get("musicUrl", default_music_url)
            if music_url:
                music_file = BASE_DIR / "frontend" / "public" / music_url.lstrip("/")
                if music_file.exists():
                    music_path = str(music_file)

            output_path = str(job_dir / "final_edited.mp4")
            _update_job(job_id, "rendering", "encoding", 0.2, detail="Re-renderizando video...")
            logger.info(f"Starting FFmpeg+NVENC re-render for job {job_id}")

            from app.templates import get_template

            re_template = get_template(template_id)

            compose_short(
                scenes=script.get("scenes", []),
                media_paths=media_paths,
                audio_path=audio_path,
                words=words,
                output_path=output_path,
                music_path=music_path,
                music_volume=comp_data.get("musicVolume", settings.AUTO_MUSIC_VOLUME),
                subtitle_style=comp_data.get("subtitleStyle"),
                layout=re_template.layout,
            )
```

- [ ] **Step 7: Rodar a suíte inteira**

Run: `pytest -q`
Expected: PASS. A fiação do re-render é validada fim-a-fim no Task 7.

- [ ] **Step 8: Commit**

```powershell
git add app/services/remotion.py app/worker/tasks.py tests/test_remotion_props.py
git commit -m "fix(export): SFX e musica do mood sobrevivem ao re-render Remotion"
```

---

### Task 4: Coerência da música no editor (display ao abrir)

**Files:**
- Modify: `app/models.py:60-73` (CompositionResponse)
- Modify: `app/api/routes.py:576-635` (get_composition)
- Modify: `frontend/src/lib/editor-api.ts:18-63` (fetchComposition)
- Test: append em `tests/test_music_resolve.py`

**Interfaces:**
- Consumes: `auto_music_url` (Task 2), `resolve_job_flag` (Task 1)
- Produces: `CompositionResponse.music_url: str | None`, `CompositionResponse.music_volume: float`

- [ ] **Step 1: Escrever o teste do default de música no get_composition (falha)**

Append em `tests/test_music_resolve.py`:

```python
import json as _json

import pytest


@pytest.mark.asyncio
async def test_composition_returns_mood_music_url(client, app, db_session, verified_user, auth_headers, tmp_path, monkeypatch):
    from app.config import settings as app_settings
    from app.db.models import Job

    job = Job(user_id=verified_user.id, topic="oceano profundo curiosidades", style="educational",
              duration_target=30, template_id="dialogue_duo", status="editable")
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    job_dir = app_settings.STORAGE_DIR / "jobs" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "script.json").write_text(_json.dumps({"title": "t", "scenes": [{"text": "a", "duration_hint": 5}]}))
    (job_dir / "words.json").write_text(_json.dumps([]))
    (job_dir / "narration.wav").write_bytes(b"x")

    resp = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["music_url"] == "/music/lofi-chill.mp3"  # mood do dialogue_duo
```

(As faixas `frontend/public/music/lofi-chill.mp3` etc. existem no repo, então `auto_music_url` as encontra via `_MUSIC_DIR` real.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `pytest tests/test_music_resolve.py::test_composition_returns_mood_music_url -q`
Expected: FAIL com `KeyError: 'music_url'` (campo não existe na resposta).

- [ ] **Step 3: Adicionar os campos ao `CompositionResponse`**

Em `app/models.py`, dentro de `class CompositionResponse`, após `pending_credits` (linha 73), acrescentar:

```python
    music_url: str | None = Field(default=None, description="Faixa de fundo do mood (default quando sem editor_state)")
    music_volume: float = Field(default=0.12, description="Volume default da musica de fundo")
```

- [ ] **Step 4: Computar o default em `get_composition`**

Em `app/api/routes.py`, na função `get_composition`, logo após `tmpl = get_template(job_template_id)` (linha 629), inserir:

```python
    from app.job_config import resolve_job_flag
    from app.services.music import auto_music_url

    music_on = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
    default_music_url = auto_music_url(job_template_id) if music_on else None
```

E no `return CompositionResponse(...)`, acrescentar os dois campos:

```python
        music_url=default_music_url,
        music_volume=settings.AUTO_MUSIC_VOLUME,
```

- [ ] **Step 5: Rodar o teste de composição (passa)**

Run: `pytest tests/test_music_resolve.py::test_composition_returns_mood_music_url -q`
Expected: PASS.

- [ ] **Step 6: Consumir o default no frontend (`fetchComposition`)**

Em `frontend/src/lib/editor-api.ts`, no tipo inline da resposta (linhas 19-32), acrescentar dentro do objeto:

```typescript
    music_url: string | null
    music_volume: number
```

E no objeto retornado (linhas 40-62), trocar as linhas de `musicUrl`/`musicVolume` (56-57) por (respeita `null` salvo = usuário removeu; usa o mood só quando NÃO há editor_state):

```typescript
    musicUrl: saved ? (saved.musicUrl ?? null) : (data.music_url ?? null),
    musicVolume: saved?.musicVolume ?? data.music_volume ?? 0.15,
```

- [ ] **Step 7: Typecheck do frontend**

Run: `cd frontend; npx next typegen; npx tsc --noEmit; cd ..`
Expected: sem erros.

- [ ] **Step 8: Commit**

```powershell
git add app/models.py app/api/routes.py frontend/src/lib/editor-api.ts tests/test_music_resolve.py
git commit -m "feat(editor): editor abre com a musica do mood (coerencia geracao->editor)"
```

---

### Task 5: Toggles de áudio no dashboard (GenerateForm)

**Files:**
- Modify: `frontend/src/lib/editor-api.ts:89-97` (GenerateParams)
- Modify: `frontend/src/components/dashboard/GenerateForm.tsx`

**Interfaces:**
- Consumes: endpoint `/generate` que aceita `sfx_enabled`/`music_enabled` (Task 1)
- Produces: `GenerateParams.sfx_enabled?: boolean`, `GenerateParams.music_enabled?: boolean`

- [ ] **Step 1: Adicionar os campos ao `GenerateParams`**

Em `frontend/src/lib/editor-api.ts`, dentro de `interface GenerateParams` (após `trend_context?`, linha 96):

```typescript
  sfx_enabled?: boolean
  music_enabled?: boolean
```

- [ ] **Step 2: Estado dos toggles no `GenerateForm`**

Em `frontend/src/components/dashboard/GenerateForm.tsx`, após `const [voiceProvider, ...]` (linha 55), acrescentar:

```typescript
  const [sfxEnabled, setSfxEnabled] = useState(true)
  const [musicEnabled, setMusicEnabled] = useState(true)
```

- [ ] **Step 3: Enviar no payload**

No objeto `params` (linhas 134-144), antes de `trend_context`, acrescentar:

```typescript
        sfx_enabled: sfxEnabled,
        music_enabled: musicEnabled,
```

- [ ] **Step 4: Renderizar o bloco "Áudio"**

Em `GenerateForm.tsx`, logo após o bloco `{/* Voice Provider */}` (após a `</div>` da linha 260) e antes de `{/* Advanced Script Section */}`, inserir:

```tsx
      {/* Audio */}
      <div className="mb-5">
        <label className="block text-xs text-[var(--text-tertiary)] mb-2">Áudio</label>
        <div className="flex flex-col gap-2">
          {([
            { on: sfxEnabled, set: setSfxEnabled, label: 'Efeitos sonoros', hint: 'Whoosh nas transições de cena' },
            { on: musicEnabled, set: setMusicEnabled, label: 'Música de fundo', hint: 'Trilha automática pelo tema do template' },
          ] as const).map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => item.set(!item.on)}
              disabled={generating}
              className={`flex items-center justify-between py-2.5 px-3 rounded-xl border text-xs font-medium transition cursor-pointer disabled:opacity-50 ${
                item.on
                  ? 'border-purple-500/50 bg-purple-500/10 text-purple-300'
                  : 'border-[var(--border-default)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] hover:border-purple-500/30'
              }`}
            >
              <span className="flex flex-col items-start text-left">
                <span className="font-semibold">{item.label}</span>
                <span className="text-[10px] opacity-60">{item.hint}</span>
              </span>
              <span
                className={`relative w-9 h-5 rounded-full transition shrink-0 ${item.on ? 'bg-purple-600' : 'bg-[var(--bg-surface-hover)]'}`}
              >
                <span
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                  style={{ left: item.on ? '18px' : '2px' }}
                />
              </span>
            </button>
          ))}
        </div>
      </div>
```

- [ ] **Step 5: Typecheck do frontend**

Run: `cd frontend; npx next typegen; npx tsc --noEmit; cd ..`
Expected: sem erros.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/lib/editor-api.ts frontend/src/components/dashboard/GenerateForm.tsx
git commit -m "feat(dashboard): toggles de SFX e musica de fundo na geracao"
```

---

### Task 6: Vozes pt-BR no diálogo (só config)

**Files:**
- Create: `scripts/list_elevenlabs_voices.py`
- Modify: `app/config.py:66-69` (DIALOGUE_VOICE_A/B)
- Modify: `app/templates.py` (dialogue_duo voice_id)
- Modify: `.env.example` (documentar override)
- Test: append em `tests/test_audio_flags.py`

**Interfaces:**
- Consumes: `ElevenLabsProvider().list_voices()` (existente, `app/services/elevenlabs_provider.py`)

- [ ] **Step 1: Script de descoberta de vozes**

Create `scripts/list_elevenlabs_voices.py`:

```python
"""Lista as vozes da conta ElevenLabs (id, nome, genero) p/ escolher as do dialogo.

Rode: python -m scripts.list_elevenlabs_voices
A language vem como "multilingual" — julgue pt-BR por nome/preview no dashboard ElevenLabs.
"""
import asyncio

from app.services.elevenlabs_provider import ElevenLabsProvider


async def main():
    voices = await ElevenLabsProvider().list_voices()
    for v in voices:
        print(f"{v.id}\t{v.name}\t{getattr(v, 'gender', '?')}\t{getattr(v, 'language', '?')}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Rodar a descoberta e escolher 2 vozes pt-BR**

Run: `python -m scripts.list_elevenlabs_voices`
Expected: lista de vozes. Escolher **2 pt-BR**, idealmente 1 feminina + 1 masculina. Candidata feminina já conhecida: **Fernanda `KHmfNHtEjHhLK9eER20w`**. Identificar uma **masculina** pt-BR (julgar por nome/preview). Anotar os 2 ids. **CHECKPOINT:** confirmar a escolha (especialmente a masculina) com o Gui antes de fixar. Se a conta não tiver masculina pt-BR boa, usar `POST /voices/design` para criar uma, ou manter a melhor multilingual disponível.

- [ ] **Step 3: Escrever o teste dos defaults (falha)**

Append em `tests/test_audio_flags.py`:

```python
def test_dialogue_voices_are_not_legacy_en():
    from app.config import settings

    legacy = {"21m00Tcm4TlvDq8ikWAM", "pNInz6obpgDQGcFmaJgB"}  # Rachel / Adam (EN)
    assert settings.DIALOGUE_VOICE_A not in legacy
    assert settings.DIALOGUE_VOICE_B not in legacy


def test_dialogue_template_uses_configured_voice():
    from app.config import settings
    from app.templates import get_template

    assert get_template("dialogue_duo").voice.voice_id == settings.DIALOGUE_VOICE_A
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `pytest tests/test_audio_flags.py -k dialogue -q`
Expected: FAIL (defaults ainda são os EN; template ainda aponta para Rachel).

- [ ] **Step 5: Atualizar os defaults em `app/config.py`**

Substituir as linhas 66-69 por (usar os ids pt-BR escolhidos no Step 2):

```python
    # Dialogo multi-locutor (text_to_dialogue): 2 vozes ElevenLabs pt-BR. Troque por env se quiser.
    DIALOGUE_VOICE_A: str = "KHmfNHtEjHhLK9eER20w"  # Fernanda (pt-BR, feminina)
    DIALOGUE_VOICE_B: str = "<VOICE_ID_MASCULINA_PTBR>"  # <Nome> (pt-BR, masculina) — do Step 2
```

- [ ] **Step 6: Alinhar o `voice_id` cosmético do template**

Em `app/templates.py`, no template `dialogue_duo`, trocar a linha `voice=VoicePreset(provider="elevenlabs", voice_id="21m00Tcm4TlvDq8ikWAM")` por:

```python
        voice=VoicePreset(provider="elevenlabs", voice_id=settings.DIALOGUE_VOICE_A),
```

Garantir que `from app.config import settings` já está importado no topo de `app/templates.py` (se não, adicionar).

- [ ] **Step 7: Documentar override no `.env.example`**

Acrescentar ao `.env.example` (perto das outras chaves ElevenLabs):

```
# Vozes do template de dialogo (dialogue_duo). Defaults pt-BR no config; troque por ids da sua conta.
DIALOGUE_VOICE_A=
DIALOGUE_VOICE_B=
```

- [ ] **Step 8: Rodar os testes de diálogo (passam)**

Run: `pytest tests/test_audio_flags.py -k dialogue -q`
Expected: PASS (2 testes).

- [ ] **Step 9: Commit**

```powershell
git add scripts/list_elevenlabs_voices.py app/config.py app/templates.py .env.example tests/test_audio_flags.py
git commit -m "feat(dialogo): vozes pt-BR no template dialogue_duo (config)"
```

---

### Task 7: Verificação final (suíte completa + E2E manual)

**Files:** nenhum (verificação).

- [ ] **Step 1: Suíte backend inteira verde**

Run: `pytest -q`
Expected: PASS (baseline do Task 0 + todos os novos).

- [ ] **Step 2: Typecheck frontend limpo**

Run: `cd frontend; npx next typegen; npx tsc --noEmit; cd ..`
Expected: sem erros.

- [ ] **Step 3: Subir a stack do worktree e reiniciar worker+backend**

Subir Postgres/Redis (docker, compartilhados) e os serviços via `scripts/_run-*.ps1` apontando para o worktree, OU rodar backend+worker+frontend manualmente a partir do worktree. **Reiniciar worker e backend** (Celery solo não recarrega código).

- [ ] **Step 4: E2E — áudio rico**

Gerar um vídeo no dashboard com **SFX on + Música on** → conferir whoosh + música no rascunho. Abrir o editor → a faixa do mood aparece selecionada (coerência). Reordenar 2 cenas → exportar. Rodar `ffprobe storage/output/{job}.mp4 -show_streams` e ouvir: **whoosh presente e sincronizado** + música no MP4 exportado.

- [ ] **Step 5: E2E — toggles off**

Gerar com **SFX off + Música off** → confirmar ausência de whoosh e de música no rascunho e no export.

- [ ] **Step 6: E2E — diálogo pt-BR**

Gerar com template `dialogue_duo` → ouvir: as 2 vozes em **pt-BR sem sotaque** (não Rachel/Adam).

- [ ] **Step 7: Relatório**

Reportar: contagem de testes (antes/depois), resultado do tsc, e o resultado de cada checagem E2E com evidência (caminho do MP4 + observação do ffprobe/áudio). Não integrar no `main` — aguarda decisão do Gui.

---

## Self-Review

- **Cobertura do spec:** flags por job (T1) ✓; geração honra flags (T2) ✓; SFX sobrevive ao export (T3) ✓; música default no export (T3) ✓; coerência música no editor (T4) ✓; toggles no dashboard (T5) ✓; vozes pt-BR diálogo (T6) ✓; descoberta de vozes (T6) ✓; verificação E2E (T7) ✓. **Fora de escopo** mantido fora: UI de seleção de voz do diálogo, UI de Voice Design, SFX nativo no Remotion, mudanças no `ai_video`.
- **Sem migration:** flags Redis-only — confirmado, nenhuma task mexe em Alembic/Job model.
- **Consistência de tipos:** `resolve_job_flag(redis, job_id, key, default)` mesma assinatura em T1/T2/T3/T4. `auto_music_url`/`resolve_music_path` definidos em T2 e consumidos em T3/T4. `build_composition_props(..., audio_filename, default_music_url)` e `invoke_remotion_render(..., audio_filename, default_music_url)` definidos em T3 e usados de forma consistente. `music_url`/`music_volume` no `CompositionResponse` (T4) batem com o consumo no `fetchComposition` (T4).
- **Riscos:** (a) `mix_transitions` no re-render exige `narration.wav` íntegro — já validado existir em `task_rerender_video`; sem `ELEVENLABS_API_KEY` vira no-op e `audio_basename` cai p/ `narration.wav` (correto). (b) Reordenar cenas: re-mix usa `script.json` (que o auto-save atualiza) → durações atuais. (c) Postgres compartilhado: nenhuma migration, sem risco de heads. (d) Reiniciar worker/backend após mudanças Python.
