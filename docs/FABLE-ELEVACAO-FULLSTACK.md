# Prompt de Tarefa — Fable 5: Elevação profissional do ClipIA (core + dashboard + editor + build)

> Cole este prompt como **mensagem do usuário** numa sessão Fable 5 (`/effort max`) no repositório
> `C:\Dev\clipia`. Ele sobrescreve o modo "advisor" (`docs/FABLE-ADVISOR-SYSTEM-PROMPT.md`):
> aqui você **analisa E implementa** — diagnostica, escolhe, codifica, builda, commita e reinicia
> o frontend. Não é auditoria pontual. Use `docs/PLANO-EXPANSAO.md` como backlog priorizado por ROI.

---

## MODO: engenheiro sênior product+fullstack (você constrói e opera)

Você é engenheiro sênior dono do produto ClipIA end-to-end, com autonomia total para **editar código
frontend E backend, buildar, commitar e reiniciar o frontend em produção local**. Combustível seu é
**entregar melhorias reais e percebidas no produto** — UX, performance de geração, acesso ao vídeo
final, acabamento visual. Pense em longo horizonte: leia o estado real do código (com `arquivo:linha`),
escolha os 2-3 ataques de maior ROI por sprint, implemente com diff mínimo (lazy senior dev — reuse o
que existe, prefira stdlib/nativo, zero scaffolding especulativo), valide com build+smoke, commite.

Sua vara de medir "bom o bastante": **o produto ficaria bem numa review da comunidade Indie Hackers
ou Product Hunt.** Padrão visual de referência:
- **Linear, Vercel e Raycast** para a shell (dashboard/auth) — densidade alta, micro-interações sutis,
  velocidade percebida, foco no conteúdo.
- **Cap, Descript e Runway** para o editor/player — creative tool de verdade: timeline rica, preview
  poderoso, atalhos de teclado, feedback visual em cada gesto.
- **Arc e Vercel dashboard expressivo** são permitidos **no lugar certo** — hero, transições de
  página, empty states com personalidade, gradientes de marca — sem virar ruído na operação repetitiva.

## O que é o ClipIA (contexto essencial)

SaaS de geração automática de vídeos curtos (Shorts/Reels/TikTok) com IA. Fluxo: tema → roteiro
(LLM em cascata) → TTS pt-BR (ElevenLabs→Edge) → legendas (Groq Whisper) → mídia
(Pexels/Drive-CLIP/gpt-image/Seedance) → composição (FFmpeg/NVENC) → editor WYSIWYG Remotion
(editor==export) → render. ICP: criadores de canais "dark"/faceless pt-BR. Diferencial: pt-BR nativo
ponta-a-ponta, editor fiel (preview==export), preço em R$ com Pix, 2 vídeos grátis sem cartão.

Stack frontend: **Next.js 16 + React 19 + Remotion 4 + Tailwind 4** (CSS-first, sem
`tailwind.config`), identidade **coral/azure/grafite** (tokens em `globals.css` `@theme`, fontes
**Geist+Sora** via `next/font` — NÃO Inter), ícones `lucide-react`, animação `motion` (pacote novo do
Framer, import `motion/react`), helpers em `lib/motion.ts`. Fronteira respeitada: site público =
Tailwind v4 utilities; **editor = `editor.css` BEM** (mantida separada); **motion só no shell — nunca
dentro de composições Remotion** (quebra a renderização server-side).

Backend Python/FastAPI (rotas `/api/v1/*`), worker Celery `--pool=solo` (concorrência 1, gargalo
conhecido), Postgres/Redis, GPU GTX 1660 4GB. Deploy **= este checkout** rodando no PC Windows do
fundador via Cloudflare Tunnel — código não-commitado pode estar em produção; **sobreviva a
`git reset` commitando tudo**.

## Estado atual (snapshot factual — 2026-07-03, branch `feat/frontend-elevacao`)

Já blindado (NÃO refazer — console o `git log` antes): Turnstile no cadastro (`92dbdac`), backup R2
funcional (`46ed556`), voice clone + cancel/reset de job + bottom-nav mobile (`a65bcae`), remoção de
dead code roxo (`05530a9`). ~347 testes pytest verdes. `tsc --noEmit` limpo após `npx next typegen`.

**Fronteiras de identidade ainda abertas (o trabalho real):**
- **Roxo residual** nos gradientes ambientais do app (`globals.css:31-33,94-96`) — migração coral
  começou na landing mas NÃO terminou no dashboard/editor. `--accent-primary` indefinido em `:root`
  (usava fallback hardcoded em `credits/page.tsx:71`).
- **Download quebrado e confuso** (BUG REPORTADO PELO FUNDADOR): `ExportPanel.tsx:102-187`
  auto-renderiza (~2min NVENC) mas o botão "Baixar Vídeo" já está ativo e baixa a versão
  **pré-edição**; `downloadAuthenticatedFile` (`lib/download.ts:25-33`) é blob-em-memória
  **sem spinner/progresso** (botão parece morto em 4G); **não existe player/acesso rápido ao vídeo
  final** fora do hover mudo do card (`VideoCard.tsx:79-94`).
- **`ExportPanel` 100% inline styles** (`#222222` hardcoded) — ignora o design system inteiro.
- **Job em `processing` não atualiza sozinho na grid** — só recarrega no `onJobComplete`.
- **`EmptyState` fraco** (🎬 + 1 linha, sem CTA/ilustração).
- **Arquivo morto `components/editor/EndScreen.tsx` vazio** (duplicata do ativo em `overlays/`).
- **Dark/light toggle sem wiring** (`ThemeToggle.tsx` existe mas `data-theme` não vai pro `<html>`).
- **Worker `--pool=solo`** = 1 job por vez; vídeo IA (timeout 780s) bloqueia a fila inteira.
- **Cascata LLM sem flag de degradação** (`llm.py:90` só loga warning) — usuário paga crédito por
  vídeo pior quando cai para fallback free.
- **Nicho não é "especial" no backend** — só SEO no frontend; `trends.py:38` ancora mas não diferencia
  roteiro/mídia/voz por nicho.

## SUA MISSÃO (4 passos — faça em ordem)

### Passo 1 — Diagnóstico grounded (≤20 min)
Leia via shell (gotcha #1 abaixo): `frontend/src/app/globals.css`,
`frontend/src/app/dashboard/page.tsx`, `frontend/src/app/dashboard/layout.tsx` +
`DashboardLayoutClient.tsx`, `frontend/src/components/dashboard/` (`VideoGrid.tsx`, `VideoCard.tsx`,
`EmptyState.tsx`, `GenerateForm.tsx`), `frontend/src/components/editor/` (`EditorLayout.tsx`,
`editor.css`, `ExportPanel.tsx`, `VideoPlayer.tsx`), `frontend/src/lib/` (`download.ts`,
`editor-api.ts`, `motion.ts`), `frontend/src/contexts/` (`AuthContext`, `EditorContext`). Cruze com
backend: `app/api/routes.py` (`download_job`, `list_jobs`, `render`), `app/worker/tasks.py`
(`dispatch_pipeline`, `task_rerender_video`). Declare um mapa curto: o que está polido vs o que
precisa de UX/core/build, **com `arquivo:linha`**.

### Passo 2 — Corrija os BUGS REPORTADOS primeiro (MANDATÓRIO, sem exceção)
Estes são dor real do fundador hoje. Faça em commit(s) próprio(s) **antes de qualquer polimento**:
1. **Acesso rápido ao vídeo final + player dedicado.** Modal/rota de "assistir" no dashboard com
   player `<video>` autenticado (reaproveite `fetchAuthenticatedBlobUrl` de `lib/download.ts:35`),
   controles nativos, share/copy-link, CTA de download. Hover do card abre esse modal — não preview
   mudo.
2. **Download confiável e com feedback.** Elimine a condição de corrida do `ExportPanel`: botão de
   download só habilita **depois** do render terminar (state machine `idle → rendering → ready`).
   Substitua o blob-em-memório por **streaming via `Range`/link pré-assinado** quando possível, ou no
   mínimo **spinner no botão + progresso estimado + toast de sucesso/erro**.
3. **Grid que se atualiza sozinha.** Job em `queued`/`processing` faz polling leve
   (`fetchJobStatus` via `editor-api.ts:258`) no próprio card ou na grid inteira, com backoff, e
   atualiza badge/progresso em tempo real. Pare o polling quando vira `completed`/`failed`.

### Passo 3 — Eleve o acabamento visual ao nível profissional (2-3 frentes por sprint)
Benchmark: Linear/Vercel/Raycast (shell) + Cap/Descript/Runway (editor). **Não mude a direção coral —
refine.** Priorize:
- **Unifique a paleta:** elimine o roxo residual (`globals.css:31-33,94-96`), defina
  `--accent-primary`/`--accent-secondary` em `:root`, migre `ExportPanel` para o design system
  (remova inline styles, use `.card` + tokens).
- **Design tokens completos:** escala tipográfica consistente (já tem `.h-display/.h-1/.h-2`),
  espaçamentos (`--space-*`), raios, sombras, elevação. Documente o uso em
  `docs/FRONTEND-ELEVACAO-REVISAO.md`.
- **Estados impecáveis:** loading skeletons reais (não `animate-pulse` genérico), empty states com
  ilustração/CTA (substitua `EmptyState.tsx` fraco), error states com retry, transições de página
  via `lib/motion.ts` (fadeUp/stagger). **Toasts consistentes** (reaproveite `ui/feedback.tsx` em todo
  lugar, inclusive `ExportPanel`).
- **Micro-interações sutis:** hover/focus states, transições de 150-200ms
  `cubic-bezier(0.22,1,0.36,1)`, shimmer em skeletons, badges pulsantes só onde comunicam estado
  (job ativo). Respeite `prefers-reduced-motion` (já global em `globals.css:221`).
- **Dashboard com densidade e personalidade:** header com saudação já existe — eleve com quick-actions,
  métricas resumidas (créditos, vídeos este mês, template favorito), atalhos de teclado (`g d`, `g e`,
  `n` para novo vídeo). Filtros/ordenação rica na grid.
- **Editor de creative tool:** preview Remotion já é WYSIWYG — deixe-o **instantâneo** (seek, scrubbing
  suave), adicione atalhos (espaço play/pause, setas avançar frame, `S` split, `M` mute), feedback
  visual no split/move de cena, mini-map da timeline. Inspector de cena rico (duração, mídia, voz,
  legenda — tudo editável inline).

### Passo 4 — Faça o build e reinicie o frontend (alcance total autorizado)
Após cada commit de impacto (ou lote coerente), valide e reflita em produção local:
```
cd frontend && npx next typegen && npx tsc --noEmit   # gate de tipos
npm run build                                           # gate de build
powershell -File scripts\restart-frontend.ps1 -Rebuild # reflete em prod local
```
Rode um **smoke visual** (Playwright ou browser manual): landing → login → dashboard → gerar um vídeo
Edge (1 crédito) → abrir player → baixar → editar → exportar. Capture screenshots em `/` nomeados
`LIVE-elevacao-<area>-<data>.png` como evidência no formato de saída.

## Guardrails INVIOLÁVEIS

- **Deploy = checkout:** todo trabalho precisa estar commitado ao terminar. Nada fica só no working
  tree. Sobreviva a `git reset`.
- **Não mexa em `app/payments/`** (cobrança/webhook já blindados nesta leva) sem motivo forte e
  declarado. **`app/auth/` pode mexer** se for para suportar uma feature de UX (ex: feedback de força
  de senha, sessão) — mas rode os testes de auth.
- **Gates antes de commitar:** `cd frontend && npx next typegen && npx tsc --noEmit` limpo;
  `.venv312\Scripts\python.exe -m pytest -q` verde se tocou backend; `npm run build` verde **antes de
  reiniciar o frontend**. Nunca reinicie com build vermelho.
- **Worker Celery `--pool=solo` é realidade:** não aumente concorrência sem coordenar com o fundador
  (GPU 4GB). Para paralelismo, prefira otimizar o pipeline existente (ex: pré-baixar mídia enquanto o
  roteiro roda) em vez de subir workers novos.
- **Motion só no shell, nunca dentro de composições Remotion** (quebra render server-side).
  `prefers-reduced-motion` sempre respeitado.
- **Fronteira visual mantida:** Tailwind v4 (público) × `editor.css` BEM (editor). Não misture.
- **Lazy senior dev:** reuse `ui/feedback.tsx`, `lib/motion.ts`, `lib/http.ts`, `lib/download.ts`,
  `lib/editor-api.ts`, hooks `useIsMobile`/`useReducedMotionState`. Nenhum boilerplate "para depois".
- **Novo componente só se reusar os tokens existentes falhar** (Ponytail).
- Commits em pt-BR, padrão `feat(frontend): ...` / `fix(frontend): ...` / `refactor(frontend): ...`
  / `feat(editor): ...` / `feat(dashboard): ...` conforme o escopo.

## ⚠️ GOTCHAS DO AMBIENTE (vão te travar se não ler — confirmados nesta máquina)

1. **O hook do plugin `claude-mem` bloqueia `Read`** (worker morto, `PreToolUse:Read` retorna erro).
   **Contorne lendo via shell** (`cat -n <file>` no Bash) **ou use `Write`** (não passa por esse hook).
   Para editar arquivos existentes sem `Read`: crie um script `.cjs` via `Write` que faz string-replace
   e rode com `node`.
2. **O wrapper de shell colapsa `\\` → `\` em bash** (quebra paths Windows e escapes). Solução:
   scripts `.cjs` via `Write` (conteúdo preservado literal) executados com `node`. Evite heredoc bash
   com barras invertidas.
3. **Next 16:** `npx next typegen` é **obrigatório** antes de `tsc --noEmit` (gera tipos de PageProps).
4. **MSYS path-mangling:** args que começam com `/` no Git Bash viram path Windows (ex.: `/create` →
   `C:\...\create`). Para `schtasks` e afins, use o **PowerShell tool**.
5. `lean-ctx` reclama de paths Windows com `\` em `tail`/`cat` — use paths POSIX (`/c/...`).
6. **`scripts/restart-frontend.ps1`** pode demorar ~30s e derrubar a conexão do tunnel — aguarde o
   healthcheck voltar verde antes de declarar sucesso.

## Pendências do FUNDO (NÃO TENTE — precisam de painel/rede/humano, fora do agente)

- Subir prod do zero: `start-production.ps1` (precisa de rede e gesto humano).
- Ativar Turnstile / registrar webhook Stripe / ativar Pix no painel Stripe / webhook MP.
- Uptime externo (UptimeRobot) + cópia do backup pra fora via rclone.
- Aumentar concorrência do worker (GPU/dinheiro) — só com fundador.
- Features do `docs/PLANO-EXPANSAO.md` marcadas como **[PRÓXIMO TIER]** ou **[MOONSHOT]** — só após
  go-live e com mais usuários pagos; não improvisar agora.

## Formato de saída (ao terminar cada sprint)

Recap curto em 4 blocos:
- **🎯 pedido** — o que esta sprint atacou.
- **✅ feito** — cada item com status de verificação real (`next build` verde, smoke rodado, screenshot
  capturado). Se algo não foi validado de verdade, diga.
- **🧭 decisões** — escolhas de design/trade-offs + pendências do fundo que esbarrou.
- **📍 arquivos/commits** — lista de `arquivo:linha` tocados + hashes de commit + paths de screenshots.

Verde de teste não é evidência se mockou o runtime — prefira `next build` + smoke visual. Para bugs
reportados (download/player/grid), **mostre o antes/depois com screenshot ou relato factual de como
reproduziu o fix**.

---

**Primeira ação esperada:** não pergunte "por onde começo" — faça o diagnóstico grounded (Passo 1),
declare os 3 ataques escolhidos com `arquivo:linha` justificando, **comece obrigatoriamente pelos bugs
de download/player/grid do Passo 2** (são dor real hoje), depois avance para o Passo 3. Há permissão
total de edição/build/commit/restart dentro dos guardrails.
