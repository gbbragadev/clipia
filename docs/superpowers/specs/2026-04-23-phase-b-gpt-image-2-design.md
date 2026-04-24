# Fase B — gpt-image-2 + Template Novelinha Histórica

**Data:** 2026-04-23
**Branch de partida:** `feat/phase-a-windows-resurrection` (commit `27a945a`)
**Autor:** Gui + Claude (sessão brainstorming)
**Pré-requisito:** Fase A concluída (pipeline end-to-end funcional com Pexels + ElevenLabs + Groq ASR)

---

## 1. Objetivo

Substituir a dependência de Pexels por imagens geradas por IA (`gpt-image-2`) como mídia primária do primeiro template "premium" (`novelinha_historica`) — drama histórico narrado no estilo de canais tipo "Tramas Cinematográficas". Validar se o salto visual é suficiente para sair do baseline MVP (handoff 2.1).

Escopo fechado para **1 template novo** com 1 nicho (drama histórico). Não cria múltiplos templates nem automatiza postagem (Fase C).

---

## 2. Resumo das decisões de escopo

| Tópico | Decisão |
|---|---|
| Escopo | Full handoff (provider + task Celery + template + `visual_hint` no script + Ken Burns + testes + 3 vídeos de validação) |
| Modelo | `gpt-image-2` (snapshot `gpt-image-2-2026-04-21`) |
| Qualidade default | `medium` em prod, `low` em dev (env var `GPT_IMAGE_QUALITY`) |
| Tamanho | `1024x1536` (portrait 2:3) |
| Moderação | `moderation="low"` (valor mais permissivo da API) |
| Tema do template | Drama histórico narrado (`novelinha_historica`) |
| Cenas por vídeo | 6 (fixo) |
| Falha | Fail-fast + retry 3x para 429/5xx/timeout; sem fallback silencioso |
| Voz | `TODO_VOICE_ID` (placeholder ElevenLabs; Gui preenche antes do 1º vídeo real) |
| Ken Burns | Zoom alternado in/out por índice de cena, 1.0 ↔ 1.15 em 5s |
| Cache | SHA-256 de `(prompt, size, quality)` em `storage/image-cache/` |

---

## 3. Arquitetura de alto nível

### 3.1 Pipeline novo

```
generate_script  →  generate_images  →  synthesize_audio  →  transcribe  →  fetch_media  →  compose  →  finalize
                   └── NOVO ──┘
```

`generate_images` é inserido entre `generate_script` e `synthesize_audio`. Motivo: se moderação bloquear, falhamos antes de gastar ElevenLabs (char budget mensal) e Groq (rate limits free tier).

### 3.2 Componentes criados/modificados

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `app/services/image_provider.py` | **novo** | Cliente OpenAI gpt-image-2, cache SHA-256, retry |
| `app/templates.py` | modificar | Template `novelinha_historica`, expansão de `MediaStrategy` e `ScriptConfig` |
| `app/services/scriptwriter.py` | modificar | Injetar instrução `visual_hint` quando template exigir; validar output |
| `app/worker/tasks.py` | modificar | Adicionar `task_generate_images`, inserir no chain, early return em `fetch_media` |
| `app/services/compositor.py` | modificar | Rota Ken Burns em `_prepare_scene` para imagens estáticas (PNG/JPG/WebP) |
| `app/config.py` | modificar | Nova env var `GPT_IMAGE_QUALITY` (default `medium`) |
| `tests/services/test_image_provider.py` | **novo** | Cache, retry, moderation, provider error |
| `tests/worker/test_tasks_generate_images.py` | **novo** | Skip por template, writes imagens, propagação no chain |
| `tests/services/test_compositor_ken_burns.py` | **novo** | Route por extensão, zoompan, alternância por índice |
| `tests/services/test_scriptwriter_visual_hint.py` | **novo** | Inclusão condicional da instrução; validação de output |

### 3.3 Storage layout

```
storage/
├── jobs/{id}/
│   ├── script.json          # agora inclui visual_hint por cena
│   ├── images/              # NOVO
│   │   ├── scene_1.png
│   │   ├── scene_2.png
│   │   └── ...
│   ├── narration.wav
│   ├── words.json
│   └── final.mp4
└── image-cache/             # NOVO — compartilhado entre jobs
    └── {sha256}.png
```

### 3.4 Status Redis

Novo `current_step` = `"generating_images"`. Progresso granular por cena no campo `detail`:
```
job:{id} current_step=generating_images progress=0.22 detail="Imagem 3/6 OK"
```

---

## 4. `OpenAIImageProvider`

### 4.1 Interface

```python
# app/services/image_provider.py

class ModerationBlockedError(Exception):
    """Raised when OpenAI content moderation blocks the prompt."""

class ImageProviderError(Exception):
    """Raised after retries are exhausted on transient failures."""


class OpenAIImageProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-image-2",
        quality: str = "medium",
        size: str = "1024x1536",
        moderation: str = "low",
        cache_dir: Path | None = None,
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ): ...

    def generate(self, prompt: str, output_path: Path) -> Path: ...
```

### 4.2 Decisões

- **Síncrono** — Celery `--pool=solo` é single-threaded; sem ganho em async.
- **Cache** — chave SHA-256 de `f"{prompt}|{size}|{quality}"`. Hit = `shutil.copy` do cache pra `output_path`. Miss = chama API, escreve cache, copia.
- **Retry** — backoff exponencial 1s/2s/4s apenas em `APIStatusError` (429/5xx) e `APITimeoutError`. `BadRequestError` com moderation → `ModerationBlockedError` imediato (sem retry).
- **Response parsing** — `resp.data[0].b64_json` → `base64.b64decode` → `Path.write_bytes`.
- **Moderation** — hardcoded `"low"` (decisão de produto, não operacional).

### 4.3 Não faz (YAGNI)

- Async (`agenerate`)
- Batching (`n > 1` não economiza, gpt-image-2 cobra por imagem)
- Fallback para outro provider
- Prompt engineering automático (visual_hint já vem pronto do Claude)
- Suporte a `images.edits`

---

## 5. Template `novelinha_historica` + ScriptWriter

### 5.1 Expansão de `MediaStrategy` e `ScriptConfig`

```python
@dataclass(frozen=True)
class MediaStrategy:
    source: str  # "pexels" | "local" | "ai_image"
    library_tag: str | None = None
    loop_single: bool = False
    # Novos (relevantes quando source == "ai_image"):
    image_quality: str = "medium"
    image_size: str = "1024x1536"
    style_suffix: str = ""
    ken_burns: bool = False


@dataclass(frozen=True)
class ScriptConfig:
    prompt_extra: str
    needs_keywords: bool = True
    needs_visual_hint: bool = False  # novo
    word_rate: float = 2.05
```

### 5.2 Template

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

### 5.3 ScriptWriter — injeção de `visual_hint`

Instrução adicional aplicada quando `template.script.needs_visual_hint == True`:

```
REGRAS DE VISUAL_HINT:
- Cada cena tem campo "visual_hint": descrição em português de uma imagem única
- Deve ser CONCRETA: objetos, pessoas, ambiente, iluminação, ângulo
- Evite texto, logos, rostos em close extremo
- Cenas diferentes = imagens claramente diferentes
```

JSON exemplar no prompt ganha o campo:
```json
{
  "text": "...",
  "visual_hint": "descrição concreta da cena",
  "duration_hint": 5
}
```

Validação pós-geração: se alguma cena vem sem `visual_hint` (ou string vazia), retry uma vez pedindo explicitamente o preenchimento. Segunda falha → `ScriptValidationError`.

### 5.4 Prompt final ao gpt-image-2

Concatenação vive na **task**, não no provider:
```python
full_prompt = f"{scene['visual_hint']}, {template.media.style_suffix}"
provider.generate(full_prompt, output_path=job_dir / f"scene_{i+1}.png")
```

---

## 6. Task `task_generate_images`

### 6.1 Assinatura e chain

```python
pipeline = chain(
    task_generate_script.s(job_id, topic, style, duration_target, template_id),
    task_generate_images.s(job_id, template_id),        # NOVO
    task_synthesize_audio.s(job_id, template_id),
    task_transcribe_audio.s(job_id),
    task_fetch_media.s(job_id, template_id),
    task_compose_video.s(job_id, template_id),
    task_finalize.s(job_id),
)
```

### 6.2 Corpo

```python
@celery_app.task(name="generate_images", bind=True)
def task_generate_images(self, data: dict, job_id: str, template_id: str) -> dict:
    try:
        _check_cancelled(job_id)
        template = get_template(template_id)

        if template.media.source != "ai_image":
            logger.info(f"Job {job_id}: template {template_id} não usa ai_image, skip")
            return data

        script = data.get("script") or json.loads(
            (get_job_dir(job_id) / "script.json").read_text(encoding="utf-8")
        )
        scenes = script["scenes"]

        _update_job(job_id, "processing", "generating_images", 0.15,
                    detail=f"Gerando {len(scenes)} imagens...")

        quality_override = settings.GPT_IMAGE_QUALITY or template.media.image_quality
        provider = OpenAIImageProvider(
            quality=quality_override,
            size=template.media.image_size,
        )

        job_img_dir = get_job_dir(job_id) / "images"
        job_img_dir.mkdir(exist_ok=True)

        image_paths: list[str] = []
        for i, scene in enumerate(scenes):
            _check_cancelled(job_id)
            hint = scene.get("visual_hint", "").strip()
            if not hint:
                raise ValueError(f"cena {i+1} sem visual_hint")

            full_prompt = f"{hint}, {template.media.style_suffix}"
            out_path = job_img_dir / f"scene_{i+1}.png"
            provider.generate(full_prompt, out_path)

            image_paths.append(str(out_path))
            progress = 0.15 + (0.15 * (i + 1) / len(scenes))
            _update_job(job_id, "processing", "generating_images", progress,
                        detail=f"Imagem {i+1}/{len(scenes)} OK")

        data["image_paths"] = image_paths
        return data

    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_images")
        raise
    except ModerationBlockedError as e:
        _fail_job(job_id, f"Conteúdo bloqueado pela moderação: {e}")
        raise
    except Exception as e:
        _fail_job(job_id, f"Falha ao gerar imagens: {e}")
        raise
```

### 6.3 Ajuste em `task_fetch_media`

Early return no topo:
```python
if template.media.source == "ai_image":
    data["media_paths"] = data.get("image_paths", [])
    return data
```

Compositor passa a receber `media_paths` preenchido com PNGs — a ramificação imagem/vídeo vive apenas no compositor, discriminada por extensão.

---

## 7. Compositor — Ken Burns

### 7.1 Router por extensão em `_prepare_scene`

```python
def _prepare_scene(media_path: str, duration: float, output_clip: str, scene_index: int = 0) -> None:
    ext = Path(media_path).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        _prepare_static_image(media_path, duration, output_clip, scene_index)
    else:
        _prepare_video_scene(media_path, duration, output_clip)  # lógica atual, renomeada
```

### 7.2 `_prepare_static_image`

```python
def _prepare_static_image(
    img_path: str, duration: float, output_clip: str, scene_index: int
) -> None:
    fps = 25
    frames = int(round(duration * fps))
    zoom_in = scene_index % 2 == 0
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

**Path escape**: PNG entra como `-i` direto, sem escape. Escape só se aparecer dentro de filtergraph (não é o caso aqui — `zoompan` referencia só o input já lido).

**Fullscreen vf_chain (linha 523 do compositor atual)**: zero mudança. Efeito Ken Burns fica embutido no clip MP4 que sai de `_prepare_scene`.

---

## 8. Testes (TDD)

### 8.1 `tests/services/test_image_provider.py`
- `test_generate_writes_png_to_output`
- `test_generate_uses_cache_on_second_identical_call`
- `test_generate_retries_on_rate_limit_429`
- `test_generate_raises_moderation_blocked_on_bad_request`
- `test_generate_raises_provider_error_after_max_retries`
- `test_cache_key_includes_quality_and_size`

### 8.2 `tests/worker/test_tasks_generate_images.py`
- `test_task_skips_when_template_is_not_ai_image`
- `test_task_writes_images_and_populates_image_paths`
- `test_task_fails_job_on_moderation_block`
- `test_task_respects_cancellation_between_scenes`
- `test_fetch_media_reuses_image_paths_when_ai_image`

### 8.3 `tests/services/test_compositor_ken_burns.py`
- `test_prepare_scene_routes_png_to_static_image`
- `test_prepare_scene_routes_mp4_to_video_scene`
- `test_static_image_uses_loop_and_zoompan`
- `test_static_image_alternates_direction_by_index`

### 8.4 `tests/services/test_scriptwriter_visual_hint.py`
- `test_includes_visual_hint_instruction_when_template_requires`
- `test_rejects_script_with_empty_visual_hint_for_ai_image_template`
- `test_does_not_add_visual_hint_for_stock_template`

### 8.5 Testes existentes afetados
- `tests/services/test_scriptwriter.py` — assert que templates stock não ganham `visual_hint`.
- `tests/worker/test_tasks.py` — chain passa de 6 para 7 tasks.

### 8.6 Fixture compartilhada

```python
# tests/conftest.py
import base64

@pytest.fixture
def tiny_png_b64() -> str:
    return base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 60).decode()
```

---

## 9. Configuração nova

### 9.1 `app/config.py`

```python
GPT_IMAGE_QUALITY: str = "medium"  # "low" | "medium" | "high"
```

### 9.2 `.env.example`

```
# GPT Image 2 quality override. low=$0.005/img, medium=$0.041/img, high=$0.165/img.
GPT_IMAGE_QUALITY=medium
```

### 9.3 Env vars existentes reutilizadas
- `OPENAI_API_KEY` (alias de `OPEN_API_CLIPIA_TOKEN`, já setado em User scope).

---

## 10. Budget & critérios de sucesso

### 10.1 Gasto projetado até a decisão go/no-go

| Fase | Qualidade | Volume | Custo |
|---|---|---|---|
| Suite TDD (smoke) | low | ~10 imgs | $0.05 |
| Primeiro end-to-end completo | low | 6 imgs | $0.03 |
| 3 vídeos de validação medium | medium | 18 imgs | $0.74 |
| Buffer iteração | medium | ~20 imgs | $0.82 |
| **Total Fase B** | | | **~$1.64** |
| **Sobra do budget $10** | | | **~$8.36** |

### 10.2 Critérios go/no-go (documentados em `docs/reports/phase-b-validation.md` após a implementação)

1. Pipeline end-to-end roda sem erro em 3 vídeos consecutivos de `novelinha_historica`.
2. Pelo menos 2 dos 3 vídeos têm qualidade visual aceitável (avaliação subjetiva com nota 1-5).
3. Nenhum vídeo disparou moderation em 6/6 cenas (1-2 bloqueios/vídeo = OK).
4. Custo médio real bate com estimado ($0.25 ± $0.10).
5. Latência total ≤ 90s por vídeo.

### 10.3 Fork pós-validação

- **Passa** → Fase B.2 adiciona template `curiosidade_cientifica` + `mitologia`.
- **Não passa** → congelar, documentar o que falhou, seguir para Fase C com `stock_narration` validado.

---

## 11. Fora de escopo (Fase B.2 ou posterior)

- Fallback com Claude reescrevendo prompts bloqueados por moderation.
- Fallback silencioso para Pexels.
- Templates adicionais (curiosidades científicas, mitologia, folclore).
- Paralelização das 6 calls de imagem (asyncio.gather).
- `output_compression` para reduzir disco (PNG para JPEG).
- Upscaling de 1024 para 1080 com modelo dedicado (scale FFmpeg é suficiente).
- YouTube/TikTok auto-upload (Fase C).
- Editor Remotion ganhando suporte visual a imagens AI (só ativar quando houver demanda real).

---

## 12. Riscos conhecidos

1. **Moderação bloqueando demais** — drama histórico tem tema sensível. Mitigação: `moderation="low"` + prompts já cuidadosos ("retrato histórico", "pintura clássica"). Se bloqueio > 20% após 3 vídeos, abrir Fase B.2 para rewrite automático.
2. **Qualidade medium insuficiente** — se hook de 3s não prende. Mitigação: criterio 2 de 10.2 pega isso. Se falhar, testar `high` só na cena 1 antes de abandonar.
3. **Rate limit OpenAI** — Tier 1 = 5 imagens/min. Com 6 cenas sequenciais a 3s cada, ficamos em ~2 imagens/min de throughput. Sem risco em execução normal. Problema apenas se alguém rodar 3 jobs concorrentes — não vai acontecer em creator-first.
4. **Consistência visual entre cenas** — gpt-image-2 não tem character consistency. Mitigação já embutida: drama histórico usa cenas factuais diferentes, não mesmo personagem em close-up.
5. **TODO_VOICE_ID esquecido** — job falha ruidosamente com 404 da ElevenLabs. Proposital (fail-fast).

---

## 13. Sequência de implementação (para o writing-plans)

1. Provider `OpenAIImageProvider` + testes (TDD).
2. Expansão de `MediaStrategy` + `ScriptConfig` + template `novelinha_historica`.
3. ScriptWriter com `visual_hint`.
4. Task `task_generate_images` + chain + early return em `fetch_media`.
5. Compositor com router + `_prepare_static_image`.
6. `GPT_IMAGE_QUALITY` no config + `.env.example`.
7. Suite completa de testes + atualização dos existentes.
8. Smoke test real: 1 vídeo `novelinha_historica` end-to-end (quality=low).
9. 3 vídeos de validação medium + `docs/reports/phase-b-validation.md`.
10. Decisão go/no-go registrada.
