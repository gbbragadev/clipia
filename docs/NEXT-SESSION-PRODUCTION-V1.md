# ClipIA — Rumo a Producao v1

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia docs/NEXT-SESSION-PRODUCTION-V1.md. Foco: dashboard, pagamentos, landing page com showcase. UM PASSO DE CADA VEZ."

---

## Regra da sessao

**1 feature → testar → confirmar → proxima.**

---

## Prioridades (em ordem)

### 1. Revisar e consolidar o que existe

Antes de adicionar features novas, revisar:
- [ ] Fluxo completo: gerar video → editar → AI apply → export → download
- [ ] Verificar que auto-save funciona apos edicoes
- [ ] Testar com video novo (nao reusando job antigo)
- [ ] `npx tsc --noEmit` limpo

### 2. Dashboard — Redesign UX

**Objetivo:** Dashboard profissional, nao cara de prototipo.

- [ ] Layout melhorado: grid de videos com thumbnails, status badges, datas
- [ ] Acoes rapidas: editar, exportar, deletar
- [ ] Indicadores: creditos restantes, videos gerados, ultimo video
- [ ] Responsivo (mobile/tablet)
- [ ] Empty state quando nao tem videos ainda

**Referencia visual:** Pense em Canva/CapCut dashboard — simples, limpo, grid visual.

### 3. Menu Dashboard na Landing Page

- [ ] Apos login, navbar da landing page mostra "Dashboard" em vez de "Login"
- [ ] Avatar/iniciais do usuario no canto
- [ ] Dropdown com: Dashboard, Meus Videos, Configuracoes, Sair

### 4. Sistema de Pagamentos e Creditos

**Conceito proposto (validar com Gui):**

| Recurso | Creditos | Descricao |
|---------|----------|-----------|
| Gerar video (pipeline completa) | 5 creditos | Script + TTS + media + composicao |
| Edicao IA (sugestao + apply) | 1 credito | Regenera narracao com texto novo |
| Regenerar narracao | 1 credito | Muda voz/velocidade/tom |
| Export | 0 creditos | Gratis — ja foi pago na geracao |

**Planos sugeridos:**
- Free: 10 creditos/mes (2 videos)
- Pro: 100 creditos/mes (20 videos + edicoes ilimitadas)
- Business: 500 creditos/mes

**Implementacao:**
- Tabela `credits` no Postgres: user_id, balance, transactions
- Middleware que verifica creditos antes de operacoes caras
- UI: badge de creditos no dashboard + modal de upgrade

**Integracao pagamento:** Stripe (checkout session) ou Mercado Pago

### 5. Landing Page — Videos Showcase

**Objetivo:** Mostrar videos 10/10 feitos pela propria plataforma. Provar que da pra fazer conteudo profissional.

- [ ] Gerar 4-6 videos showcase com temas variados:
  - Curiosidades cientificas
  - Fatos historicos surpreendentes
  - Dicas de produtividade
  - Tecnologia/IA
  - Natureza/animais
  - Cultura pop
- [ ] Cada video deve ter:
  - Gancho forte nos primeiros 3s
  - Legendas estilizadas (diferentes presets)
  - Musica de fundo adequada ao tema
  - EndScreen com CTA
- [ ] Carrossel/grid na landing page com player inline
- [ ] "Feito com ClipIA" badge em cada video
- [ ] Usar templates variados (stock_narration, gameplay_split, story_time) pra mostrar versatilidade

### 6. Seletor de Templates no Dashboard

Ja existe `app/templates.py` com 4 templates (stock_narration, gameplay_split, character_narration, story_time).
O dispatch_pipeline ja aceita template_id. Falta:
- [ ] UI de selecao de template ao gerar video (cards visuais)
- [ ] Preview/descricao de cada template
- [ ] Integrar template_id no fluxo de geracao do dashboard

### 7. Melhorias no Export (visual)

- [ ] Overlays mais fieis ao preview (PNG overlay ou SVG)
- [ ] Testar todos os presets de legenda no export ASS

---

## Arquivos-chave

| Area | Arquivos |
|------|----------|
| Dashboard | `frontend/src/app/dashboard/page.tsx` |
| Landing | `frontend/src/app/page.tsx`, `frontend/src/components/` |
| Auth/Navbar | `frontend/src/components/Navbar.tsx`, `frontend/src/contexts/AuthContext.tsx` |
| Creditos | `app/models.py` (novo), `app/api/routes.py` |
| Export | `app/services/compositor.py`, `app/worker/tasks.py` |
| Editor | `frontend/src/contexts/EditorContext.tsx` |
| Templates | `app/templates.py` — 4 templates com layout, media, script, voice configs |

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

# TypeScript check
cd ~/projects/auto-shorts/frontend && npx tsc --noEmit
```
