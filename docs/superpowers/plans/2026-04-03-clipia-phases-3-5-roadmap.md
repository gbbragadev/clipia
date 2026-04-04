# ClipIA Phases 3-5: Roadmap de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Após a Fase 2 (Auth + DB), implementar sistema de créditos, pagamento Stripe, dashboard do usuário, e infraestrutura de produção.

**Architecture:** Créditos como coluna no User model (já criado na Fase 2). Stripe Checkout Sessions para pagamentos. Dashboard como nova rota `/dashboard` protegida por auth. Docker Compose para deploy completo. Cloudflare R2 para storage de vídeos.

**Tech Stack:** Stripe API, Next.js App Router, Docker Compose, Cloudflare R2, Sentry, Prometheus/Grafana

**Dependências:** Fase 2 → Fase 3 → Fase 4 (sequenciais). Fase 5 parcialmente parallelizável.

---

## Fase 3: Monetização — Créditos & Pagamento (2-3 dias)

### Pré-requisitos
- Fase 2 completa (users table com campo `credits`, auth JWT funcionando)
- Conta Stripe criada
- Stripe CLI instalada para testar webhooks localmente

### File Structure

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `app/payments/__init__.py` | Package init |
| Create | `app/payments/schemas.py` | CheckoutRequest, WebhookEvent schemas |
| Create | `app/payments/service.py` | Stripe session creation, credit granting |
| Create | `app/payments/routes.py` | POST /checkout, POST /webhook/stripe, GET /user/credits |
| Create | `app/payments/plans.py` | Definição dos planos e preços |
| Modify | `app/db/models.py` | Adicionar Payment model |
| Modify | `app/main.py` | Registrar payments router |
| Modify | `app/config.py` | STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET |
| Create | `alembic/versions/002_payments.py` | Migration: tabela payments |
| Create | `frontend/src/app/pricing/page.tsx` | Página de preços |
| Create | `frontend/src/components/pricing/PricingCard.tsx` | Card de plano individual |
| Modify | `frontend/src/components/Navbar.tsx` | Link para /pricing |
| Create | `tests/test_payments.py` | Testes de créditos e checkout |

### Tasks

#### Task 1: Payment Model + Migration
- Criar model Payment (id, user_id, amount_cents, credits_granted, stripe_payment_id, status, created_at)
- Gerar Alembic migration
- Aplicar

#### Task 2: Plans Definition
- Criar `app/payments/plans.py` com definição de planos:
  ```python
  PLANS = {
      "starter": {"name": "Starter", "price_cents": 2900, "credits": 30, "stripe_price_id": "price_xxx"},
      "pro": {"name": "Pro", "price_cents": 7900, "credits": 100, "stripe_price_id": "price_xxx"},
      "single": {"name": "Avulso", "price_cents": 150, "credits": 1, "stripe_price_id": "price_xxx"},
  }
  ```

#### Task 3: Stripe Checkout Endpoint
- POST `/api/v1/checkout` — cria Stripe Checkout Session
- Requer auth (get_current_user)
- Retorna `{ url: "https://checkout.stripe.com/..." }`
- Frontend redireciona para Stripe

#### Task 4: Stripe Webhook
- POST `/api/v1/webhook/stripe` — recebe eventos
- Verifica assinatura com STRIPE_WEBHOOK_SECRET
- `checkout.session.completed` → creditar usuário
- Salvar Payment no DB

#### Task 5: Credits Endpoint
- GET `/api/v1/user/credits` — retorna saldo atual
- Já existe parcialmente via `/auth/me` (user.credits)

#### Task 6: Frontend Pricing Page
- Criar `/pricing` com 3 cards (Free, Starter, Pro)
- Botão "Assinar" → chama POST /checkout → redirect para Stripe
- Design consistente com a landing (gradientes, dark theme)

#### Task 7: Refund on Job Failure
- Modificar `task_finalize` (worker): se job falha, reembolsar 1 crédito ao user
- Atualizar status no DB para "failed"

#### Task 8: Testes
- Testar checkout session creation (mock Stripe)
- Testar webhook processing
- Testar credit deduction + refund
- Testar flow completo: register → checkout → credit → generate

---

## Fase 4: Dashboard do Usuário (2-3 dias)

### Pré-requisitos
- Fase 2 completa (auth + jobs table)
- Fase 3 completa (créditos funcionando)

### File Structure

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `frontend/src/app/dashboard/page.tsx` | Dashboard principal |
| Create | `frontend/src/app/dashboard/layout.tsx` | Layout protegido por auth |
| Create | `frontend/src/components/dashboard/VideoGrid.tsx` | Grid de vídeos gerados |
| Create | `frontend/src/components/dashboard/VideoCard.tsx` | Card individual de vídeo |
| Create | `frontend/src/components/dashboard/GenerateModal.tsx` | Modal de geração (form melhorado) |
| Create | `frontend/src/components/dashboard/StatsBar.tsx` | Barra com créditos, total vídeos, etc |
| Create | `app/api/user_routes.py` | GET /user/jobs (paginado) |
| Modify | `app/main.py` | Registrar user_routes router |
| Modify | `frontend/src/components/Navbar.tsx` | Link "Dashboard" quando logado |

### Tasks

#### Task 1: Backend — Jobs History Endpoint
- GET `/api/v1/user/jobs?page=1&per_page=12` — lista jobs do user
- Ordenado por created_at DESC
- Retorna paginação: `{ items: Job[], total: int, page: int, pages: int }`
- Requer auth

#### Task 2: Dashboard Layout (Protected)
- Criar `frontend/src/app/dashboard/layout.tsx`
- Verificar auth no client — se não logado, redirect para `/auth/login`
- Sidebar ou header com navegação do dashboard

#### Task 3: Dashboard Page + Stats
- StatsBar: créditos restantes, total de vídeos, último vídeo gerado
- Botão "Gerar novo vídeo" abre modal

#### Task 4: Video Grid + Cards
- Grid responsivo de VideoCards
- Cada card: thumbnail (se possível), título/tema, data, status, download button
- Click → expande player
- Pagination controls

#### Task 5: Generate Modal
- Form melhorado dentro do dashboard (modal ou slide-over)
- Campos: tema, estilo, duração, voz (futuro)
- Progress bar inline
- Após conclusão, vídeo aparece no grid

#### Task 6: Navbar Update
- Quando logado: mostrar "Dashboard" link, créditos, avatar/nome, logout
- Quando deslogado: "Entrar" e "Criar conta"

#### Task 7: Testes E2E
- Flow: login → dashboard → gerar vídeo → aparece no grid → download

---

## Fase 5: Produção & Infra (2-3 dias)

### Pré-requisitos
- Fases 2-4 completas

### File Structure

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `Dockerfile` | Multi-stage build do backend |
| Create | `frontend/Dockerfile` | Build do frontend Next.js standalone |
| Modify | `docker-compose.yml` | Stack completa: api, worker, frontend, postgres, redis |
| Create | `docker-compose.prod.yml` | Override de produção (sem volumes dev, secrets) |
| Modify | `app/main.py` | CORS restrito, security headers |
| Create | `app/middleware/rate_limit.py` | Rate limiting por IP/user |
| Create | `.github/workflows/ci.yml` | GitHub Actions: lint, test, build |
| Modify | `app/config.py` | SENTRY_DSN, R2 credentials |
| Create | `app/services/storage.py` | Upload para Cloudflare R2 |
| Modify | `app/worker/tasks.py` | Upload vídeo para R2 após render |

### Tasks

#### Task 1: Docker Compose Produção
- Dockerfile backend (Python 3.12 slim, pip install, uvicorn)
- Dockerfile frontend (Node 22, npm build, standalone)
- docker-compose.yml completo: api, worker (GPU), frontend, postgres, redis
- Health checks em todos os serviços
- GPU reservation para worker

#### Task 2: Cloudflare R2 Storage
- Criar bucket R2 para vídeos
- Serviço Python com boto3 (S3-compatible)
- Upload após renderização no worker
- URL pública para download (via R2 public bucket ou presigned URL)
- Cleanup: expirar vídeos de users free após 7 dias

#### Task 3: Segurança
- CORS restrito: `allow_origins=["https://autoshorts.gbbragadev.com"]`
- Rate limiting: SlowAPI ou middleware custom
  - Sem auth: 10 req/min por IP
  - Com auth: 60 req/min por user
- Input validation (topic length, sanitize)
- JWT_SECRET em produção: `openssl rand -hex 32`

#### Task 4: Monitoramento
- Sentry: SDK Python (FastAPI) + SDK JS (Next.js)
- Prometheus metrics (já existe no servidor)
  - Custom metrics: video_generation_duration, credits_consumed, active_users
- Alertas WhatsApp (já existe) para falhas de geração

#### Task 5: CI/CD
- GitHub Actions workflow:
  - On push to main: lint (ruff) → test (pytest) → build docker → deploy
  - On PR: lint + test only
- Deploy: SSH to srv01-bc → docker compose pull → docker compose up -d

#### Task 6: Cloudflare Tunnel Update
- Atualizar hostname de `autoshorts.gbbragadev.com` para `clipia.gbbragadev.com`
- Adicionar DNS entry para o novo domínio
- Reiniciar cloudflared

#### Task 7: Testes de Carga
- k6 ou locust para 10 usuários simultâneos
- Medir: latência API, throughput de geração, uso de GPU
- Verificar que rate limiting funciona

---

## Fases 6-7: Pós-produção (ongoing)

### Fase 6: QA & Beta Testing
- Playwright E2E: register → generate → download → dashboard
- Recrutar 5-10 beta testers do waitlist
- Dar 5 créditos grátis
- Coletar feedback via Google Forms
- Iterar UX baseado em feedback

### Fase 7: Marketing & Lançamento
- SEO: sitemap.xml, robots.txt, blog com conteúdo sobre IA + vídeos
- Product Hunt launch
- Social media: usar o próprio ClipIA para gerar vídeos de marketing
- Contadores reais na landing (total vídeos gerados, usuários)

---

## Cronograma Estimado

| Fase | Dependência | Esforço | Acumulado |
|------|-------------|---------|-----------|
| ~~Fase 1: Branding~~ | — | ~~1 dia~~ | ~~Dia 1~~ ✅ |
| Fase 2: Auth + DB | Fase 1 | 2-3 dias | Dia 3-4 |
| Fase 3: Créditos + Stripe | Fase 2 | 2-3 dias | Dia 6-7 |
| Fase 4: Dashboard | Fase 2+3 | 2-3 dias | Dia 9-10 |
| Fase 5: Infra + Deploy | Fase 2 | 2-3 dias | Dia 12-13 |
| Fase 6: QA + Beta | Fase 4+5 | 1-2 dias | Dia 14-15 |
| Fase 7: Marketing | Fase 6 | Ongoing | — |

**Nota:** Fases 3-4 e 5 podem ser parcialmente paralelizadas. A Fase 5 (Docker, R2, CI/CD) não depende de Stripe estar pronto, apenas de Auth + DB.
