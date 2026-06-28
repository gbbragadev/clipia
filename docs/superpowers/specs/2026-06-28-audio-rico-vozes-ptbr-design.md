# Spec — Áudio rico por job + Vozes pt-BR no diálogo

> Design aprovado em 2026-06-28 (brainstorming). Branch isolada `feat/audio-rico-vozes-ptbr`
> (worktree). Integração no `main` só após o commit da sessão concorrente `ai_video`.

## Problema / motivação

O ClipIA (clipia.com.br, deploy local) tem dois recursos prontos no backend mas subexpostos
(ROADMAP §3, quick wins #1 e #2):

1. **Áudio rico sem controle por-vídeo.** SFX (whoosh nas transições, `app/services/sfx.py`) e
   música automática por mood (`app/services/music.py`) ligam só por flag **global** de config
   (`SFX_ENABLED`, `AUTO_MUSIC_ENABLED`). O creator não decide por vídeo. Pior: o **whoosh some no
   export editado** — o re-render Remotion (`task_rerender_video`) usa `narration.wav` cru, não o
   `narration_sfx.wav`. Isso quebra a fidelidade editor==export (valor central do produto).
2. **Diálogo com sotaque.** O template `dialogue_duo` sintetiza com `DIALOGUE_VOICE_A/B` =
   Rachel/Adam (premade EN) — falam pt-BR com sotaque.

## Resultado pretendido

- Creator controla **SFX on/off** e **Música on/off** por vídeo (no dashboard), persistido por job.
- O **whoosh sobrevive ao export editado**, sincronizado mesmo após reordenar cenas.
- O editor abre **coerente** com a música que a geração aplicou.
- O diálogo sai em **pt-BR natural** (vozes da conta ElevenLabs).
- Tudo **reusando** o backend existente (`mix_transitions`, `resolve_auto_music`, `GET /voices`).
  Nenhum provider/serviço novo.

## Restrições

- pt-BR sempre; código enxuto, creator-first.
- **Não** tocar na feature `ai_video` da sessão concorrente.
- Postgres/Redis são compartilhados (docker): migrations só-aditivas nullable; checar `alembic heads`
  na integração.
- Celery `--pool=solo` sem hot-reload → reiniciar worker+backend após mudar código/config.
- Next.js 16: `npx next typegen` antes de `tsc --noEmit`.

---

## Componentes e mudanças

### Feature 1 — Áudio rico por job

**1a. UI (dashboard).** `frontend/src/components/dashboard/GenerateForm.tsx`: bloco "Áudio" com 2
toggles ("Efeitos sonoros nas transições", "Música de fundo"), default visual ligado, estilo
consistente com o editor. Envia `sfx_enabled`/`music_enabled` (boolean) no payload de
`generateVideo()` → `POST /api/v1/jobs/generate`. Tipos em `frontend/src/lib/*` (`GenerateParams`).

**1b. Dados (por job).**
- `app/models.py` `GenerateRequest`: `sfx_enabled: bool | None = None`, `music_enabled: bool | None = None`.
- `app/db/models.py` `Job`: colunas `sfx_enabled` / `music_enabled` (`Boolean`, nullable; `None`=global).
- Migration Alembic aditiva (`op.add_column("jobs", ...)`).
- `app/api/routes.py` `POST /jobs/generate`: gravar os flags no `Job` **e** no Redis job hash (mesmo
  lugar de `template_id`; o re-render lê via `_redis_hget`).

**1c. Geração respeita os flags.** `app/worker/tasks.py`:
- `dispatch_pipeline`: propagar os flags ao Redis hset (editar só signature/hset — região vizinha à
  chain que a sessão `ai_video` alterou).
- `task_compose_video`: resolver SFX/música por job (Redis → fallback `settings`). Música off →
  `music_path=None` (não volume 0). SFX off → áudio cru.

**1d. SFX no export (ponto técnico central).** `task_rerender_video` + `app/services/remotion.py`:
- Se SFX habilitado por job, **re-mixar** com as durações **atuais** do `editor_state`
  (`mix_transitions(áudio_atual, scene_durs, narration_sfx.wav)`) — re-mixar (não reusar o arquivo
  antigo) evita dessincronizar ao reordenar cenas. Mixar sobre o **áudio atual** (pode ser TTS regen).
- `build_composition_props`/`invoke_remotion_render`: apontar o `audioUrl` do Remotion para
  `narration_sfx.wav` quando existir no re-render. **VALIDAR PRIMEIRO** como `audioUrl` é montado hoje.

**1e. Coerência da música no editor.** `build_composition_props` inicial: setar
`musicUrl = /music/{TEMPLATE_MOODS[template_id]}.mp3` (mapa em `app/services/music.py`) quando música
habilitada, e alinhar o `musicVolume` default com `AUTO_MUSIC_VOLUME` (0.12).

### Feature 2 — Vozes pt-BR no diálogo (só config)

**2a. Descoberta.** Rodar `GET /api/v1/voices` (ou `ElevenLabsProvider().list_voices()`). Identificar 2
vozes pt-BR: Fernanda `KHmfNHtEjHhLK9eER20w` (feminina, candidata) + uma masculina. Gotcha: `language`
vem `"multilingual"` — avaliar por nome/preview. Fallback: Voice Design ou premade multilingual aceitável.
Confirmar a masculina com o Gui antes de fixar.

**2b. Aplicar.** `app/config.py:68-69` trocar `DIALOGUE_VOICE_A/B` pelos ids pt-BR (override por env
mantido; documentar no `.env.example`). `app/templates.py` `dialogue_duo`: atualizar o `voice_id`
cosmético para `settings.DIALOGUE_VOICE_A`.

---

## Testes

- Backend (`pytest -q`, venv do worktree): flags por job no Redis (None→fallback); `task_compose_video`
  (música off→`music_path=None`, SFX off→áudio cru); **re-render aplica SFX** (`narration_sfx.wav`
  recriado, `audioUrl` aponta pra ele); defaults de `DIALOGUE_VOICE_A/B` != ids EN antigos.
- Frontend: `npx next typegen` → `npx tsc --noEmit`.

## Verificação end-to-end (manual)

Subir stack (reiniciar worker+backend) → gerar com SFX+música on (conferir whoosh+música) → editor
abre com a faixa do mood → reordenar 2 cenas → exportar → `ffprobe` + ouvir: whoosh **sobrevive** e
sincronizado → `dialogue_duo` em pt-BR sem sotaque → gerar com SFX/música off confirma ausência.

## Fora de escopo

UI de seleção de vozes do diálogo; UI de Voice Design; SFX como camada nativa Remotion; qualquer
mudança em `ai_video`.
