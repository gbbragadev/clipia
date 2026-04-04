# ClipIA Editor v3 — QA Session

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia docs/NEXT-SESSION-EDITOR-V3-QA.md. Foco: debugar AI apply, testar export, QA feature por feature. UM FIX DE CADA VEZ."

---

## Regra da sessao

**1 fix → 1 teste → confirmar com usuario → proximo fix.**
NAO fazer multiplas mudancas em paralelo. O usuario perdeu confianca na sessao anterior por causa disso.

---

## Bug #1 (PRIORIDADE): AI apply nao atualiza texto

### Sintoma
Clicar "Aplicar" numa sugestao IA nao muda o texto da cena visivelmente. O botao muda pra "Aplicado" mas o texto na aba Cenas continua o original.

### O que ja sabemos
- Backend `/ai-suggest` retorna dados corretos (testado via curl): `scene_index: 0` (int), `new_text` (string)
- `handleApply` chama `updateScene(suggestion.scene_index, { text: suggestion.new_text })`
- `updateScene` esta no EditorContext e chama `updateComposition → setComposition`
- O fluxo tambem chama `selectScene` e `setActivePanel('scenes')` para navegar pra aba Cenas

### O que investigar (nesta ordem)
1. **Adicionar console.log** no `handleApply` (AIAssistant.tsx:80) para confirmar que e chamado com valores corretos
2. **Adicionar console.log** no `updateScene` (EditorContext.tsx:145) para confirmar que setComposition recebe o novo texto
3. **Verificar SceneGrid.tsx** — o textarea value esta bound a `scene.text`? O componente re-renderiza quando composition muda?
4. **Testar React batching** — tentar REMOVER `selectScene` e `setActivePanel` do handleApply e ver se so o `updateScene` funciona isolado
5. **Verificar pushHistory** — o `historyIndex` no useCallback pode estar stale, causando a history a sobrescrever o update

### Arquivos relevantes
- `frontend/src/components/editor/AIAssistant.tsx:80` — handleApply
- `frontend/src/contexts/EditorContext.tsx:133-141` — updateComposition
- `frontend/src/contexts/EditorContext.tsx:145-151` — updateScene
- `frontend/src/components/editor/SceneGrid.tsx:101-113` — textarea com scene.text

---

## Bug #2: Export Remotion SSR (nao testado)

### O que foi feito
- `@remotion/renderer` instalado
- `frontend/scripts/render-video.mjs` criado (bundla + renderMedia)
- `task_rerender_video` chama o script via subprocess
- `Path` import fixado no tasks.py

### O que pode dar errado
- Webpack bundler pode falhar (paths de alias `@/` nao resolvidos)
- Assets (video, audio) precisam ser acessiveis via HTTP durante render
- Backend precisa estar rodando em localhost:8005 para servir os assets
- `@remotion/bundler` pode precisar de config extra (tsconfig paths)

### Como testar
1. Verificar que backend esta rodando
2. No editor, exportar video
3. Checar logs do worker: `tail -f /tmp/clipia-worker.log`
4. Se falhar no bundle, verificar o erro e ajustar webpack config

---

## Bug #3: Regenerar narracao com texto editado

### Depende de
Bug #1 resolvido (precisa que AI apply funcione para ter texto diferente)

### O que foi feito
- VoiceSelector agora envia `text: composition.scenes.map(s => s.text).join(' ')` no request
- Backend `/regenerate-tts` aceita `text` e re-sintetiza + re-transcreve

### Como testar
1. Editar texto de uma cena manualmente na aba Cenas
2. Ir pra aba Voz → Regenerar Narracao
3. O audio deve refletir o texto editado

---

## QA Checklist Completo

Testar CADA item individualmente. Marcar com ✅ ou ❌.

| # | Feature | Teste | Status |
|---|---------|-------|--------|
| 1 | Transicoes | Cena 2 → fade → play | |
| 2 | Legendas preview | Preset tiktok, play, karaoke funciona | |
| 3 | Musica preview | Elementos → play track → som toca | |
| 4 | Musica no Player | Selecionar track → play video | |
| 5 | AI sugestoes | Quick prompt → recebe sugestoes | |
| 6 | AI apply | Clicar Aplicar → texto muda na aba Cenas | |
| 7 | Regenerar narracao | Editar texto → Voz → Regenerar | |
| 8 | Elementos editaveis | EndScreen → editar username/texto | |
| 9 | Export | Exportar → video baixa com tudo | |
| 10 | Persistencia | F5 → musica/overlays/estilo preservados | |
| 11 | TypeScript | npx tsc --noEmit | |

---

## Comandos

```bash
# Frontend
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# Backend
cd ~/projects/auto-shorts && source .venv/bin/activate
uvicorn app.main:app --reload --port 8005

# Worker Celery
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1

# Testar AI suggest via curl
TOKEN=$(curl -s -X POST http://localhost:8005/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"gui@clipia.com","password":"test123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -X POST "http://localhost:8005/api/v1/jobs/b5569f9c-3e73-456e-9b3f-d34667344e5b/ai-suggest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"Torne mais dramatico","context":{"title":"Teste","scenes":[{"text":"O sol e uma estrela","keywords_en":["sun"],"duration_hint":7}]}}' \
  | python3 -m json.tool
```
