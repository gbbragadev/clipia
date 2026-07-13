# Task 1C1 — relatório de entrega

## Status

Implementação concluída no worktree `C:\Dev\clipia-worktrees\clipia-audit-hardening`, preservando o baseline `5ac23d6` e sem implementar compensation/reconciler/watchdog da Task 1C2.

Commit convencional desta entrega: `feat: persist durable job operations`. O hash final é informado no handoff da sessão; um commit não consegue registrar o próprio hash dentro do conteúdo que o determina.

## Entrega funcional

- Migration expansiva `f6e7d8c9b0a1` após `d4e5f6a7b8c9`, com os nove campos de operação, defaults e índice `(rerender_state, rerender_debited_at)`.
- Backfill somente de `generation_dispatched_at = created_at`; `generation_refunded_at` permanece vazio.
- Serviço DB-only `app/services/job_operations.py`, sem Redis/filesystem/Celery e sem commit interno, com row locks, `populate_existing` e deltas SQL de saldo/créditos pendentes.
- Cancelamento persistido em DB antes da flag Redis, somente para geração ativa não entregue, idempotente em `cancelling` e com TTL de 24 horas.
- Refund de geração one-shot por `generation_refunded_at`; entrega prevalece sobre cancel/refund tardio.
- Finalize com CAS DB: cancelamento vencedor não entrega; sucesso grava `editable`, `video_url` e `completed_at`, depois remove a flag.
- Rerender com UUID, snapshot fracionário, custo `ceil`, estados duráveis, único débito/task e 409 para operação concorrente.
- Worker reivindica UUID antes de tocar output; duplicata/stale sai. O artefato temporário inclui o UUID e a publicação canônica + telemetria + estado terminal ocorre sob row lock e revalidação do UUID.
- Falha/cancel de rerender devolve o custo uma vez e soma o snapshot ao bucket atual, preservando edições concorrentes.
- Caminho legado `operation_id=None` só reivindica `idle` sem UUID e nunca adivinha contra uma operação nova.
- `ai_suggest` soma `pending_credits` por `UPDATE` SQL relativo/`RETURNING`, evitando sobrescrever o zero/snapshot do render com uma identidade ORM stale.

## Evidência TDD — RED observado

Os testes foram escritos antes de cada mudança de produção e executados com basetemp novo. REDs principais observados:

- Cancelamento: `2 failed` — entregue retornava 200; cancel ativo não persistia `cancelling/cancel_requested_at`.
- Schema/migration: `1 failed` — colunas de operação ausentes no metadata.
- Refund de geração: `2 failed` — função DB-only ainda ausente.
- Wrapper worker de refund: `1 failed` — job entregue ainda era publicado como falha no Redis.
- Máquina de rerender: `2 failed` — begin/claim/refund/complete ainda ausentes.
- Rota render: `1 failed` — segundo POST ainda retornava 200 e não havia UUID durável.
- Worker rerender/legado: `2 failed` por assinatura sem `operation_id`; `1 failed` pelo claim legado ausente.
- Finalize: `2 failed` — cancel-winner entregava arquivo; sucesso não gravava `completed_at`/delete da flag.
- Dispatch de geração: `1 failed` — `generation_dispatched_at` permanecia nulo.
- Self-review: `3 failed` — cancelling entregue aceitava cancel, render inválido apagava cancel real e falha DB do finalize virava completed.
- Refund legado: `1 failed` — falha DB não retornava resultado explícito.
- Review independente: `2 failed` — interleaving `ai_suggest/render` deixava 2.0 antes do refund em vez de 0.5; operação stale-after-claim sobrescrevia output canônico.
- Re-review: `2 failed` — artefatos MP4 por UUID permaneciam no storage após success/stale.

## Evidência GREEN

- Todos os ciclos focados acima foram reexecutados individualmente até GREEN.
- Gate integrado pré-fixes do review: `70 passed, 13 warnings in 73.89s`.
- Regressões dos dois achados Important: `2 passed, 13 warnings in 7.71s`.
- Regressões de cleanup dos temporários UUID: `2 passed, 13 warnings in 6.70s`.
- Reteste pós-`ruff-format` dos arquivos afetados + integridade: `36 passed, 13 warnings in 48.10s`.
- Reteste dos três arquivos formatados pelo hook isolado: `16 passed, 13 warnings in 11.04s`.
- Gate integrado final:

  `python -m pytest tests\test_job_operation_integrity.py tests\test_pipeline_resilience.py tests\test_rerender_refund.py tests\test_concurrent_usage.py tests\test_credits_integrity.py tests\test_credit_refund_on_enqueue_failure.py tests\test_video_gen_cancel.py tests\test_worker_voice.py tests\test_regression_pipeline.py tests\test_jobs_realtime.py -q --basetemp .pytest-tmp-1c1-gate-final`

  Resultado final pós-formatação: `72 passed, 13 warnings in 61.65s`.

- Ruff nos arquivos Python tocados: `All checks passed!`.
- `python -m alembic heads`: `f6e7d8c9b0a1 (head)`.
- `git diff --check`: exit 0.

As 13 warnings são o `DeprecationWarning` já existente do SlowAPI sobre `asyncio.iscoroutinefunction` no Python 3.14.

## Arquivos

- `alembic/versions/f6e7d8c9b0a1_add_job_operation_state.py`
- `app/services/job_operations.py`
- `app/db/models.py`
- `app/api/routes.py`
- `app/worker/tasks.py`
- `tests/test_job_operation_integrity.py`
- `tests/test_rerender_refund.py`
- `tests/test_concurrent_usage.py`
- `tests/test_credits_integrity.py`
- `tests/test_jobs_realtime.py`
- `tests/test_regression_pipeline.py`
- `tests/voice_test_support.py`

## Self-review e preocupações remanescentes

- Nenhum Critical/Important conhecido permaneceu após a revisão independente e os dois fixes TDD.
- Os testes usam SQLite; eles exercitam interleavings e identidade ORM stale, mas não provam a semântica multiprocesso de `SELECT FOR UPDATE` no PostgreSQL real.
- Não houve broker Redis/Celery real nem migration smoke contra PostgreSQL publicado.
- Publicação de arquivo e commit DB não podem ser uma transação única. O row lock impede outra operação válida de iniciar durante a publicação, mas uma falha de commit depois do copy canônico ainda exige a futura reconciliação da Task 1C2.
- Compensation/reconciler/watchdog de enqueue/debito ficaram explicitamente fora desta tarefa, conforme o brief.

## Revisão final corretiva

A revisão final posterior ao commit `5b14570` encontrou seis lacunas de concorrência/publicação. Elas foram corrigidas por TDD em um commit separado, sem incorporar compensation, reconciler ou watchdog da Task 1C2.

### Correções

- O hash Redis passa a registrar `rerender_operation_id`. Estados terminais de rerender são publicados por Lua atômico somente quando o UUID ainda é o atual; o fallback com lock existe apenas para fakes/legado sem `eval`.
- O interleaving worker-before-route preserva `rerender_dispatched_at`: o claim preenche o timestamp se necessário, e o ack tardio da rota aceita `running` sem regredir o estado.
- Falhas de infraestrutura no claim do worker propagam para a task/Celery. Apenas UUID inválido ou mismatch legítimo retornam `False`.
- A geração adquire uma claim persistente `finalizing` antes de criar artefatos canônicos. Cancelamentos tardios são rejeitados, retries concorrentes observam `in_progress`, e cancel/refund/estado ignorado removem MP4 e thumbnail stale.
- Geração e rerender preparam outro/MP4/thumbnail em caminhos temporários antes do row lock. Sob o lock final ficam somente revalidação do estado/UUID, troca por `Path.replace`, mutação ORM e commit, com restauração de arquivos em falha.
- As operações `render` e `cancel` agora documentam o conflito `409` no OpenAPI.

### Evidência TDD adicional

REDs observados antes das correções:

- Primeiro lote: `6 failed` — ack tardio não gravava dispatch, UUID não entrava no Redis, OpenAPI não expunha 409, falha DB no claim era engolida e terminal stale sobrescrevia a operação nova.
- Segundo lote: `3 failed` — append/thumbnail ocorriam depois do row lock, a claim de finalize não existia e job ignorado deixava MP4/JPG diretamente baixáveis.

GREENs após as correções:

- Primeiro lote direcionado: `6 passed, 13 warnings in 3.34s`.
- Segundo lote direcionado: `3 passed, 13 warnings in 2.79s`.
- Regressões existentes de finalize/cancel/falha DB: `3 passed, 13 warnings in 2.88s`.
- Integridade completa: `29 passed, 13 warnings in 48.74s` antes do format; `29 passed, 13 warnings in 25.70s` depois do format isolado.
- Gate integrado final corretivo: `81 passed, 13 warnings in 70.96s`.
- `python -m alembic heads`: `f6e7d8c9b0a1 (head)`.
- `uvx pre-commit run --files ...`: `ruff Passed`; `ruff-format Passed` na segunda execução.
- `git diff --check`: exit 0 antes do fechamento do relatório.

As 13 warnings continuam sendo exclusivamente o `DeprecationWarning` já existente do SlowAPI no Python 3.14.

## Segunda re-review corretiva

A re-review posterior ao commit `2cbdc5c` encontrou duas corridas Redis restantes e uma precedência incorreta entre validação persistida e filesystem. As três foram corrigidas por TDD, novamente sem ampliar o escopo para reconciler ou watchdog.

### Correções

- O terminal/refund do enqueue-failure da rota `render` usa o mesmo CAS Redis por `rerender_operation_id` da task. Se A faz refund, B inicia e só então A tenta publicar o terminal, o Redis de B permanece `rendering`.
- O terminal `completed` da geração usa Lua atômico próprio e só publica quando o hash ainda não possui um `rerender_operation_id`. Assim, o intervalo entre commit `editable`, notificação e update Redis não permite que a geração sobrescreva um rerender B já iniciado.
- A rota `render` faz precheck dos estados persistidos inválidos (`status` não entregue ou rerender ativo) antes de consultar o diretório. O `begin_rerender` sob row lock permanece como revalidação autoritativa, portanto o precheck não substitui o CAS nem debita créditos.

### Evidência TDD

- RED dos três achados: `3 failed, 13 warnings in 5.22s`, exatamente com A sobrescrevendo B para `completed`, geração sobrescrevendo B para `completed` e job `queued` sem diretório retornando 404 em vez de 409.
- RED adicional do outro estado persistido inválido: rerender `running` sem diretório retornou 404 em vez de 409 (`1 failed, 13 warnings in 4.06s`).
- GREEN conjunto dos quatro interleavings/prechecks: `4 passed, 13 warnings in 5.50s`.
- Gate cobridor final: `85 passed, 13 warnings in 73.03s`.
- Ruff: `All checks passed!`.
- `python -m alembic heads`: `f6e7d8c9b0a1 (head)`.
- Hook isolado: `ruff Passed`; `ruff-format Passed`, sem modificações.

As 13 warnings continuam sendo exclusivamente o `DeprecationWarning` já existente do SlowAPI no Python 3.14.
