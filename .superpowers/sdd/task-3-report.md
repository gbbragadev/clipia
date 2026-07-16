# Task 3 Report — campaign landing, registration propagation and public sharing UI

## Scope delivered

- Added `/oferta/criadores` with the exact `creator20_v1` CTA, honest 20-credit terms, idea-to-video proof and FAQ without timers or artificial scarcity.
- Kept direct registration on the backend-driven 2-credit copy; captured `offer` separately and propagated it as `offer_code`.
- Added an unchecked, optional Meta measurement checkbox independent from required legal acceptance.
- Added typed public-share create/revoke/get/qualified-view clients with encoded path parameters.
- Preserved local showcase resolution in `/v/[id]`, added API fallback for unknown opt-in tokens and dynamic share metadata without exposing storage paths.
- Added a durable anonymous UUID tracker that posts only after 5 seconds of accumulated visible page time and cleans up visibility timers/listeners.
- Added explicit publish/copy/revoke controls for completed videos and corrected referral copy to referrer-only +18 after verification and first completed video.
- Updated Terms and Privacy for campaign, referral, opt-in sharing, qualified views and consented Meta measurement.

## TDD evidence

### RED

Command:

```powershell
C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_frontend_growth_contract.py
```

Observed before production changes: `5 failed`. Failures were the expected missing campaign route/client/tracker contracts, missing offer propagation, absent share controls and stale referral/legal copy.

A self-review hardening cycle added encoded job/token path parameters. Its focused RED was `1 failed` before `encodeURIComponent` was implemented.

### GREEN

Final focused contract result:

```text
5 passed, 19 warnings in 0.12s
```

The warnings are pre-existing SlowAPI deprecation warnings for `asyncio.iscoroutinefunction`.

## Verification

- `npx.cmd next typegen` — passed.
- `npx.cmd tsc --noEmit` — passed.
- `$env:NEXT_DIST_DIR='.next-task3'; npx.cmd next build` — passed on Next.js 16.2.2; 40 static pages generated and `/oferta/criadores` plus `/v/[id]` compiled successfully.
- `git diff --check` — passed (only Windows LF/CRLF notices).
- The isolated `.next-task3` artifact was removed and Next's temporary `tsconfig.json` include change was reverted; no lockfile changes were made.

## Self-review and residual concern

- Confirmed the public video uses only `/api/v1/public-shares/{token}/video`; the backend storage path never enters page props or markup.
- Confirmed showcase IDs are resolved from `showcase.json` before any API call.
- Confirmed failed registration does not clear attribution; successful registration clears UTM, referral and offer together.
- The backend exposes no owner-side read endpoint for an already-active share. After a reload the card safely shows `Publicar link`; that explicit, idempotent action recovers the existing link and then exposes copy/revoke controls. It does not publish automatically.

## Fix Review Findings

Review status addressed: `1 Critical + 3 Important`.

### RED

The Node 24 native TypeScript harness required no dependency or lockfile change:

```powershell
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --test src/lib/public-share-presentation.test.ts src/lib/qualified-view-scheduler.test.ts src/lib/registration-attribution.test.ts src/lib/public-shares.test.ts
```

Initial result: `11 tests, 0 passed, 11 failed`. Each failure was an assertion that the missing behavioral unit was not yet exported. A separate publish/revoke/gating target correction reproduced `2 tests, 0 passed, 2 failed`. A focused privacy hardening RED later proved the public display title helper was still absent (`2 passed, 1 failed`).

### Fixes

- `/v/[id]` now renders structured data only through `StructuredData/JsonLd`; its serializer escapes every literal `<`, including malicious `</script><script>...` titles.
- Dynamic public shares use a generic title, description, OpenGraph/Twitter text, image alt, visible heading/aria label and JSON-LD. Free-form job topic, e-mail, phone, Windows path and script payloads are recursively absent. Curated showcase titles remain intact.
- `QualifiedViewTracker` is now a thin DOM adapter over an injected scheduler. The scheduler accumulates only visible dwell, pauses while hidden, cleans timers, resets per token, ignores stale in-flight success, marks sent only after success and caps transient retries at `500/1500/3000ms`.
- Registration attribution and public-share action/gating logic moved to pure units covered by behavioral tests. The remaining Python source checks cover only Next/React wiring and required copy.

### GREEN and verification

- Node behavioral suite: `12 tests, 12 passed, 0 failed` (`213.4344ms`).
- `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_frontend_growth_contract.py`: `5 passed, 19 warnings in 0.08s`; warnings remain the pre-existing SlowAPI deprecation notices.
- `npx.cmd next typegen`: passed.
- `npx.cmd tsc --noEmit`: passed.
- `$env:NEXT_DIST_DIR='.next-task3-review'; npx.cmd next build`: passed on Next.js 16.2.2; all 40 static pages generated and `/v/[id]` compiled.
- The isolated build directory was removed and its generated `tsconfig.json` includes were reverted. `package-lock.json`, plan and progress were not changed.

## Final Fix: Lazy Anonymous Session ID

### RED

The scheduler regression was written before the implementation and run with:

```powershell
node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --test src/lib/qualified-view-scheduler.test.ts
```

Observed result: `6 tests, 5 passed, 1 failed`. At the first qualified send the transport ran, but the new lazy getter had not been called (`reads/writes/creations = 0` instead of `1/1/1`).

### Fix

- `QualifiedViewScheduler` now receives `getAnonymousSessionId` and invokes it only while constructing the first request after at least 5 seconds of accumulated visible dwell.
- The resolved UUID is cached by the scheduler: retries and a token-generation reset reuse it, while stale in-flight results remain ignored.
- `QualifiedViewTracker` passes the browser resolver by reference, so mount, hidden time, sub-threshold visible time and early disposal do not read or write storage and do not call `crypto.randomUUID()`.
- The behavioral test uses storage/factory spies to prove zero pre-qualification work, one lazy creation and payload at qualification, UUID reuse across retry/token reset, and zero work after disposal before 5 seconds.

### GREEN and verification

- Focused scheduler suite: `6 tests, 6 passed, 0 failed`.
- Full Node behavioral suite: `13 tests, 13 passed, 0 failed` (`260.1952ms`).
- `C:\Dev\clipia\.venv\Scripts\python.exe -m pytest -q tests/test_frontend_growth_contract.py`: `5 passed, 19 warnings in 0.12s`; warnings remain the pre-existing SlowAPI deprecation notices.
- `npx.cmd next typegen`: passed.
- `npx.cmd tsc --noEmit`: passed.
- `$env:NEXT_DIST_DIR='.next-task3-lazy'; npx.cmd next build`: passed on Next.js 16.2.2; all 40 static pages generated and `/v/[id]` compiled.
- The isolated build directory was removed and its generated `tsconfig.json` includes were reverted. `package-lock.json`, plan and progress were not changed.
