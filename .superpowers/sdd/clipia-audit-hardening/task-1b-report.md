# Task 1B - eventos de pagamento transacionais e saldo por delta

## Status

Concluida no escopo do brief `task-1b-brief.md`, preservando a Task 1A e as interfaces publicas
`process_webhook(...)->bool` e `process_webhook_stripe(...)->bool`.

## RED observado

Comando:

```powershell
python -m pytest tests\test_payment_transactions.py -q --basetemp <temp-unico>
```

Resultado antes de alterar producao: **15 failed**. As falhas foram as esperadas para o recorte:

- concorrencia entre compras perdia um incremento (`15 != 25`);
- refund-before-paid permitia credito tardio;
- paid/refund concorrentes podiam terminar `approved`;
- divergencias financeiras Stripe/MP e refund parcial eram aceitos;
- bonus permanecia `0` no checkout em vez de snapshot;
- `ProcessedPaymentEvent` e seu claim ainda nao existiam.

## Decisoes de implementacao

- Um unico helper transacional aplica eventos normalizados sob `payment:purchase:{purchase_id}`.
- A compra e relida com `SELECT ... FOR UPDATE`; validacao, claim, transicao e delta ocorrem antes do
  unico commit.
- `User.credits` e alterado apenas por `UPDATE` relativo. Refund usa `CASE` para clamp em zero.
- Metricas de credito/debito sao emitidas somente depois do commit.
- Stripe assinado usa `event.id`; evento reconsultado usa `api:{event_type}:{object_id}`.
- MP usa `payment:{payment_id}:{authoritative_status}`.
- O bonus e congelado nos checkouts MP e Stripe. Webhooks nunca consultam o percentual corrente.
- Refund Stripe reconsulta o PaymentIntent, resolve primeiro por metadata e usa o fallback legado por
  `provider=stripe + mp_payment_id` somente quando a metadata esta ausente.
- Refund parcial e rejeitado antes do claim financeiro e fica visivel em warning para reconciliacao.

## Migration e modelo

- Revision: `d4e5f6a7b8c9`, depois de `b7c8d9e0f1a2`.
- Tabela `processed_payment_events` com PK composta `provider + event_key`.
- FK `purchase_id -> credit_purchases.id` e indice nao unico por `purchase_id`.
- Apenas `provider`, `event_key`, `purchase_id`, `event_type` e `processed_at`; nenhum payload bruto ou PII.
- Smoke de DDL com `MigrationContext`/`Operations` em SQLite executou `upgrade()` e `downgrade()`, validou
  PK/indice e terminou com `migration upgrade/downgrade smoke passed`.
- `alembic heads`: `d4e5f6a7b8c9 (head)`.

## GREEN e verificacoes

```text
tests/test_payment_transactions.py
15 passed, 13 warnings in 16.40s

tests/test_payment_webhook.py + tests/test_payment_webhook_stripe.py + tests/test_purchase_bonus.py
25 passed, 13 warnings in 29.27s

gate financeiro final (7 arquivos de pagamento/credito/concorrencia)
54 passed, 13 warnings in 67.22s

python -m ruff check <arquivos tocados>
All checks passed!

git diff --check
exit 0
```

Os 13 warnings sao o `DeprecationWarning` preexistente do SlowAPI sobre
`asyncio.iscoroutinefunction`; nao ha warning novo do recorte financeiro.

## Arquivos

- `app/db/models.py`
- `app/payments/service.py`
- `alembic/versions/d4e5f6a7b8c9_add_processed_payment_events.py`
- `tests/test_payment_transactions.py`
- `tests/conftest.py`
- `tests/test_payment_webhook.py`
- `tests/test_payment_webhook_stripe.py`
- `tests/test_purchase_bonus.py`
- `tests/test_concurrent_usage.py`
- `.superpowers/sdd/clipia-audit-hardening/task-1b-report.md`

## Commit

Commit convencional desta entrega: `feat: harden payment event transactions`. O hash e informado na
resposta final porque este relatorio faz parte do proprio commit.

## Preocupacoes

- SQLite ignora `FOR UPDATE`; os testes provam lock process-local e deltas SQL relativos no deployment de
  teste, nao serializacao multiprocesso real em PostgreSQL.
- Nao foi executada a suite completa por instrucao do coordenador; o gate exigido de pagamento/creditos,
  Ruff e smoke da migration passou.
