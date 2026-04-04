# ClipIA Editor v3 — Proxima Sessao

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia docs/NEXT-SESSION-EDITOR-V3.md e continue os fixes do editor. Foco: transicoes entre cenas, pausa na narracao, e validar music/export."

---

## Estado Atual (2026-04-04)

### Funciona
- ✅ Legendas Pretext com karaoke word-highlight, glow, underline (preset tiktok)
- ✅ Impact com cores alternadas + stroke grosso + glow
- ✅ Todos os controles refletem no preview: fonte, tamanho, cor, fundo, posicao, animacao, stroke, margem
- ✅ Player preserva posicao ao atualizar (signature-based remount + seekTo)
- ✅ Timeline seek em blocos de cena
- ✅ SubtitleTimeline Pretext no timeline
- ✅ 10 tracks de musica em frontend/public/music/

### Bugs Pendentes

#### 1. CRITICO: Transicoes entre cenas NAO funcionam

**Sintoma:** Selecionar fade/slide/wipe nao tem efeito visual. Video corta direto entre cenas.

**O que ja tentamos:**
- Keys unicas nos Transition components
- Compensacao de frames para transicoes
- Remount do Player quando transicao muda

**O que investigar:**
- Ler docs oficiais do `@remotion/transitions` (TransitionSeries)
- O TransitionSeries pode nao suportar renderizacao condicional dos `<TransitionSeries.Transition>` — talvez precise SEMPRE renderizar transicoes (usando um noop/identity para "none")
- Testar com um exemplo minimo isolado: 2 cenas + 1 fade, sem condicional
- Verificar se o problema e que `React.Fragment` wrapping quebra o TransitionSeries (ele pode esperar filhos diretos Sequence/Transition)
- Verificar se `durationInFrames` das Sequences esta correto com o calculo de compensacao

**Codigo relevante:** `frontend/src/remotion/compositions/ShortVideoComposition.tsx` linhas 52-72

#### 2. Pausa na narracao entre cenas

**Sintoma:** Audio tem gaps/pausas entre transicoes de cena.

**Causa provavel:** Relacionado ao bug de transicoes — se o TransitionSeries esta criando gaps nos frames, o audio continua mas o video fica preto/congelado, criando sensacao de pausa.

**Investigar:** O `Html5Audio` toca independente do TransitionSeries. Se o video tem gaps mas o audio nao, pode ser que os frames das cenas nao cubram 100% da duracao total.

#### 3. Music preview e selecao (nao testado)

- Error handling foi adicionado
- Cleanup no unmount adicionado
- URLs `/music/*.mp3` retornam 200
- **Testar:** clicar play em uma track, ouvir audio, selecionar, verificar no Remotion Player

#### 4. Export com re-render (nao testado)

- `task_rerender_video` criada em `app/worker/tasks.py`
- `/render` endpoint despacha task Celery
- `/status` endpoint para polling
- ExportPanel faz polling
- **Testar:** precisa do Celery worker rodando

#### 5. IA suggestions (nao testado nesta sessao)

- AIAssistant.tsx tem interface de chat com quick prompts
- Backend endpoint `/ai-suggest` funciona
- **Testar:** aplicar sugestao e verificar se texto da cena muda no preview

---

## Arquivos Chave

| Arquivo | O que verificar |
|---------|----------------|
| `frontend/src/remotion/compositions/ShortVideoComposition.tsx` | TransitionSeries — por que nao funciona |
| `frontend/src/components/editor/PretextSubtitlePreview.tsx` | Engine de legendas Pretext (canvas) |
| `frontend/src/components/editor/VideoPlayer.tsx` | Signature-based remount + seekTo |
| `frontend/src/components/editor/MusicSelector.tsx` | Preview e selecao de tracks |
| `frontend/src/components/editor/ExportPanel.tsx` | Polling de render status |
| `app/worker/tasks.py` | task_rerender_video |
| `app/api/routes.py` | /render, /status, /edit (sync script.json) |

## Comandos

```bash
# Frontend
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# Backend
cd ~/projects/auto-shorts && source .venv/bin/activate
uvicorn app.main:app --reload --port 8005

# Worker Celery (precisa CUDA)
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1

# URLs
# https://autoshorts.gbbragadev.com/editor/d6dfe62e-e4e8-41d0-8bd8-cc8dec6da736
```

## Prioridade

1. **Transicoes** — investigar TransitionSeries a fundo, testar isolado
2. **Pausa na narracao** — resolver junto com transicoes
3. **Validar music** — testar preview + selecao
4. **Validar export** — testar com worker Celery
5. **Pretext melhorias** — mais efeitos, WYSIWYG editing direto no canvas
