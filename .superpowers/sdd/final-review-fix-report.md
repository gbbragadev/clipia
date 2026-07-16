# Final Review Fix Report

## Status

All Critical/Important final-review findings were fixed in TDD on the local
`codex/clipia-growth-product` branch. Meta delivery remained disabled by
default and no real Meta request was executed.

## Delivered video contract and public metadata

- RED: `finalize_generation` persisted `Job.status="editable"`, while public
  share creation, lookup, social reward, and the frontend gate accepted only
  `completed`.
- GREEN: `editable|completed` is now the delivered contract across those
  backend/frontend seams. An integrated test finalizes a real job, publishes
  it, records a qualified external view, and grants the +2 reward.
- The unauthenticated metadata endpoint now returns only the generic title
  `Vídeo publicado com ClipIA`, never `Job.topic`. A hostile topic test covers
  email, Windows path, filename, and token-shaped content.
- Public metadata includes the share publication timestamp and the public
  `VideoObject` uses it as `uploadDate`.

## Legal versions and attribution

- `TERMS_VERSION` and `PRIVACY_VERSION` are both `2026-07-16`, matching the
  effective date displayed by both legal pages and the versions persisted on
  registration.
- The public CTA uses one fixed, capability-free taxonomy:
  `public_share / organic_social / creator20_v1 / public_video`.
- Registration now accepts and persists `utm_content`; server analytics and
  purchase export carry it through the same field-specific allowlists.
- The end-to-end test follows CTA values through registration, the
  `user_registered` event, and the internal marketing export while denying
  email, token, share capability, or path leakage.

## Migration contract

- All tests that assert the current Alembic head now share
  `tests/migration_contract.py` with head `fa0b1c2d3e4f`.
- Revision `fa0b1c2d3e4f` adds `users.utm_content` and the Meta dispatch lease
  fields without creating a second head.
- Real PostgreSQL smoke completed: full upgrade to head, downgrade to
  `f9a0b1c2d3e4`, and re-upgrade to head. Inspection confirmed the head,
  attribution column, and both lease columns.

## Meta dispatcher concurrency

- RED: PostgreSQL tests proved that both a normal `User` update and an outbox
  cancellation blocked while the HTTP client was pending.
- GREEN: due rows are claimed with `FOR UPDATE SKIP LOCKED`, assigned a short
  `dispatching` lease, and committed before any network await. Consent,
  deleted-account, outbox status, and lease ownership are rechecked without
  locks immediately before delivery.
- Success/retry finalization is conditional on the same live lease, so a
  concurrent cancellation is never overwritten. Timeout errors return rows to
  durable exponential retry, and an expired lease is reclaimable after a
  crashed worker.
- SQLite remains fail-closed and never invokes the network client.

## Verification

- Focused backend growth/marketing/auth/analytics matrix: **90 passed, 2
  skipped** (the skips are opt-in PostgreSQL cases covered separately).
- Real PostgreSQL Meta outbox matrix: **7 passed**, including no User lock
  during HTTP, concurrent cancellation, SKIP LOCKED, retry, and stale lease
  recovery.
- Migration matrix with real PostgreSQL: **24 relevant tests passed** across
  the initial run plus the two corrected stale-head reruns.
- Frontend Node behavior tests: **31 passed**.
- `next typegen`, `tsc --noEmit`, and Next.js production build: green; **40
  pages** generated.
- Ruff check/format, focused `compileall`, and `git diff --check`: green.

## Explicit follow-ups (not implemented in this fix)

- Move public-share token signing from the general JWT secret to a dedicated
  share secret with rotation support.
- Refactor the SQLite credit-ledger compatibility path separately; the
  production PostgreSQL invariants remain authoritative.
