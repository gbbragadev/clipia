# Verificação F5 — Reforma UX do app logado (10/07/2026)

> Branch `feat/editor-mobile-ux`, commits `e96d739..f563150` (9 commits da reforma).
> Evidências: `frontend/F5-*.png` (preview isolado 3105) e `frontend/F0-*.png` (antes).

## Resultados de máquina

| Check | Resultado |
|---|---|
| `npx tsc --noEmit` | exit 0 (rodado após F1, F2, F3, F4 e retoques) |
| `next build` isolado (`NEXT_DIST_DIR=.next-verify`) | exit 0 (prod 3003 intocado) |
| pytest | 380 passed + 3 novos (config/thumbnail) · 7 falhas PRÉ-existentes de payments (gotcha `.env` promo=20 — área não tocada) |
| Console (dashboard/credits/editor, desktop+mobile) | Sem erro JS. 404 esperado de `/api/v1/config` (backend de prod ainda sem restart) com fallback funcionando; warnings de preload de fonte pré-existentes |

## Antes → Depois (evidência visual)

- **Grid de vídeos**: 3 col. gigantes sem thumbnail → **4 col. + StatusBadge pt-BR
  tokenizado** (F0-03 → F5-02). Posters reais aparecem quando o backend reiniciar
  (70 JPEGs já gerados via backfill; rota testada por unit test).
- **Dashboard**: feed de trends em inglês dominando a 1ª dobra → **"Criar novo vídeo"
  primeiro**, painel de ideias pt-BR compacto com feed cru colapsado (F0-01 → F5-01).
- **Editor aba IA**: custo oculto → **CostChip "0,5 crédito por consulta, somado ao
  próximo export"** no topo (F0-09 → F5-05).
- **Timeline**: 6 cores arbitrárias → neutra com ativa coral (F5-05).
- **Credits**: badge/CTA roxos → gradiente da marca; "por crédito" → "≈ por vídeo com
  voz padrão" (narrativa da landing); "Pendente" com explicação no hover.
- **Roxo na UI**: 0 ocorrências restantes (`#6366f1`/`#8b5cf6`/`#e879f9`/`purple` —
  exceções legítimas: presets de conteúdo do usuário).
- **Light theme**: aposentado (bloco CSS + toggle removidos; -146 linhas).

## Guardrails de confiança (DESIGN.md) — conferidos

- [x] Custo antes de TODA ação paga: gerar (já tinha), export (já tinha), regenerate-TTS
  (CostChip grátis/2cr por voz), AI Suggest (0,5 diferido + acumulado), voice design
  (5cr), reset (modal com custo), clone (1cr no tab).
- [x] Números prometidos via backend: `GET /api/v1/config` + `lib/config.ts`; banner de
  verificação, strings e metadata neutralizados (fim do "2 créditos" hardcoded).
- [x] Status pt-BR via StatusBadge em VideoCard e PurchaseHistory.
- [x] Ações destrutivas/pagas com Modal acessível (portal/Esc/foco): reset do editor,
  créditos insuficientes; cancel de job já tinha confirmação inline.
- [x] Botão desabilitado explica o porquê (hint no Gerar Vídeo).

## Checklist de tela (impeccable / ui-ux-pro-max)

- [x] 1440×900 e 390×844 sem quebra (F5-01..07); MobileBottomNav e FAB ok; padding
  reservado pro FAB da timeline no editor mobile.
- [x] Contraste: textos de leitura em cloud/mist sobre ink/panel (≥4.5:1); text-gray-600
  do custo trocado por token legível.
- [x] Esc/foco nos modais novos; aria-labels adicionados (Cancelar etc.);
  reduced-motion coberto pela rede de segurança global.
- [x] Estados: skeletons (grid/trends), empty states, InlineError com retry preservados.

## Pendências para o deploy (precisa de OK)

1. Frontend: build de produção + `restart-frontend.ps1` (sem -Rebuild se buildar antes
   no shell — a schtask falha por PATH do npm).
2. **Backend (uvicorn)**: restart p/ ativar `/config` e `/jobs/{id}/thumbnail`.
3. **Worker (celery)**: kill (o loop do `_run-worker.ps1` respawna) p/ ativar o
   thumbnail no finalize.
4. Smoke pós-deploy: posters visíveis na grid + `/config` 200 + geração de 1 vídeo de
   teste com conferência de débito/estorno das ações pagas.
