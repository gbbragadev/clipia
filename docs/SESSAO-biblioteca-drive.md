# Sessão completa — Biblioteca do Drive + Semântica CLIP (ClipIA)

> Export da sessão (28-29/06/2026) + continuação (01/07/2026). Relatório narrativo detalhado para archive/continuidade. Branch: `feat/biblioteca-drive-multi-tag`.

---

## 1. Objetivo (o pedido original)

O ClipIA tem templates de vídeo que usam clips de **fundo** de uma biblioteca local (`storage/library/<tag>/`). A seleção era **burra**: `random.choice` de uma pasta que estava **vazia** → templates quebravam ("No clips in library"). O Gui tem um Google Drive com milhares de clips de b-roll.

**Pedido:** transformar a biblioteca numa **base pesquisável por significado** — inventariar o Drive, catalogar, embeddar (CLIP) e buscar o clip mais relevante pro tema/cena (em vez de aleatório). Embeddings locais na GTX 1660 (batch one-time).

## 2. Linha do tempo (o que aconteceu)

### Fase 0 — Setup e descoberta
- **Briefing** (`docs/briefing-biblioteca-drive-glm.md`): fases A–E (inventário → índice → categorização → embeddings → busca). Trazia um erro: dizia "sem GPU" — a máquina **tem GTX 1660 4GB** (CUDA). Corrigido.
- **Branch obsoleta detectada:** `feat/fluxo-unificado-drive` só tinha specs e estava ~atrasada do main (sem trends/quality/elevenlabs/etc.). Decisão: trabalhar sobre `main`, em branch nova.
- **rclone setup confirmado:** remote `gdrive` (OAuth do Gui), binário winget fora do PATH.
- **Mecânica-chave descoberta:** pasta compartilhada via link se acessa com `rclone lsf gdrive: --drive-root-folder-id={ID}` — o path por ID (`gdrive:{ID}`) falha "directory not found". Isso destravou catalogar pastas por ID sem o Gui adicionar nada ao Drive.

### Fase A — Inventário do Drive (reinventariar)
- Gui forneceu ~70+ links de pastas compartilhadas categorizadas (satisfying, lifestyle, cinematic, veículos, fitness, memes, podcasts, etc.) + Notion + gdoc jetflix.
- **Resultado:** ~4000 clips validados (mp4 real) em dezenas de categorias; a recursão (`--recursive`) revelou muito mais (STOCK VIDEOS 1855 em subpastas, etc.). Total: **7403 clips em 10 tags**.
- **Gameplay (parkour Minecraft / surf CS): AUSENTE do Drive**, confirmado (CPU BF6 = crack; "Counter Strike" = mapa de jogo, não footage; gdoc jetflix parcialmente morto — "Link Trocado!").
- Decisão do Gui: **nicho fixo por template** (repropósito dos 3 gameplay) + aguardar gameplay real pra depois.

### Fase B — Base do catálogo (`drive_library.py`)
- Catálogo SQLite (`storage/drive_index.db`), `FOLDER_TAG_MAP: dict[str, list[str]]` (tag → folder-IDs), `list_remote_clips` (recursivo), `index_folder`/`index_all`, cache sob demanda (`_ensure_cached`), `pick_drive_clip`, `count_for_tag`.
- `media_library.pick_clip` cai no Drive quando a pasta local está vazia; `count_clips` = local + Drive.
- CLI `scripts/index_drive_library.py` (cataloga). Indexação real: **7403 clips**.
- `pick_drive_clip('cinematic')` validado: baixou `297.mp4` pro cache, funcionou.

### Fase B' — Repropósito templates
- `gameplay_split`→cinematic, `character_narration`→satisfying, `dialogue_duo`→podcast. `story_time`→satisfying (mantém). `loop_single=False` nos 4 local (ativa per-cena depois).

### Fase B'' — E2E inicial (bloqueou)
- Subiu backend+worker, rodou `validate_readiness` com `story_time`. Passou scripting, **falhou no TTS** (`WinError 2`). Causa: `tts.py:_fit_to_duration` chama `ffprobe`/`ffmpeg` via subprocess, e **ffmpeg não estava no PATH** (winget não adiciona). Fix: ffmpeg (Gyan.FFmpeg winget) adicionado ao User PATH; worker reiniciado.

### Fase C-D — Camada semântica CLIP (cuda)
- Instalado `torch 2.6.0+cu124` (cuda=True, GTX 1660) + `sentence-transformers 5.6.0` no venv `.venv312`.
- `drive_library.py` estendido: coluna `embedding` (BLOB float32), `_get_clip_model` (ViT-B/32 cuda, lazy), `_extract_frame` (ffmpeg, frame do meio), `index_embeddings(tag, limit)`, `search_clips(query, tag, k, exclude)` (cosine; fallback aleatório).
- **5 bugs silent resolvidos** (ver seção 5) pra conseguir indexar 30 clips de satisfying.
- `search_clips` validado: 3 queries contrastantes (ocean waves / fire / slime) retornaram top-3 **distintos** → semântica ativa (não random).

### Fase E — Integração no pipeline
- `task_fetch_media` (worker/tasks.py) ramo `source=="local"` reescrito: **per-cena** — `search_clips(visual_hint/keywords_en[0]/text/topic, tag, k=1, exclude=used_names)` + fallback `pick_clip`. Query cascateada (story_time não tem visual_hint/keywords → cai no `text`/topic).
- CLI `scripts/index_library.py [tag] [limit]` (embedda idempotente).

### Fase F — Commit, agendamento, E2E final
- **Commits:** `f2fbe1f` (feature) + `1dac5be` (script overnight). Pre-commit `ruff-format` reformatou (re-add + commit).
- **Scheduled task** `ClipIA Index Overnight` → 30/06 3h AM (`Register-ScheduledTask`, `StartWhenAvailable`+`WakeToRun`).
- **E2E verde:** `validate_readiness` (story_time) ponta-a-ponta → **MP4 5.97 MB** com fundo do Drive semântico per-cena.
- **MP4 enviado no zap** do Gui via `/enviarwpp` (Evolution API).

### Continuação (01/07 — registrada no handoff atualizado)
- Indexação overnight (30/06 3h) **abortou**: `subprocess.TimeoutExpired` no `rclone copy` (timeout 300s padrão); o `.ps1` mascarava o exit code (resultado 0).
- **Fix `drive_library.py`:** `_rclone(timeout=...)` captura timeout como processo `returncode=124` (não exceção); `_download_batch` quebra em lotes de 100, usa `--tpslimit 2`, `--retries 5`, `--low-level-retries 20`, timeout 1800s, averte quando Drive retorna sucesso baixando 0.
- **Fix `index_all_overnight.ps1`:** `*>> $log` (sem pipeline quebrar exit), grava `fim (exit=N)`, `exit $exitCode`.
- `tests/test_drive_library.py` agora **5 passed** (timeout + chunk). Smoke: `index_library.py satisfying 1` embeddou 1 novo.
- Indexação completa **reiniciada manual 01/07 19:04** via `index_all_overnight.ps1`. Monitorar.

## 3. Decisões-chave (com racional)

| Decisão | Racional |
|---|---|
| Trabalhar sobre `main`, não `feat/fluxo-unificado-drive` | Branch obsoleta (só specs, atrasada). |
| `--drive-root-folder-id` em vez de path por ID | Path por ID falha; root-folder-id acessa pastas compartilhadas via link. |
| `FOLDER_TAG_MAP: dict[str, list[str]]` (multi-tag) | Uma tag pode vir de várias pastas (ex: satisfying = PACK1 + PACK3 + 40 Virais). |
| Indexação recursiva (`--recursive --files-only`) | Subpastas escondiam 60% do acervo (STOCK 1855, etc.). |
| Repropósito templates (nicho fixo) em vez de semântica cross-tag | Gameplay ausente do Drive; nicho fixo destrava com acervo real HOJE. |
| 1 clip/cena + pool anti-repetição (`loop_single=False`) | Variação visual coerente (pedido do Gui). |
| CLIP cuda (GTX 1660), batch one-time | Gui endorsou GPU; batch one-time não pesa em runtime (numpy). |
| `--files-from` batch na indexação | Evita rate-limit do Drive (1 listagem por pasta vs 2392 por `--include`). |
| Agendamento madrugada (schtasks) | Indexação completa (~11GB, horas) não bloqueia o PC durante uso. |

## 4. Implementação (arquivos)

| Arquivo | Função |
|---|---|
| `app/services/drive_library.py` | Catálogo SQLite + cache + semântica CLIP + `search_clips`. |
| `app/services/media_library.py` | `pick_clip` (fallback Drive) + `count_clips`. |
| `app/worker/tasks.py` (`task_fetch_media`) | Ramo `local` per-cena semântico + fallback. |
| `app/templates.py` | `loop_single=False`; tags repropósito (cinematic/satisfying/podcast). |
| `app/config.py` | `RCLONE_EXE`, `RCLONE_REMOTE`. |
| `scripts/_run-worker.ps1` | Prelude copia `RCLONE_EXE` do User scope. |
| `scripts/index_drive_library.py` | Cataloga pastas → SQLite. |
| `scripts/index_library.py` | Embedda (idempotente, GPU). |
| `scripts/index_all_overnight.ps1` | Batch noturno (loga, propaga exit). |
| `tests/test_drive_library.py` | 5 testes offline (mock rclone, timeout, chunk). |
| `docs/drive-sources-catalog.md` | Mapa fontes Drive (categorias → folder-IDs). |
| `docs/briefing-biblioteca-drive-glm.md` | Briefing original (GPU corrigido). |
| `docs/HANDOFF-biblioteca-drive.md` | Handoff pra próxima LLM (atualizado 01/07). |

## 5. Bugs resolvidos (sintoma → causa → fix) — o mais valioso pra continuidade

1. **`UnicodeDecodeError` cp1252 no index** → `subprocess` decodificava stdout do rclone como cp1252 (default Win). **Fix:** `encoding="utf-8", errors="replace"` no `_rclone`.
2. **Mojibake nos names** (`Ó` → `Ã"`) → a indexação original pegou cp1252 antes do fix; o `--files-from`/`--include` não matcheava os names corrompidos → **baixava 0 silenciosamente** (rc=0, stderr vazio). **Fix:** apagar `drive_index.db` + re-indexar (utf-8). Diagnóstico: comparar `name.encode('utf-8')` do SQL vs `list_remote_clips` (live é o correto).
3. **Rate-limit do Drive (0 baixados em batch)** → `--include` lista a pasta inteira (PACK1 2392 = ~17s) a cada chamada; 50 copies seguidos throttleavam. **Fix:** `_download_batch` com `--files-from` (1 listagem por pasta). Depois (01/07): chunks de 100 + `--tpslimit 2` + retries.
4. **`\r\n` no files-from** → `NamedTemporaryFile("w")` em modo texto Win converte `\n`→`\r\n`; rclone trata `\r` como parte do nome → não matcheia. **Fix:** `newline=""`.
5. **`WinError 2` no TTS/frame-extract** → ffmpeg/ffprobe (winget) fora do PATH. **Fix:** adicionar ao User PATH; scripts standalone setam `$env:Path`. Cada call PowerShell do tool é sessão nova (env stale).
6. **Timeout do rclone aborta indexação overnight** (01/07) → `subprocess.run(timeout=300)` levanta `TimeoutExpired` sem tratamento; `.ps1` mascarava exit. **Fix:** `_rclone` captura timeout como `returncode=124`; `_download_batch` timeout 1800s; `.ps1` propaga `exit $exitCode`.
7. **lean-ctx bloqueia `Remove-Item`, `git -C`, aspas em `git -m`** → PS interpreta `(drive)` como subexpressão. **Fix:** `git commit -F <arquivo>`; `Register-ScheduledTask` (cmdlet) passa.

## 6. Validações

- **279 testes** pytest verdes (3 novos offline; 5 após continuação 01/07).
- **Indexação real:** 7403 clips catalogados; `pick_drive_clip('cinematic')` baixou `297.mp4` (fetch+cache OK).
- **Semântica validada:** 30 clips satisfying embeddados (cuda ~40 it/s); `search_clips` retornou top-3 distintos por query (ocean/fire/slime).
- **E2E verde:** `validate_readiness` (story_time) → MP4 5.97 MB (cadastro→OTP→video com fundo Drive semântico per-cena).
- **Entrega:** MP4 enviado no zap do Gui via Evolution API.

## 7. Estado final (01/07)

- **Catálogo:** 7403 clips / 10 tags (satisfying 3164, stock 1855, lifestyle 1093, cinematic 656, fails 114, fitness 194, podcast 161, humor 97, impactantes 37, nature 31).
- **Embeddings:** ~31 de satisfying (validação) + indexação completa em andamento (reiniciada 01/07 19:04).
- **Commits:** `f2fbe1f` + `1dac5be` (local, não pushed).
- **Ambiente:** backend+worker rodando (código novo); rclone/torch+CUDA/ffmpeg configured; scheduled task registrada.
- **Memórias:** `biblioteca-midia-drive.md` (estado final), `sem-gpu-local.md` (corrigida — GTX 1660), `MEMORY.md` (índice).

## 8. Próximos passos (priorizados)

1. **Indexação completa** (em andamento 01/07, ou re-agendar) — ~7000 clips, horas. Monitorar `storage/index_overnight.log`. Depois: `search_clips` com variedade real.
2. **Push da branch** `feat/biblioteca-drive-multi-tag` + PR (quando o Gui liberar).
3. **Deploy prod** — rclone + `RCLONE_EXE` no `start-production.ps1` + torch+CUDA em prod (hoje dev=prod no PC do Gui).
4. **Gameplay real** (parkour MC / surf CS) — quando o Gui subir, adicionar tag `minecraft_parkour` no `FOLDER_TAG_MAP` + indexar; reverter os 3 templates pro nicho gameplay.
5. **Fluxo unificado de geração** (rascunho editável) — feature separada, spec pronto, não iniciada.
