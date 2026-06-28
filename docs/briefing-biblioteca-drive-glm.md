# Briefing — Indexar, categorizar e embeddar a biblioteca de clips do Google Drive (ClipIA)

> Documento autocontido para um agente (GLM 5.2) executar. Tarefa de tamanho médio-grande;
> tem decisões de design marcadas como "DECIDIR" para alinhar antes de implementar.

## Objetivo

O ClipIA tem acesso a um **Google Drive** com **milhares de clips de vídeo** (vídeos
"satisfatórios", virais, b-roll diverso) usados como **fundo** dos templates de vídeo. Hoje a
escolha do clip de fundo é **burra**: pega um arquivo aleatório de uma pasta por *tag*. 

Queremos transformar isso numa **biblioteca pesquisável por significado**:
1. **Inventariar** todo o Drive e separar o que é b-roll utilizável (9:16, loopável) do lixo.
2. **Categorizar** os clips (satisfying, viral, natureza, gameplay, etc.).
3. **Embeddar** (gerar vetores) cada clip para **busca semântica** — dado o tema/cena do vídeo,
   escolher o clip de fundo **mais relevante**, em vez de aleatório.
4. **Integrar** essa busca na geração (substituir o `random.choice` por busca semântica, com
   fallback para aleatório).

Resultado esperado: vídeos com fundo coerente com o assunto (ex. cena sobre "oceano" puxa um
clip de água/ondas do acervo), não um clip qualquer.

## GPU: GTX 1660 4GB (CUDA) — batch one-time

A máquina tem **GTX 1660 4GB** (Turing, compute 7.5, **CUDA-capable**). A antiga RTX 3090 foi
removida, mas a 1660 ficou. Decisão (28/06, Gui): **embeddings locais via CLIP em CUDA**
(`sentence-transformers`, `clip-ViT-B-32`, `device="cuda"`). É **batch one-time** — depois de
indexado, o runtime é só comparação de vetores em numpy, não toca a GPU de novo. Implicações:
- **Indexação (one-time)**: CLIP em CUDA na 1660 — rápido (segundos/centena de frames). ViT-B/32 é
  leve (~150MB de pesos), cabe folgado em 4GB. Sempre testar `torch.cuda.is_available()` antes;
  fallback automático para `device="cpu"` se não enxergar a GPU.
- **Busca em runtime**: numpy puro (cosine/dot-product), instantâneo em CPU, sem GPU.
- Memórias/docs antigos que dizem "sem GPU" ou "nunca assumir cuda" estão **desatualizados** —
  tinham removido a 3090 mas esqueceram da 1660.

## Stack e onde mexer

- Backend Python 3.12, venv `C:\Dev\clipia\.venv312` (`.\.venv312\Scripts\Activate.ps1`).
- **`app/services/media_library.py`** — HOJE é trivial: `list_clips(tag)` (glob `.mp4` em
  `storage/library/{tag}`) + `pick_clip(tag)` (`random.choice`). É AQUI que a busca semântica entra.
- **`app/templates.py`** — templates locais usam `media=MediaStrategy(source="local",
  library_tag="satisfying"|..., loop_single=True)`. Hoje 1 clip loopado pro vídeo inteiro.
- **`app/worker/tasks.py`** — `task_fetch_media`, branch `source == "local" and loop_single`,
  chama `pick_clip(tag)`. Ponto de integração.
- Clips ficam em `storage/library/{tag}/*.mp4`; cache do Drive previsto em `storage/library/cache/`.

## Estado atual (o que já existe / já foi mapeado)

- A seleção local é `random.choice` por tag. **Sem índice, sem categorias, sem embeddings.**
- **Drive já parcialmente inspecionado (28/06/2026)** — ver memória do projeto
  `biblioteca-midia-drive.md`. Resumo:
  - Acesso via **rclone** (remote `gdrive`, scope `drive.readonly`, **OAuth da conta do Gui** —
    service account NÃO enxerga "Compartilhados comigo").
  - **"VÍDEOS VIRAIS PACK 1"** = 1000+ clips `VIDEO SATISFATÓRIO (N).mp4`, **576×1024 (9:16),
    h264, 8–16s, ~1–2 MB** → já vira a tag `satisfying` (template `story_time`).
  - Outras pastas inspecionadas na época eram lixo (zips de memes, cracks, produtos digitais).
    **MAS** o Gui acredita haver mais conteúdo útil — **reinventariar o Drive inteiro faz parte
    da tarefa**, não confiar só na inspeção antiga.
- **Existe a branch `feat/fluxo-unificado-drive`** com specs em
  `docs/superpowers/specs/2026-06-28-*` e um plano de índice por pasta (SQLite) + fetch sob
  demanda + cache local. **Comece por ela** (`git checkout feat/fluxo-unificado-drive`), veja o
  que já está escrito/iniciado e construa em cima — não recomece do zero nem duplique.

## Tarefa (fases)

### Fase A — Inventário do Drive
- Listar o Drive **nível por nível** via rclone (NÃO usar `-R` recursivo nas pastas grandes —
  pendura/timeout). Para cada pasta, amostrar e classificar: é b-roll 9:16 utilizável? (checar
  resolução/duração com ffprobe numa amostra).
- Produzir um **catálogo** (JSON/SQLite) das pastas úteis com: nome, nº de clips, formato típico,
  categoria proposta. Pastas lixo (zip, crack, memes com texto queimado) ficam de fora.

### Fase B — Cache + índice local
- Estratégia já prevista: **índice SQLite** + **cache sob demanda** em `storage/library/cache/`.
  Cada clip indexado: `id, drive_path, local_path|null, category, width, height, duration, hash`.
- Decidir se baixa tudo (milhares × 1–2 MB = alguns GB) ou cacheia sob demanda. Recomendação:
  baixar/cachear o acervo útil (satisfying + o que mais for aprovado) — é pequeno por clip.

### Fase C — Categorização
- Categoria base por **pasta/nome** (rápido, determinístico).
- Opcional/melhor: categoria por **conteúdo visual** reusando os embeddings da Fase D (clusterizar
  ou classificar por similaridade a rótulos âncora tipo "ocean waves", "city night", "abstract
  satisfying", "nature"). **DECIDIR** se vale o esforço além da categoria por pasta.

### Fase D — Embeddings (CPU, one-time)
- Para cada clip: extrair **1 frame-chave** (ffmpeg, ex. no meio do clip) → embeddar a imagem com
  CLIP (`sentence-transformers` `clip-ViT-B-32`, `device="cpu"`). Guardar o vetor no índice
  (blob/np.save). Rodar como **script batch** (`scripts/index_library.py`), idempotente
  (pula clips já embeddados via hash).
- Reaproveitar/estender `app/services/clip_rerank.py` (já tem `clip-ViT-B-32` com imports lazy),
  mas **forçar `device="cpu"`** (não assumir cuda).

### Fase E — Busca semântica + integração
- Nova função em `media_library.py`, ex.:
  `search_clips(query_text: str, category: str | None = None, k: int = 1, exclude: set[str] = ...) -> list[Path]`
  — embedda o **texto** da cena/tema com CLIP (mesmo espaço multimodal), compara (cosine) com os
  vetores dos clips do índice, retorna top-k. numpy puro, sem GPU.
- Integrar em `task_fetch_media`: onde hoje chama `pick_clip(tag)`, passar a chamar
  `search_clips(texto_da_cena_ou_tema, category=tag, k=1)`, **com fallback para `pick_clip`** se o
  índice estiver vazio/sem match. **DECIDIR**: 1 clip por vídeo (mantém `loop_single`) pelo tema
  geral, ou 1 clip por cena (mudar `loop_single`) pelo `visual_hint` de cada cena — o segundo dá
  fundo mais variado/relevante, porém mais complexo.

## Como validar

- `scripts/index_library.py` roda e popula o índice (SQLite) com embeddings de um subconjunto de
  teste sem erro; é idempotente (rodar 2x não re-embedda).
- `search_clips("ondas do mar à noite", category="satisfying")` retorna clips coerentes (inspeção
  manual de 3–5 resultados) e é instantâneo.
- Gerar um vídeo com template `story_time` e confirmar nos logs que a busca semântica escolheu o
  clip (não `random.choice`), com fallback funcionando quando o índice está vazio.
- `pytest -q` continua verde. Adicionar teste offline da busca (vetores fake → ranking esperado),
  sem exigir CLIP/rede.

## Gotchas / cuidados

- **rclone**: binário do winget NÃO entra no PATH do Git Bash → usar caminho absoluto. Usar
  `--drive-shared-with-me` para "Compartilhados comigo". NÃO usar `-R` em pastas grandes. Refresh
  token em `%APPDATA%\rclone\rclone.conf` — **não commitar**.
- **Sem GPU**: `device="cpu"` em todo embedding; a indexação é batch offline, não no request.
- **Não quebrar o fallback**: se o índice não existir/estiver vazio, a geração deve continuar
  funcionando com `pick_clip` aleatório (comportamento atual).
- **Worker `--pool=solo`** reinicia manual após mudar código (Python sem hot-reload).
- **Secrets** (PEXELS/Drive OAuth) vivem em env vars do Windows / `rclone.conf`, não no repo.
- **Escopo**: começar da branch `feat/fluxo-unificado-drive`; aproveitar o que já existe lá.

## Decisões a alinhar com o Gui antes de codar
1. Embeddings: CLIP local em CPU (grátis, mais lento no batch) vs API multimodal (paga, rápida)?
2. Granularidade: 1 clip de fundo por vídeo (atual, `loop_single`) vs 1 por cena?
3. Quais categorias/pastas do Drive entram além de `satisfying`?
4. Baixar todo o acervo útil localmente vs cache sob demanda?
