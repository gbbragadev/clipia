# ClipIA Editor — Fixes e Features (Proxima Sessao)

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia docs/NEXT-SESSION-EDITOR-FIXES.md e execute os fixes do editor. Foco: fazer o preview Remotion reagir a edicoes em tempo real, re-render no export, e adicionar trilha sonora."

---

## Bugs Confirmados pelo QA Real (2026-04-04)

### 1. CRITICO: Remotion Player nao reage a mudancas do editor

**Sintoma:** Mudar legendas, aplicar sugestoes da IA, trocar transicoes — nada reflete no video preview.

**Causa provavel:** O `<Player inputProps={composition}>` nao re-renderiza quando `composition` muda. O Remotion Player pode precisar de:
- `key` prop que muda quando composition muda (forca re-mount)
- Ou as props precisam ser passadas de forma que o Player detecte mudanca

**Arquivos:**
- `frontend/src/components/editor/VideoPlayer.tsx` — onde o Player recebe inputProps
- `frontend/src/contexts/EditorContext.tsx` — onde composition e atualizado
- `frontend/src/remotion/compositions/ShortVideoComposition.tsx` — como le as props

**Investigar:**
1. Ler docs do Remotion 4 sobre reatividade do Player
2. Verificar se `inputProps` precisa ser spread ou se precisa key
3. Testar com `key={JSON.stringify(composition)}` no Player
4. Verificar se `ShortVideoComposition` usa props diretas ou useCurrentFrame

### 2. Export baixa video original (sem edicoes)

**Sintoma:** Apos editar (mudar voz, texto), clicar Exportar baixa o video original.

**Causa:** Endpoint `/render` em `routes.py` (linhas ~300-330) so copia `final.mp4`. Nao re-compoe.

**Fix necessario:** Implementar re-render real:
- Opcao A: Nova task Celery que executa `compose_short()` com parametros atualizados
- Opcao B: Usar Remotion SSR (`npx remotion render`) no servidor
- Opcao A e mais simples (ja temos o pipeline)

**Fluxo:**
1. Ler editor_state com edicoes do usuario
2. Se audio foi regenerado, usar o novo narration.wav
3. Re-executar compose_short com novos parametros
4. Retornar novo video

### 3. Transicoes nao aplicam

**Sintoma:** Selecionar fade/slide/wipe nao tem efeito visual.

**Investigar:**
- Se `composition.scenes[i].transition` esta sendo setado quando usuario seleciona
- Se `ShortVideoComposition` le `transition` de cada cena
- Se `getTransitionPresentation()` retorna o objeto correto de `@remotion/transitions`
- Se `TransitionSeries` esta recebendo as scenes com duracao correta

### 4. Timeline seek impreciso

**Sintoma:** Clicar na timeline nao posiciona o video no ponto correto.

**Investigar:**
- `EditorTimeline.tsx` `handleSceneAreaClick` — calculo de frame a partir de click
- Se `seekToFrame` chama `playerRef.current.seekTo(frame)` corretamente
- Se `clickToPlay` prop no Player interfere com o seek
- Testar remover `clickToPlay` do Player para ver se melhora

---

## Novas Features

### 5. Trilha sonora / Musica de fundo

**Escopo:** Adicionar opcao de background music ao video.

**Abordagem:**
- Biblioteca de tracks royalty-free (ex: 5-10 opcoes lofi/upbeat/dramatic)
- Slider de volume (0-100%) para mix com narracao
- Preview no Remotion Player (segundo `<Html5Audio>` com volume baixo)
- No compose_short, mixar audio com FFmpeg: `ffmpeg -i narration.wav -i music.mp3 -filter_complex amix=inputs=2:weights="1 0.15"`

**Arquivos a criar/modificar:**
- `frontend/src/components/editor/MusicSelector.tsx` — nova aba ou seção
- `frontend/src/remotion/compositions/ShortVideoComposition.tsx` — adicionar audio de fundo
- `app/services/compositor.py` — mix de audio no FFmpeg
- `storage/music/` — diretorio com tracks

### 6. Auto-posting e agendamento (FASE FUTURA)

**Escopo:** Publicar automaticamente no TikTok/YouTube/Instagram + agendar postagem.

**Nao implementar agora** — documentar como roadmap:
- TikTok: Content Posting API (requer app review)
- YouTube: YouTube Data API v3 (upload via OAuth)
- Instagram: Instagram Graph API (Reels upload)
- Agendamento: Celery beat + tabela de schedules no Postgres

---

## Arquivos Chave

| Arquivo | O que verificar |
|---------|----------------|
| `frontend/src/components/editor/VideoPlayer.tsx` | Como inputProps sao passadas ao Player |
| `frontend/src/contexts/EditorContext.tsx` | Como composition e atualizado e propagado |
| `frontend/src/remotion/compositions/ShortVideoComposition.tsx` | Como le props, transitions, overlays |
| `frontend/src/components/editor/EditorTimeline.tsx` | Calculo de frame no click |
| `app/api/routes.py` | Endpoint /render precisa re-render real |
| `app/services/compositor.py` | compose_short — adicionar mix de audio |

## Ordem de execucao

1. **Fix reatividade Remotion** (desbloqueia bugs 1, 3, 4)
2. **Fix timeline seek** 
3. **Re-render real no export** (bug 2)
4. **Trilha sonora**
5. Testes end-to-end de todo o fluxo

## Comandos

```bash
# Frontend
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# Backend (ja roda com --reload)
curl http://localhost:8005/health

# Worker (precisa CUDA)
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1

# URL do dashboard
# https://autoshorts.gbbragadev.com/dashboard

# URL do editor (job com dados completos)
# https://autoshorts.gbbragadev.com/editor/d6dfe62e-e4e8-41d0-8bd8-cc8dec6da736
```
