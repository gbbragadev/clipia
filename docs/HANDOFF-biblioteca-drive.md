# HANDOFF — Biblioteca do Drive + Semântica CLIP (ClipIA)

> Autocontido para outra LLM continuar. Sessão original: 28-29/06/2026.

## Atualização 2026-07-01
- A task `ClipIA Index Overnight` rodou em **30/06/2026 03:00**, mas a indexação abortou por `subprocess.TimeoutExpired` no `rclone copy` depois de 300s. O agendador mostrou resultado 0 porque o `.ps1` mascarava o exit code.
- Correção aplicada em `app/services/drive_library.py`: `_rclone(timeout=...)` agora captura timeout como processo com `returncode=124`; `_download_batch` quebra downloads em lotes de 100, usa `--tpslimit 2`, `--retries 5`, `--low-level-retries 20`, timeout de 1800s e avisa quando o Drive retorna sucesso baixando 0 arquivos.
- Correção aplicada em `scripts/index_all_overnight.ps1`: redireciona stdout/stderr sem pipeline, grava `fim (exit=N)` e propaga `exit $exitCode`.
- Validação: `tests/test_drive_library.py` passou (`5 passed`) e `scripts/index_library.py satisfying 1` embeddou 1 clip novo. Contagem após smoke: `satisfying 31/3164`; demais tags ainda 0 embeddings.
- Indexação completa reiniciada manualmente em **01/07/2026 19:04** via `scripts/index_all_overnight.ps1`. Monitorar `storage/index_overnight.log` e processos `python.exe scripts/index_library.py` / `rclone.exe`.

## Branch e commits
- **Branch:** `feat/biblioteca-drive-multi-tag` (LOCAL, **não pushed**). Base: `main` (`97c8d07`).
- **Commits:** `f2fbe1f` (feature completa) + `1dac5be` (script overnight).
- main está ~175 commits atrás; trabalho recente vive em branches locais. Push só quando o Gui pedir.

## Contexto (o que era x o que é)
ClipIA = gerador de Shorts (FastAPI + Celery + Next.js). Templates de vídeo (`app/templates.py`) usam clips de **fundo** de uma biblioteca.
- **ANTES:** `media_library.pick_clip(tag)` = `random.choice` de `storage/library/<tag>/*.mp4` — pasta vazia → templates quebravam ("No clips in library").
- **AGORA:** biblioteca do **Google Drive** (7403 clips) **pesquisável por semântica** (CLIP). Cada cena do roteiro puxa o clip mais coerente pelo significado.

## O que está implementado (`app/services/drive_library.py`)
- **Catálogo SQLite** (`storage/drive_index.db`, tabela `drive_clips`): `remote_path` PK, `tag`, `folder_id`, `name`, `cached_path`, `indexed_at`, `embedding` (BLOB float32). **7403 clips em 10 tags** via `FOLDER_TAG_MAP` (tag → lista de folder-IDs do Drive).
- **Acesso rclone:** `_rclone()` wrapper; `list_remote_clips(folder_id)` = `rclone lsf gdrive: --drive-root-folder-id={ID} --recursive --files-only`.
- **Cache sob demanda:** `_ensure_cached()` baixa 1 clip via `rclone copy ... --include <name>` → `storage/library/cache/<tag>/`.
- **Camada semântica CLIP (cuda):** `_get_clip_model()` (ViT-B/32, lazy), `_extract_frame()` (ffmpeg, frame do meio), `index_embeddings(tag, limit)` (batch `--files-from`, baixa + embedda), `search_clips(query, tag, k, exclude)` (cosine; fallback aleatório se faltar dep/embeddings).
- **Integração pipeline:** `app/worker/tasks.py::task_fetch_media` ramo `source=="local"` agora é **per-cena** — `search_clips(visual_hint/keywords_en[0]/text/topic da cena, tag, k=1, exclude=used_names)` + fallback `pick_clip`. Se `loop_single`: 1 clip pro vídeo todo.
- **`media_library.pick_clip(tag)`** cai no Drive quando a pasta local está vazia; `count_clips(tag)` = local + Drive.
- **Templates** (`app/templates.py`): `loop_single=False` nos 4 local; repropósito: `gameplay_split`→cinematic, `character_narration`→satisfying, `dialogue_duo`→podcast, `story_time`→satisfying.
- **CLIs:** `scripts/index_drive_library.py` (cataloga), `scripts/index_library.py [tag] [limit]` (embedda idempotente), `scripts/index_all_overnight.ps1` (batch noturno).
- **Testes:** `tests/test_drive_library.py` (3 offline, mock rclone). **279 passed.**
- **Config:** `RCLONE_EXE`, `RCLONE_REMOTE` em `app/config.py`. `_run-worker.ps1` copia `RCLONE_EXE` do User scope.

## Estado dos dados (29/06)
- Catálogo: **7403 clips indexados** (names em UTF-8 correto — re-indexado depois de mojibake).
- **Embeddings: só ~30 clips de satisfying** embeddados (validação). O resto está pendente.
- Cache: ~37 clips de satisfying baixados em `storage/library/cache/satisfying/`.

## Estado do ambiente (29/06, PC do Gui)
- Backend uvicorn (`:8005`) + worker celery rodando **com código novo** (`scripts/_run-backend.ps1` / `_run-worker.ps1`). Subir/derrubar: ver `_run-*.ps1` (detached via `Start-Process powershell -File ... -WindowStyle Hidden`).
- **rclone** configurado: remote `gdrive` (OAuth do Gui, `drive.readonly`). Binário winget em `C:\Users\guibr\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_*\rclone.exe`. `RCLONE_EXE` setado em **User scope** (propaga pro worker).
- **ffmpeg/ffprobe** winget em `...\Gyan.FFmpeg_*\ffmpeg-8.1-full_build\bin` — **adicionado ao User PATH**.
- **torch 2.6.0+cu124** (`cuda=True`, GTX 1660 4GB) + `sentence-transformers 5.6.0` no venv `.venv312`.
- **Scheduled task** `ClipIA Index Overnight` → **30/06/2026 03:00** (one-time, `StartWhenAvailable`+`WakeToRun`), roda `index_all_overnight.ps1`. Loga em `storage/index_overnight.log`.

## ⚠️ GOTCHAS (NÃO repetir — todos SILENT, rc=0, stderr vazio)
1. **Pasta compartilhada via link do Drive:** acessar por `rclone lsf gdrive: --drive-root-folder-id={ID}`. O path por ID (`gdrive:{ID}`) falha com "directory not found". `--drive-shared-with-me` só lista as compartilhadas no topo.
2. **encoding utf-8 OBRIGATÓRIO** no `subprocess.run` (`encoding="utf-8", errors="replace"`). Sem isso, cp1252 (default Win) gera **mojibake** nos names com acento ("SATISFATÓRIO" → "SATISFATÃ"RIO") → `--files-from`/`--include` não matcheiam → **baixa 0 silenciosamente**. Se suspeitar, compare `name.encode('utf-8')` do SQL vs `list_remote_clips` (o live é o correto). Re-indexar do zero (`rm storage/drive_index.db` + `index_drive_library.py`) corrige.
3. **Rate-limit do Drive:** `rclone copy --include <name>` lista a pasta inteira a cada chamada (PACK1 tem 2392 = ~17s/call). Em batch (50+ copies seguidos) o Drive throttlea e retorna 0 transfers sem erro. Indexação usa `--files-from` (1 listagem por pasta) num único `rclone copy`. Em runtime, `--include` de 1 clip é ok (1ª vez lento, depois cache). `--files-from` precisa `newline=""` no `NamedTemporaryFile` (senão `\r\n` quebra o match).
4. **rclone/ffmpeg (winget) fora do PATH** das sessões novas do tool (cada PowerShell call herda env stale). Scripts standalone setam `$env:Path += ";<winget bin>"` e `$env:RCLONE_EXE` explícito. O launcher `_run-worker.ps1` copia do User scope (prelude).
5. **ffprobe/ffmpeg** são chamados em `tts.py:_fit_to_duration` (TTS) e `drive_library._extract_frame`. Sem eles no PATH → `WinError 2`.
6. **lean-ctx (proxy de shell)** bloqueia: `Remove-Item`, `git -C <dir>` (use `git` do cwd), e aspas duplas em `git commit -m "..."` (PS interpreta `(drive)` como subexpressão). **Use `git commit -F <arquivo-de-msg>`** (gitignored, ex: `storage/_msg.txt`). `Register-ScheduledTask` (cmdlet) passa.
7. **Branch `feat/fluxo-unificado-drive` está OBSOLETA** (só specs, ~atrasada do main em trends/quality/etc.). NÃO trabalhar nela. Trabalho novo sobre `main`.

## E2E validado
`scripts/validate_readiness.py` (com `template_id=story_time` temporariamente) passou verde ponta-a-ponta: cadastro→OTP→verify→generate→scripting→tts→transcribe→**fetch_media (Drive per-cena semântico)**→compose→finalize→MP4 5.97 MB. **O `validate_readiness` está de volta no default `stock_narration`** (é untracked, arquivo do Gui).

## ▶️ Próximos passos (priorizados)

1. **Indexação completa (automática 30/06 3h, ou rodar manual).** `scripts/index_all_overnight.ps1` (ou `index_library.py` sem args) embedda todas as tags (~7000 clips restantes, ~11GB download, **horas** — rate-limit do Drive é o gargalo). **Monitorar** `storage/index_overnight.log`. Se rate-limitar muito (muitas pastas com 0 baixados), adicionar `--tpslimit 2` no `_rclone` de `_download_batch` ou sleep entre pastas. Depois disso, `search_clips` tem variedade real.
2. **Push da branch** `feat/biblioteca-drive-multi-tag` quando o Gui liberar (+ PR).
3. **Deploy prod:** se o prod roda noutro PC/servidor, precisa: rclone configurado (OAuth) + `rclone.conf`, `RCLONE_EXE`/ffmpeg no `start-production.ps1`, e `torch+CUDA`+`sentence-transformers` no venv de prod. Hoje tudo roda no PC do Gui (dev=prod).
4. **Gameplay real (parkour Minecraft / surf CS):** **ausente do Drive** (confirmado — só satisfying/lifestyle/cinematic/etc.). Quando o Gui subir os clips numa pasta do Drive, adicionar a tag `minecraft_parkour` no `FOLDER_TAG_MAP` com o folder-ID + `index_drive_library.py` + `index_library.py minecraft_parkour`. Os 3 templates `gameplay_split`/`character_narration`/`dialogue_duo` foram repropósito pra nichos que existem (cinematic/satisfying/podcast) — voltar a tag pra `minecraft_parkour` quando houver acervo.
5. **Fluxo unificado de geração (rascunho editável):** feature SEPARADA, spec pronto em `docs/superpowers/specs/2026-06-28-fluxo-unificado-geracao-design.md` (branch obsoleta). Não iniciada.

## Comandos rápidos (venv `.venv312`)
```powershell
# Indexar catálogo (idempotente; names utf-8)
$env:RCLONE_EXE="<winget rclone.exe>"; $env:PYTHONPATH="C:\Dev\clipia"
& .\.venv312\Scripts\python.exe scripts\index_drive_library.py

# Embeddar (idempotente; GPU). 1 tag + amostra, ou tudo.
$env:Path += ";<winget ffmpeg bin>"
& .\.venv312\Scripts\python.exe scripts\index_library.py satisfying 200

# Testar busca semântica
& .\.venv312\Scripts\python.exe -c "from app.services.drive_library import search_clips; print([p.name for p in search_clips('ocean waves', 'satisfying', k=3)])"

# Testes
& .\.venv312\Scripts\python.exe -m pytest -q

# Reiniciar worker (pega código novo; Python sem hot-reload)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*celery*app.worker*' } | Stop-Process -Force
Start-Process powershell -ArgumentList '-NoProfile','-File','C:\Dev\clipia\scripts\_run-worker.ps1' -WindowStyle Hidden
```

## Mapa de arquivos
- `app/services/drive_library.py` — catálogo + cache + semântica (tudo aqui).
- `app/services/media_library.py` — `pick_clip` (fallback Drive) + `count_clips`.
- `app/worker/tasks.py:577` — `task_fetch_media` ramo `local` per-cena.
- `app/templates.py` — `FOLDER_TAG_MAP` via tags; `loop_single=False`.
- `app/config.py` — `RCLONE_EXE`/`RCLONE_REMOTE`.
- `docs/drive-sources-catalog.md` — mapa de fontes do Drive (categorias → folder-IDs, contagens).
- `docs/briefing-biblioteca-drive-glm.md` — briefing original (GPU corrigido p/ GTX 1660).
- Memórias: `~/.claude/projects/C--Dev-clipia/memory/biblioteca-midia-drive.md`, `sem-gpu-local.md`.

## Decisões do Gui (registradas)
- **Semântica:** CLIP local em **CUDA (GTX 1660)**, batch one-time (não API paga).
- **Granularidade:** 1 clip por cena + pool anti-repetição (`loop_single=False`).
- **Gameplay:** repropósito p/ nichos fixos (cinematic/satisfying/podcast) + aguardar fonte real de parkour MC/surf CS.
- **Indexação completa:** agendada de madrugada (não bloquear o PC durante o uso).
