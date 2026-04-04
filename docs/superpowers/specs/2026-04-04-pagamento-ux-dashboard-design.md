# ClipIA — Pagamento MercadoPago + UX Dashboard

**Data:** 2026-04-04
**Status:** Aprovado

## Contexto

O ClipIA tem auth JWT funcional, sistema de creditos (User.credits default 2, User.plan default "free"), e deducao de 1 credito por video gerado. Porem nao existe forma de comprar creditos — sem monetizacao, nao tem produto. Alem disso, o dashboard tem pontos de UX que impactam a experiencia: logo nao leva pra landing, indicacao de logado fraca, navbar basica, e grid de videos sem filtros.

**Objetivo:** Implementar compra de creditos via MercadoPago Checkout Pro + 4 melhorias de UX no dashboard.

---

## Sub-projeto 1: Pagamento MercadoPago

### Modelo de monetizacao

Creditos avulsos — usuario compra pacotes. Sem assinatura por enquanto.

### Pacotes

| Nome | Creditos | Preco (BRL) | Preco/credito |
|------|----------|-------------|---------------|
| Starter | 5 | R$ 19,90 | R$ 3,98 |
| Popular | 15 | R$ 49,90 | R$ 3,33 |
| Pro | 50 | R$ 129,90 | R$ 2,60 |

### Sistema de custos por operacao

| Operacao | Custo | Quando cobra |
|----------|-------|--------------|
| Gerar video | 1 credito | Imediato (ao iniciar geracao) |
| Sugestao IA no editor | 0.5 credito | Acumula (cobra no export) |
| Preview no editor | Gratis | - |
| Resetar video (recomecar) | 1 credito | Imediato (zera pending_credits e editor_state) |
| Export do video editado | Custo acumulado | No momento do export |

**Fluxo de edicao:** Cada chamada `/ai-suggest` adiciona 0.5 ao campo `pending_credits` do Job. O usuario ve o custo acumulado em tempo real. Ao exportar, `pending_credits` e debitado do User.credits. Se creditos insuficientes pro export, mostra modal de compra.

**Cancelamento:** Se o usuario sai do editor sem exportar, `pending_credits` fica no Job mas NAO e cobrado. So cobra no export. Se voltar e exportar depois, cobra o acumulado. Se nunca exportar, nao paga nada pelas sugestoes IA.

### Arquitetura Backend

**Novos arquivos:**
- `app/payments/__init__.py`
- `app/payments/routes.py` — Endpoints de creditos e checkout
- `app/payments/service.py` — Logica MercadoPago (criar preference, processar webhook)
- `app/payments/schemas.py` — Pydantic models (PackageResponse, CheckoutRequest, etc.)

**Novo modelo DB** (`app/db/models.py`):

```python
class CreditPurchase(Base):
    __tablename__ = "credit_purchases"
    id: Mapped[uuid.UUID]           # PK
    user_id: Mapped[uuid.UUID]      # FK -> users
    package_name: Mapped[str]       # "starter", "popular", "pro"
    credits_amount: Mapped[int]     # 5, 15, 50
    price_brl: Mapped[int]          # centavos: 1990, 4990, 12990
    mp_payment_id: Mapped[str | None]   # ID pagamento MercadoPago
    mp_preference_id: Mapped[str]   # ID preference MercadoPago
    status: Mapped[str]             # "pending", "approved", "rejected"
    created_at: Mapped[datetime]
    paid_at: Mapped[datetime | None]
```

**Alterar modelo Job** — adicionar campo:
```python
pending_credits: Mapped[float] = mapped_column(Float, default=0.0)
```

**Nova migration Alembic** para CreditPurchase + Job.pending_credits.

**Novos endpoints:**

| Metodo | Rota | Auth | Descricao |
|--------|------|------|-----------|
| GET | `/api/v1/credits/packages` | Sim | Lista os 3 pacotes disponiveis |
| POST | `/api/v1/credits/checkout` | Sim | Recebe `{package: "starter"}`, cria preference MP, retorna `{checkout_url}` |
| POST | `/api/v1/webhooks/mercadopago` | Nao* | Webhook MP. Valida signature, busca payment na API MP, credita se approved |
| GET | `/api/v1/credits/history` | Sim | Lista CreditPurchase do usuario (paginado) |

*Webhook nao tem JWT mas valida assinatura HMAC do MercadoPago.

**Alterar endpoints existentes:**

- `POST /api/v1/jobs/{job_id}/ai-suggest` — Acumular 0.5 em `job.pending_credits` a cada chamada. Retornar `pending_credits` na response.
- `POST /api/v1/jobs/{job_id}/render` — Antes de renderizar, verificar `user.credits >= job.pending_credits`. Debitar `pending_credits` do user. Resetar `job.pending_credits = 0`.

**Fluxo MercadoPago:**

1. Frontend chama `POST /credits/checkout` com package name
2. Backend cria `CreditPurchase` (status=pending), chama SDK MP para criar preference
3. Preference configurada com:
   - `back_urls.success` = `{FRONTEND_URL}/dashboard/credits?status=success`
   - `back_urls.failure` = `{FRONTEND_URL}/dashboard/credits?status=failure`
   - `back_urls.pending` = `{FRONTEND_URL}/dashboard/credits?status=pending`
   - `notification_url` = `{BACKEND_URL}/api/v1/webhooks/mercadopago`
   - `external_reference` = CreditPurchase.id
4. Retorna `checkout_url` pro frontend → redirect
5. Webhook recebe notificacao → busca payment na API MP → se approved, credita

**Idempotencia:** Webhook checa se CreditPurchase.status ja e "approved" antes de creditar. Evita double-credit.

**Config** (`app/config.py`):
```
MP_ACCESS_TOKEN: str       # Token de producao MercadoPago
MP_WEBHOOK_SECRET: str     # Secret pra validar signature (opcional mas recomendado)
FRONTEND_URL: str          # https://clipia.com.br (pra back_urls)
```

### Arquitetura Frontend

**Nova pagina:** `frontend/src/app/dashboard/credits/page.tsx`

Layout:
```
[Navbar]
[Seus creditos: X]  ← destaque grande
[3 Cards de pacote lado a lado]
  [Starter]  [Popular ★]  [Pro]
  [5 cred]   [15 cred]    [50 cred]
  [R$19,90]  [R$49,90]    [R$129,90]
  [Comprar]  [Comprar]    [Comprar]
[Historico de compras - tabela]
```

- Card "Popular" com borda gradient e badge "Mais vendido"
- Card "Pro" com badge "Melhor custo"
- Botao "Comprar" chama API, redireciona pra MP
- Query params `?status=success|failure|pending` mostram toast ao retornar
- Historico: tabela com data, pacote, creditos, status, valor

**Novos componentes:**
- `CreditPackageCard.tsx` — Card de pacote individual
- `PurchaseHistory.tsx` — Tabela de historico
- `ExportCostBanner.tsx` — Banner no editor mostrando custo acumulado antes do export

**Alteracoes no editor:**
- Mostrar custo acumulado (`pending_credits`) em destaque perto do botao Export
- Se `pending_credits > 0` e `user.credits < pending_credits`: botao Export desabilitado com tooltip "Creditos insuficientes" + link pra comprar

**Nova lib:** `frontend/src/lib/payments.ts`
- `fetchPackages()` — GET /credits/packages
- `createCheckout(packageName)` — POST /credits/checkout → redirect
- `fetchHistory()` — GET /credits/history

### Dependencia Python

```
mercadopago>=2.2.0
```

Adicionar ao requirements.txt e instalar no .venv.

---

## Sub-projeto 2: UX Dashboard

### 2.1 Logo → Landing

**Arquivo:** `frontend/src/components/dashboard/DashboardNavbar.tsx`

Trocar link do Logo de `/dashboard` para `/`. Quando usuario clica no logo do dashboard, vai pra landing page.

### 2.2 Indicacao de logado (Landing Navbar)

**Arquivo:** `frontend/src/components/Navbar.tsx`

Quando logado, trocar o link text "Dashboard" + "Sair" por:
- Avatar circular com inicial do nome (reusar estilo do UserDropdown)
- Chip com creditos
- Botao "Dashboard →" mais proeminente (gradient, como o "Entrar")
- Manter "Sair" no hover/dropdown

### 2.3 Navbar melhorada (Dashboard)

**Arquivo:** `frontend/src/components/dashboard/DashboardNavbar.tsx`

Adicionar:
- Link "Creditos" clicavel ao lado do CreditsBadge → `/dashboard/credits`
- No UserDropdown: item "Meus Creditos" com icone de moeda
- Chip do plano do usuario ("Free" cinza / "Pro" gradient) no dropdown

### 2.4 VideoGrid com filtros

**Arquivo:** `frontend/src/components/dashboard/VideoGrid.tsx`

Adicionar barra de filtros acima do grid:
- **Ordenacao:** "Recentes" / "Antigos" (pills clicaveis, NAO select nativo)
- **Status:** "Todos" / "Concluidos" / "Processando" / "Erro" (pills com contagem)
- **Template:** "Todos" / pills por template usado

Filtragem client-side (jobs ja carregados, max 50). Sem chamada extra ao backend.

**Novo componente:** `FilterBar.tsx` — Barra de pills reutilizavel

---

## Arquivos criticos a modificar

### Backend
| Arquivo | Mudanca |
|---------|---------|
| `app/db/models.py` | Adicionar CreditPurchase, Job.pending_credits |
| `app/payments/routes.py` | **Novo** — endpoints de creditos |
| `app/payments/service.py` | **Novo** — logica MercadoPago |
| `app/payments/schemas.py` | **Novo** — schemas Pydantic |
| `app/api/routes.py` | Alterar /ai-suggest (acumular) e /render (debitar pending) |
| `app/config.py` | Adicionar MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, FRONTEND_URL |
| `app/main.py` | Registrar router de payments |
| `requirements.txt` | Adicionar mercadopago |
| `alembic/versions/` | Nova migration |

### Frontend
| Arquivo | Mudanca |
|---------|---------|
| `src/app/dashboard/credits/page.tsx` | **Novo** — pagina de creditos |
| `src/components/dashboard/CreditPackageCard.tsx` | **Novo** — card de pacote |
| `src/components/dashboard/PurchaseHistory.tsx` | **Novo** — tabela historico |
| `src/components/dashboard/ExportCostBanner.tsx` | **Novo** — banner custo export |
| `src/components/dashboard/FilterBar.tsx` | **Novo** — barra de filtros |
| `src/lib/payments.ts` | **Novo** — funcoes API pagamento |
| `src/components/dashboard/DashboardNavbar.tsx` | Logo→/, link creditos, navbar |
| `src/components/Navbar.tsx` | Indicacao de logado melhorada |
| `src/components/dashboard/VideoGrid.tsx` | Adicionar FilterBar |
| `src/app/dashboard/credits/layout.tsx` | **Novo** — layout protegido |

### Reusar existente
| Componente | Arquivo | Uso |
|------------|---------|-----|
| `Logo` | `src/components/brand/Logo.tsx` | Ja usado, so trocar href |
| `CreditsBadge` | `src/components/dashboard/CreditsBadge.tsx` | Reusar na landing navbar |
| `UserDropdown` | `src/components/dashboard/UserDropdown.tsx` | Adicionar item "Creditos" |
| `getToken()` / `fetchWithAuth()` | `src/lib/auth.ts` | Pra chamadas autenticadas |
| `DashboardLayout` | `src/app/dashboard/layout.tsx` | Protege /credits automaticamente |
| Design system (cores, glass cards) | `src/app/globals.css` | Manter consistencia visual |

---

## Verificacao

### Backend
1. Criar conta MercadoPago sandbox e obter access token de teste
2. `POST /credits/checkout` com package "starter" → deve retornar URL valida do MP sandbox
3. Simular webhook com payment approved → verificar creditos creditados no user
4. `POST /ai-suggest` no editor → verificar `pending_credits` incrementa 0.5
5. `POST /render` com pending_credits > 0 → verificar debito do user.credits
6. Webhook duplicado → verificar idempotencia (nao credita 2x)
7. Export sem creditos suficientes → 402 com mensagem clara

### Frontend
1. Navegar pra `/dashboard/credits` → ver 3 cards de pacote
2. Clicar "Comprar" → redirect pra checkout MP sandbox
3. Voltar com `?status=success` → ver toast + creditos atualizados
4. No editor, usar AI suggest → ver custo acumulado perto do Export
5. Tentar exportar sem creditos → ver mensagem + link pra comprar
6. Logo do dashboard → deve ir pra landing `/`
7. Landing logado → ver avatar + creditos + botao Dashboard proeminente
8. VideoGrid → testar filtros por status e ordenacao
9. Temas dark/light → verificar todos os novos componentes
