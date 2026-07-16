# Clipia Growth Loop Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an auditable 20-credit acquisition offer, activated referral reward, opt-in public video sharing, PII-free marketing export and consent-gated Meta conversion delivery without changing the normal 2-credit signup.

**Architecture:** New append-only reward records sit beside the existing credit ledger and are claimed under row locks. Public sharing uses unguessable tokens and a qualified-view endpoint; the Next.js page preserves the static showcase fallback. Marketing data is exposed through a separate token-protected aggregate API, while Meta delivery is disabled by default and never blocks core transactions.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL/SQLite tests, Pydantic, Next.js 16, TypeScript, pytest.

## Global Constraints

- Normal direct, organic and referral sign-up remains exactly 2 welcome credits.
- Active offer code is `creator20_v1`; verified eligible campaign users receive exactly +18 once, for 20 total.
- A user who did not receive the campaign +18 can receive exactly +18 once after their first referred person verifies email and completes their first generation.
- Campaign and referral acquisition rewards are mutually exclusive for the rewarded user.
- A user can receive exactly +2 once after the first qualified external view of any active public share.
- A qualified view requires at least 5000 ms visible dwell, a non-owner session, an active share and a non-bot user agent; no raw visitor IP is persisted.
- Every credit mutation must create an idempotent credit-ledger entry in the same database transaction.
- First-party analytics is authoritative; Meta CAPI is disabled by default and requires explicit marketing measurement consent.
- No browser Meta Pixel is introduced.
- Public APIs return no email, IP, filesystem path, access token or other PII.

---

### Task 1: Campaign offer and activated referral rewards

**Files:**
- Modify: `app/db/models.py`
- Create: `alembic/versions/e8f9a0b1c2d3_add_growth_acquisition_rewards.py`
- Create: `app/services/acquisition_rewards.py`
- Modify: `app/auth/schemas.py`
- Modify: `app/auth/routes.py`
- Modify: `app/auth/referrals.py`
- Modify: `app/services/job_operations.py`
- Modify: `app/analytics/schemas.py`
- Modify: `app/analytics/service.py`
- Test: `tests/test_growth_acquisition_rewards.py`
- Modify: `tests/test_authoritative_analytics_flows.py`

**Interfaces:**
- `RegisterRequest.offer_code: str | None` and `RegisterRequest.marketing_measurement_consent: bool = False`.
- `claim_campaign_reward(db, user, occurred_at) -> int` returns 18 or 0.
- `claim_referral_activation_reward(db, referred_user, completed_job, occurred_at) -> int` returns 18 or 0.
- `AcquisitionReward.reward_type` is one of `campaign_signup|referral_activation|social_share`, unique per `(user_id, reward_type)`; acquisition +18 claims also enforce one of campaign/referral per user.

- [ ] Write failing tests: direct verification grants 2; valid `creator20_v1` verification grants 2 then 18; invalid/inactive offers grant only 2; retries and concurrent claims never duplicate.
- [ ] Write failing tests: verification alone no longer rewards the referrer; the referred user's first completed generation grants +18 once; later generations grant zero.
- [ ] Write failing tests: campaign recipient cannot also receive referral activation +18; campaign registration ignores a simultaneous referral code.
- [ ] Add `marketing_offers`, `acquisition_rewards`, `users.acquisition_offer_id`, `users.marketing_measurement_consented_at`; seed active `creator20_v1` with 18 bonus credits and no fake expiry.
- [ ] Keep `ReferralCreditAward` readable for historical rows but stop creating new +2-per-verification awards.
- [ ] Implement claim services with row locks, unique constraints, credit-ledger context and `credit_balance_changed` analytics reasons `campaign_signup` and `referral_activation`.
- [ ] Verify email by applying base welcome credit first and campaign reward second in the same transaction; return the amount actually added in the response.
- [ ] Call referral activation from `finalize_generation` before its transaction commits; require verified referred user and generation ordinal `first`.
- [ ] Update analytics property models/catalog constraints and migration tests for the new reasons/events without accepting arbitrary payload properties.
- [ ] Run `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_growth_acquisition_rewards.py tests/test_authoritative_analytics_flows.py tests/test_email_otp.py tests/test_job_operation_integrity.py tests/test_credit_ledger.py` and commit only task files.

### Task 2: Opt-in public video shares and qualified-view reward

**Files:**
- Modify: `app/db/models.py`
- Create: `alembic/versions/f9a0b1c2d3e4_add_public_video_shares.py`
- Create: `app/public_shares/__init__.py`
- Create: `app/public_shares/schemas.py`
- Create: `app/public_shares/service.py`
- Create: `app/public_shares/routes.py`
- Modify: `app/main.py`
- Test: `tests/test_public_video_shares.py`

**Interfaces:**
- `POST /api/v1/videos/{job_id}/public-share` returns `{token,url,title,active}` for an owned completed job and is idempotent while active.
- `DELETE /api/v1/videos/{job_id}/public-share` revokes the owned share.
- `GET /api/v1/public-shares/{token}` returns public metadata and a public video URL, never the storage path.
- `GET /api/v1/public-shares/{token}/video` streams only an active share's completed video.
- `POST /api/v1/public-shares/{token}/qualified-view` accepts `{anonymous_session_id: UUID,dwell_ms: int,page_visible: bool}` and returns `{qualified,rewarded}`.

- [ ] Write failing ownership/status/revoke tests and assert 404 for missing/revoked tokens.
- [ ] Write failing view tests for dwell below 5000, hidden page, owner cookie, bot user-agent, repeated session and concurrent first views.
- [ ] Add `public_video_shares` with a cryptographically random URL-safe token hash, owner/job foreign keys, active/revoked timestamps and one active share per job.
- [ ] Add `public_share_visits` unique by `(share_id, anonymous_session_id)`; store user-agent classification and timestamps but no raw IP.
- [ ] Claim `social_share` +2 only once per owner through `AcquisitionReward`, using credit-ledger origin `social_share_reward` in the same transaction.
- [ ] Serve video through the existing safe output resolution rules and reject paths outside the configured output directory.
- [ ] Register the router under `/api/v1`, apply rate limits and append authoritative share published/visited/rewarded events.
- [ ] Run `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_public_video_shares.py tests/test_credit_ledger.py tests/test_authorization.py` and commit only task files.

### Task 3: Campaign landing, registration propagation and sharing UI

**Files:**
- Modify: `frontend/src/hooks/useUTM.ts`
- Modify: `frontend/src/lib/auth.ts`
- Modify: `frontend/src/contexts/AuthContext.tsx`
- Modify: `frontend/src/app/auth/register/page.tsx`
- Create: `frontend/src/app/oferta/criadores/page.tsx`
- Create: `frontend/src/lib/public-shares.ts`
- Modify: `frontend/src/app/v/[id]/page.tsx`
- Create: `frontend/src/app/v/[id]/QualifiedViewTracker.tsx`
- Modify: `frontend/src/components/dashboard/VideoCard.tsx`
- Modify: `frontend/src/components/dashboard/ReferralCard.tsx`
- Modify: `frontend/src/app/termos/page.tsx`
- Modify: `frontend/src/app/privacidade/page.tsx`
- Test: `tests/test_frontend_growth_contract.py`

**Interfaces:**
- Attribution storage carries `offer_code` separately from UTM and clears it after successful registration.
- Campaign CTA is `/auth/register?offer=creator20_v1&utm_source=meta&utm_medium=paid_social&utm_campaign=clipia_creator20_pilot`.
- `createPublicShare(jobId)`, `revokePublicShare(jobId)` and `getPublicShare(token)` are typed frontend clients.

- [ ] Read the installed Next.js 16 App Router documentation from `C:\Dev\clipia\frontend\node_modules\next\dist\docs` before editing routes or metadata.
- [ ] Write a source-contract test proving direct registration copy remains 2 and the campaign route alone promises 20.
- [ ] Capture query `offer`, propagate it as `offer_code`, present an unchecked optional marketing-measurement consent and never infer it from terms acceptance.
- [ ] Build the creator landing with no fake timer/scarcity: idea-to-video proof, exact 20-credit terms, CTA, FAQ and campaign UTMs.
- [ ] Preserve static showcase IDs in `/v/[id]`; resolve unknown IDs through the public-share API and generate dynamic OG metadata.
- [ ] Start the qualified-view POST only after five seconds of visible page time using a durable anonymous UUID; teardown timers on visibility/unmount.
- [ ] Add publish/copy/revoke controls to completed VideoCards, clear opt-in language and no automatic public exposure.
- [ ] Change ReferralCard copy to: the referrer unlocks +18 only after the invited person verifies and completes the first video; do not claim both users receive extras.
- [ ] Update terms/privacy for campaign, referral, public sharing, view qualification and consented Meta measurement.
- [ ] Run `npx.cmd next typegen`, `npx.cmd tsc --noEmit` and `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_frontend_growth_contract.py` and commit only task files.

### Task 4: PII-free marketing export and consent-gated Meta CAPI

**Files:**
- Modify: `app/config.py`
- Create: `app/marketing/__init__.py`
- Create: `app/marketing/schemas.py`
- Create: `app/marketing/export.py`
- Create: `app/marketing/meta_capi.py`
- Create: `app/marketing/routes.py`
- Modify: `app/main.py`
- Modify: `app/auth/routes.py`
- Modify: `app/payments/webhooks.py`
- Test: `tests/test_marketing_export.py`
- Test: `tests/test_meta_capi.py`

**Interfaces:**
- `GET /api/v1/internal/marketing/summary?from=YYYY-MM-DD&to=YYYY-MM-DD` requires `X-Marketing-Token` and returns aggregate funnel/revenue/source data.
- `GET /api/v1/internal/marketing/conversions?cursor=...` returns event ID, event type, timestamp, pseudonymous customer ref, amount/currency and attribution fields only.
- `enqueue_meta_conversion(db, *, user, event_name, event_id, value_brl=None) -> bool` stores only consented conversions and is idempotent by event ID.
- `dispatch_pending_meta_conversions(...) -> dict` is disabled unless all Meta settings are present.

- [ ] Write failing tests for absent/wrong marketing token, date bounds, pagination, pseudonym stability and response PII denial (`email`, `name`, `ip`, tokens and filesystem paths absent recursively).
- [ ] Write failing tests proving no Meta row/network call without consent or with `META_CAPI_ENABLED=false`; repeated event IDs dispatch once.
- [ ] Add secret settings with safe defaults: `MARKETING_EXPORT_TOKEN`, `MARKETING_PSEUDONYM_SECRET`, `META_CAPI_ENABLED=false`, `META_CAPI_PIXEL_ID`, `META_CAPI_ACCESS_TOKEN`, `META_CAPI_API_VERSION`.
- [ ] Aggregate authoritative analytics and approved purchases; hash user IDs with HMAC-SHA256 and the dedicated pseudonym secret.
- [ ] Add a durable Meta conversion outbox with event ID, event name, JSON payload, attempts, next attempt and sent timestamp; store only normalized/hashed identifiers.
- [ ] Enqueue `CompleteRegistration` after successful verification and `Purchase` after canonical approved payment, with deterministic event IDs for Meta deduplication.
- [ ] Dispatch with bounded timeout and exponential retry; failures never roll back signup/payment.
- [ ] Run `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_marketing_export.py tests/test_meta_capi.py tests/test_stripe_webhook_signatures.py tests/test_payment_webhook_idempotency.py` plus Ruff on touched Python files, then commit only task files.

