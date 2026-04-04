# ClipIA — QA Final e Preparacao para Producao

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia docs/NEXT-SESSION-QA-PRODUCTION.md. Foco: polir dashboard, QA critico, preparar deploy producao com dominio clipia.com.br. UM PASSO DE CADA VEZ."

---

## Regra da sessao

**1 fix → testar → confirmar → proximo.**

---

## Contexto

Dashboard redesign feito (10 componentes Tailwind), branding refresh (logo, Space Grotesk), dark/light mode, showcase com 3 videos reais, 12 estilos de narração. Dominio clipia.com.br sendo comprado.

---

## Prioridades (em ordem)

### 1. QA Critico — Fluxo Completo

Testar com browser real (Chromium DevTools ou gstack) cada fluxo:

- [ ] **Landing page (deslogado)**
  - Navbar mostra "Entrar"
  - Showcase videos tocam com autoplay muted
  - Hover/touch unmute funciona nos 3 videos
  - Demo form redireciona para login ao gerar
  - Dropdown de estilos abre e fecha, legivel
  - Links: Exemplos, Como funciona (scroll suave)
  - Light/dark mode toggle funciona

- [ ] **Auth**
  - Register: cria conta, redireciona
  - Login: entra, redireciona
  - Logo novo aparece centralizado
  - Creditos iniciais corretos

- [ ] **Dashboard (logado)**
  - Navbar: logo, creditos badge, avatar dropdown
  - Dropdown: Dashboard, Tema toggle, Sair
  - Template selector: 4 opcoes visiveis
  - Style selector: 12 opcoes visiveis e legiveis
  - Topic input funciona
  - Duration slider funciona
  - Gerar video: polling, progress bar, conclusao
  - Video aparece no grid apos conclusao
  - Editar abre o editor
  - Baixar funciona
  - Empty state quando sem videos
  - Modal creditos quando 0 creditos
  - Responsivo: mobile 375px, tablet 768px, desktop 1440px

- [ ] **Editor**
  - Carrega composicao do video
  - Preview Remotion funciona
  - Abas: Cenas, Voz, Legendas, Elementos, IA
  - AI suggest + apply funciona
  - Export FFmpeg funciona
  - Auto-save funciona
  - Logo novo no header

- [ ] **Light mode (todas as telas)**
  - Cards com shadow, bordas visiveis
  - Texto legivel em todos os componentes
  - Gradientes ambient sutis
  - Navbar transparente com backdrop blur

### 2. Polir Dashboard UX

- [ ] **Thumbnails reais** — Gerar thumbnail do video (primeiro frame) via FFmpeg e mostrar no VideoCard em vez de gradiente placeholder
- [ ] **Deletar video** — Botao de deletar job no VideoCard (com confirmacao)
- [ ] **Ordenacao** — Mais recentes primeiro (verificar se backend ja faz isso)
- [ ] **Busca/filtro** — Input de busca por tema nos videos (client-side filter)
- [ ] **Stats no topo** — Cards com: total de videos, creditos usados, ultimo video gerado
- [ ] **Mobile menu** — Hamburger menu no dashboard navbar para mobile

### 3. Preparar Deploy Producao

- [ ] **Dominio clipia.com.br**
  - Atualizar Cloudflare Tunnel config:
    - `clipia.com.br` → localhost:3003
    - `api.clipia.com.br` → localhost:8005
  - Atualizar NEXT_PUBLIC_BASE_URL
  - Atualizar CORS origins no backend
  - Atualizar metadata/OpenGraph em layout.tsx
  - Testar SSL/HTTPS via Cloudflare

- [ ] **Environment variables**
  - Criar `.env.production` com valores reais
  - ANTHROPIC_API_KEY (ja configurado)
  - PEXELS_API_KEY (ja configurado)
  - SECRET_KEY para JWT (gerar nova chave forte)
  - DATABASE_URL (manter local por agora)

- [ ] **Hardening**
  - Rate limiting no FastAPI (slowapi ou similar)
  - Validar tamanho maximo de input no generate
  - Logs estruturados (JSON) para producao
  - Health check endpoint ja existe (/health)

- [ ] **Performance**
  - `next build` e servir com `next start` (nao dev mode)
  - Otimizar showcase videos (comprimir com FFmpeg -crf 28)
  - Lazy load de componentes pesados (Remotion player)

### 4. Melhorias Visuais (nice to have)

- [ ] **Animacao de entrada** nos cards do dashboard (fade-in staggered)
- [ ] **Skeleton loading** mais polido no VideoGrid
- [ ] **Toast notifications** em vez de alerts inline
- [ ] **Favicon** atualizado com novo logo
- [ ] **OG Image** atualizada para compartilhamento social

---

## Arquivos-chave

| Area | Arquivos |
|------|----------|
| Dashboard | `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/dashboard/*` |
| Landing | `frontend/src/app/page.tsx`, `frontend/src/components/ShowcaseSection.tsx` |
| Branding | `frontend/src/components/brand/Logo.tsx` |
| Theme | `frontend/src/app/globals.css`, `frontend/src/components/ThemeToggle.tsx` |
| Auth | `frontend/src/app/auth/*/page.tsx`, `frontend/src/contexts/AuthContext.tsx` |
| Editor | `frontend/src/components/editor/EditorLayout.tsx` |
| Backend | `app/api/routes.py`, `app/config.py`, `app/main.py` |
| Deploy | `/etc/cloudflared/config.yml`, `frontend/.env` |

---

## Comandos

```bash
# Frontend dev
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# Frontend production build
cd ~/projects/auto-shorts/frontend && npm run build && npm start -- -p 3003

# Backend
cd ~/projects/auto-shorts && source .venv/bin/activate
uvicorn app.main:app --reload --port 8005

# Worker Celery
LD_LIBRARY_PATH=/usr/local/lib/ollama/cuda_v12:$LD_LIBRARY_PATH \
  celery -A app.worker.celery_app worker -l info --concurrency=1

# TypeScript check
cd ~/projects/auto-shorts/frontend && npx tsc --noEmit

# Testar endpoint
TOKEN=$(curl -s -X POST http://localhost:8005/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"gui@clipia.com","password":"test123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```
