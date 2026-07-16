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
