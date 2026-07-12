# Triagem adversarial — auditoria GPT-5.6 Sol (12/07/2026, madrugada)

> Fonte: `docs/INSIGHTS-GPT56-2026-07-12.md` (25 achados, Codex gpt-5.6-sol, read-only).
> Contrato /loops adaptado: finders = o relatório externo; Verify = 6 céticos `agency-cetico`
> (1 por achado sério de dinheiro/perf) + verificação direta do orquestrador nos 19 restantes.
> Gate: delegado ao orquestrador (Gui dormindo — "finalizar tudo sem precisar de mim"),
> critério conservador. **Deploy NÃO feito** (trava explícita: "não faça deploy sem confirmação").

## Custo da rodada

6 subagentes céticos (Fable) + ~30 leituras diretas. Baseline 435 → **445 testes verdes**
(10 novos). `next typegen` + `tsc --noEmit` = 0 erros. 6 commits (`aa045b1..`).

## Veredictos dos céticos

| Achado | Veredicto | Nota do cético |
|---|---|---|
| ai_video conta não fecha (P0) | PLAUSIBLE | Clamps globais EXISTEM (40 máx, 12 a 45s); buraco real = custom_script a 180s (~R$130/30cr) + telemetria por `sum(hints)` quando Seedance cobra `len(scenes)×5s`. Recomendou teto 8 escalado, NÃO os 6 fixos do GPT (cortaria vídeos de 60s). |
| dialogue_duo subcobrança (P1) | CONFIRMED | Integral; repro por curl; sem teste cobrindo; edge não faz diálogo → zero uso legítimo do payload. |
| Custo ignora refinos (P1) | CONFIRMED | Cenário 402 alcançável (saldo 1 + refine_owed 1.0); lote soma refino 1× (liquidado no 1º POST). |
| Clipes órfãos em cancel (P1) | CONFIRMED **pior** | Cancelar durante o poll de 6-10min deixava o job COMPLETAR e COBRAR (check só na entrada da task). Fix mínimo = check entre polls (~5 linhas, 0 latência); Semaphore NÃO recomendado (3× wall-clock). |
| Sliders remontam Player (P1) | CONFIRMED c/ ressalva | ~52 remounts por drag, real; MAS a matriz E2E de fidelidade foi validada COM remounts — remover `key=version` arrisca a promessa central. Fix seguro = throttle nos sliders. |
| Keystroke invalida árvore (P1) | CONFIRMED c/ correção | Player NÃO remonta por texto (signature não inclui scene.text); dano real = 1 undo/tecla (estoura MAX_HISTORY=50) + re-render do preview. |

## Aplicados (19) — commits `aa045b1`, `worker`, `seo`, `8e70775`, `3c2abc8`

**Dinheiro/contrato**: dialogue_duo pricing server-side (`routes.py`, + teste endpoint) ·
teto próprio ai_video `MAX_SCENES_AI_VIDEO=8` escalado (scriptwriter + validador custom_script,
+3 testes) · telemetria por `len(scenes)×5s` (+teste) · cancel no poll do provider +
tratamento como cancelamento no worker (+2 testes) · `/generate` 202 (+13 asserts migrados) ·
custo exibido soma `floor(refinePending)` no gate/microcopy/modal (1× no lote) + `credit_cost`
tipado na resposta.

**Ativação**: e-mail "vídeo pronto" idempotente (SET NX, best-effort, deep-link `/editor/{id}`,
+3 testes) · signup_intent de nicho → prefill único no dashboard pós-OTP.

**SEO/OG**: sitemap (blog in, auth out) · noindex nos 3 layouts de auth · blog cluster
(footer, canonical, twitter, BlogPosting, interlinks) · claims falsos do blog corrigidos
(RTX 3090, "2 min", R$9,90→19,90) · JSON-LD SoftwareApplication só na home · `/v/[id]` com
og:image/twitter/VideoObject próprios (Next 16 substitui openGraph inteiro — cards saíam sem
imagem) · galeria → link `/v/{id}` · copy de bônus estável (15+ strings) · 16 posters/OG
reais gerados por ffmpeg dos MP4s do showcase.

**Perf/a11y**: hero com poster + `preload="metadata"` (7,1MB fora do LCP, autoplay preservado) ·
RAF ocioso removido dos 2 canvases (redesenhavam o mesmo frame 6×, até pausado) · FilmGrain
estático (era ImageData 128×128/150ms em toda rota) · ThrottledRange nos 5 sliders ·
texto de cena com rascunho local + debounce 400ms/blur · Modal com focus trap · role=alert
nos erros de auth.

## Rejeitados / não aplicados agora (com motivo)

- **Teto de 6 cenas fixo (ação original do GPT)**: cortaria vídeos legítimos de 60s+;
  aplicado 8 escalado (cético + conta da casa em `config.py`).
- **Remover `key=version` do Player**: risco de regressão da fidelidade preview==export
  (validada COM remounts); mitigado com throttle; remoção só com browser real → backlog.
- **Privacidade GA/Pixel (P1 do GPT)**: REFUTADO como problema atual — IDs ausentes do env
  (verificado), nenhum tracker ativo, política correta hoje. Vira guarda pré-ads (decisão
  do Gui: analytics-only vs CMP) → backlog.
- **Loop /v de usuário (P0)**: JÁ CONHECIDO (comentário no código: decisão de produto
  pendente); aposta estrutural L → backlog. Mini-loop do showcase aplicado primeiro.
- **Imagens IA paralelas / fila re-render / clipes órfãos completo / 5 páginas
  programáticas / seção premium na landing**: M cada, exigem deploy+validação real ou
  decisão de conteúdo → backlog (detalhado no BACKLOG-AUDITORIA).

## Verify

- `pytest -q`: **445 passed** (435 baseline + 10 novos) — 2 rodadas completas (pós-fix e pós-ruff).
- `npx next typegen`: 0 erros/0 warnings · `npx tsc --noEmit`: 0 erros.
- `next build`/smoke NÃO rodados: o `.next` do repo é o servido em prod (incidente 10/07) e
  o deploy está travado aguardando confirmação do Gui.
- Gotcha novo: `ruff format app tests` global reformatou 24 arquivos FORA do escopo —
  revertidos com `git checkout` antes dos commits (formatar só os arquivos tocados).

## Pendências para o Gui (deploy)

1. OK para deploy → frontend `restart-frontend.ps1 -Rebuild` + backend via schtask
   temporária + kill do worker (processo específico, NÃO regex `celery.*worker` — mata o
   beat junto e o beat não respawna).
2. Smoke logado em clipia.com.br + validar OG do `/v` em browser real (WhatsApp debugger).
3. Decisões: guarda pré-ads (CMP vs analytics-only) · pricing por clipe do ai_video
   (médio prazo) · nº de créditos grátis na copy quando definir o valor público.
