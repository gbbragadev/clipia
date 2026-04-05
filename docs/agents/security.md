# Segurança — Audit por Vetor

## Como usar

Escolha um vetor e forneça o(s) arquivo(s) relevante(s). Um vetor por sessão.

**Prompt de invocação:**
```
@docs/agents/security.md
Vetor: cors
Arquivo: app/main.py
```

Vetores disponíveis: `cors`, `jwt`, `sql`, `inputs`, `auth-frontend`, `secrets`, `rate-limit`, `webhook`

---

## Vetor: cors

**Arquivos relevantes:** `app/main.py`, `app/config.py`

Verificar:
- `allow_origins` não é `["*"]` em produção
- Origins permitidas são apenas domínios controlados (clipia.com.br, api.clipia.com.br)
- `allow_credentials=True` só existe se necessário
- Métodos e headers permitidos são o mínimo necessário

Reportar: valor atual de `allow_origins`, se está lendo de variável de ambiente, se tem fallback inseguro.

---

## Vetor: jwt

**Arquivos relevantes:** `app/auth/`, `app/config.py`

Verificar:
- `JWT_SECRET` vem de variável de ambiente, não está hardcoded
- Secret tem comprimento adequado (≥32 chars)
- Algoritmo é HS256 ou RS256 (não "none")
- Token tem expiração (`exp` claim)
- Tokens expirados são rejeitados (não apenas ignorados)
- Não há log do token em nenhum lugar

---

## Vetor: sql

**Arquivos relevantes:** qualquer arquivo com queries, `app/db/`, `app/services/`

Verificar:
- Nenhuma query usa f-string ou concatenação de string com input do usuário
- Todas as queries usam parâmetros bindados (`:param` no SQLAlchemy ou `$1` no asyncpg)
- Filtros de busca não permitem wildcards não sanitizados

Reportar: cada ocorrência de query com string formatting (f"SELECT...", "SELECT..." + variavel).

---

## Vetor: inputs

**Arquivos relevantes:** `app/api/routes.py`, schemas Pydantic em `app/models.py`

Verificar:
- Campos de texto têm `max_length` definido no Pydantic?
- Email é validado como email (`EmailStr` ou `Field(..., pattern=...)`)
- Campos numéricos têm `ge`/`le` bounds?
- Upload de arquivos (se existir) valida tipo MIME e tamanho?
- Nenhum campo aceita HTML/script sem sanitização?

---

## Vetor: auth-frontend

**Arquivos relevantes:** `frontend/src/lib/auth.ts`, qualquer `.tsx` que lida com token

Verificar:
- Token armazenado em `localStorage` como `clipia_token` (não em cookie, não em variável global)
- Token não aparece em console.log, URL params, ou query strings
- Rotas protegidas redirecionam para `/auth/login` se não autenticado
- Token é removido no logout (não apenas redirect)
- Não há token hardcoded em nenhum arquivo

---

## Vetor: secrets

**Arquivos relevantes:** todo o repositório (busca por padrão)

Buscar por:
- Strings que parecem API keys (`sk-`, `mp-`, chaves longas alfanuméricas)
- Emails com senha junto
- Qualquer `SECRET` ou `KEY` hardcoded fora de `.env`
- Arquivos `.env` commitados (verificar `.gitignore`)

Reportar: arquivo e linha de cada ocorrência suspeita.

---

## Vetor: rate-limit

**Arquivos relevantes:** `app/api/routes.py`, `app/main.py`

Verificar:
- Endpoint `/auth/login` tem rate limiting?
- Endpoint `/auth/register` tem rate limiting?
- Endpoint `/generate` tem rate limiting?
- Endpoint `/auth/resend-code` tem rate limiting?
- Rate limit é por IP ou por usuário (ou ambos)?
- Há resposta 429 com `Retry-After` header?

---

## Vetor: webhook

**Arquivos relevantes:** `app/api/routes.py` (rota `/webhooks/mercadopago`), `app/payments/`

Verificar:
- Webhook valida assinatura HMAC do MercadoPago antes de processar?
- Payload é validado antes de usar (não assume campos existem)?
- Idempotência: processar o mesmo webhook duas vezes não credita duas vezes?
- Erros no webhook retornam 200 (para o MP não retentar) ou 4xx com log?

---

## Formato do relatório

```
VETOR: <nome>
ARQUIVO: <caminho>
LINHA: ~<número>
PROBLEMA: <descrição técnica>
RISCO: crítico | alto | médio | baixo
CORREÇÃO SUGERIDA: <como resolver>
```

**Não corrija automaticamente.** Apenas reporte.
