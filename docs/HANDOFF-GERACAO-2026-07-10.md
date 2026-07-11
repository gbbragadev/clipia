# Handoff — Frente "Experiência de Geração" (10-11/07/2026)

Sessão que consertou o core do produto. Este arquivo reancorra a próxima sessão
(qualquer host: Claude/GLM/Codex) sem depender de memória de conversa.

## O que está NO AR (deploy completo, verificado ao vivo)

- **Branch**: `feat/editor-mobile-ux`, commits `7561860..4a4a5b5` (15), **pushada**
  para `origin` (github.com/gbbragadev/clipia) — primeiro push da branch.
- **Frontend 3003**: build novo servindo (form com lote/variações, stepper, roteiro
  avançado real, aba Economia no admin).
- **Backend 8005**: rotas novas ativas (`/script-preview`, `/script-preview/refine`,
  `/example-topics/{nicho}`, `/admin/economy`, `queue_position` no `/jobs`).
- **Worker + BEAT**: rodando o código novo. GOTCHA descoberto no deploy: `celery
  worker -B` é REJEITADO no Windows → o beat roda como processo separado
  (`scripts/_run-worker.ps1`, commit `a3e7cb8`). Primeira vez na história do projeto
  que os cleanups agendados rodam.
- **Watchdog**: ativo (thread no worker, passada a cada 5min) e **provado ao vivo** —
  ceifou 3 jobs-lixo estagnados há 93min na primeira passada.

## A prova dos nove (medida em produção)

| Métrica | Antes | Depois |
|---|---|---|
| Vídeo de imagens IA (60s, Drama Histórico) | **3h39** | **5min12s** (job `5a821c34`) |
| Etapa compositing | ~92min | **34s** |
| Custo API estimado/vídeo (imagens IA) | — | $0,43 (5 créditos ≈ R$6,50) |

Gargalo atual: `generating_images` (4min12 = API externa gpt-image). Telemetria
completa no JSONB `Job.telemetry` e na aba **Admin → Economia**.

## Decisões desta frente (não re-litigar)

- Lote: variações ×N **e** fila de temas, cap 5, Modal de custo antes, POSTs sequenciais.
- Roteiro: 1º rascunho **grátis** (anti-farming: saldo + cap 10/h); refino 0,5cr
  acumulado em Redis com **floor+carry** (2 refinos = 1 crédito; nunca cobra a mais).
- Diálogo (2 vozes): capability por template (5 liberados), custo = pricing elevenlabs
  decidido **server-side**.
- Escala: sem infra nova; gatilhos numéricos em `docs/PLANO-ESCALA.md`.
- Reaper de queued: 6h (60min mataria fila legítima — o Postgres fica "queued"
  durante todo o processamento).

## Pendências / próxima sessão

1. **Reforma do EDITOR** (pedido explícito do Gui: "sessão futura separada, mesmo
   espírito") — usar a skill `frontend-fable` + este fluxo de plano.
2. **Merge para main + PR?** A branch está pushada; main local/remota seguem atrás.
   Decisão do Gui.
3. Casca vazia `\.claude\worktrees\audio-voices` resiste a remoção (0 arquivos, ACL
   órfã de pytest-tmp) — remove num reboot/takeown; branches obsoletas já deletadas
   (fluxo-unificado-drive, landing-valor-imagens, nav-login-state, audio-rico — todas
   com conteúdo incorporado ou superseded).
4. Untracked intencionais (de outras sessões, NÃO tocar sem contexto): `marketing/`,
   `samples veo/`, `dashboard-mockup.html` (raiz e `frontend/public/`), `test_sub.ass`.
5. Margem ElevenLabs é a mais apertada — vigiar na aba Economia (gatilho 4 do
   PLANO-ESCALA).
6. 1010: pendências #212 (ações pagas ao vivo), #185-188 (créditos/Pix/watermark/A-B).

## Gotchas para o próximo host (os que doeram)

- **`set X=Y&& cmd` no tool Bash NÃO exporta** (git bash!) → o build de verificação
  caiu no `.next` de produção e derrubou o site ~10min. Build isolado SEMPRE via
  PowerShell: `$env:NEXT_DIST_DIR='.next-verify'; npm run build`.
- `celery -B` não existe no Windows; beat = processo separado (já resolvido no script).
- Time limits do Celery = no-op no pool solo/Windows. Não confiar; o watchdog cobre.
- `create_access_token(user_id_string)` — recebe a STRING, não dict (smoke logado).
- zoompan multiplica frames por frame de ENTRADA: sempre `-frames:v` no output.
- ruff-format aborta commit e o stage sobrevive; RTK quebra `git commit -m` multilinha
  → mensagem via `-F arquivo` ou Bash tool.

## Referências

- Plano executado: `~/.claude/plans/como-fizemos-a-remodelagem-atomic-sutherland.md`
- Memória: `~/.claude/projects/C--dev-clipia/memory/geracao-core-pipeline-fix.md`
- Economia/escala: `docs/PLANO-ESCALA.md` · Roadmap qualidade: `docs/ROADMAP-QUALIDADE-VIDEO.md`
- 1010 sessão 73 (+ update ao fim desta) com `nextPrompt` pronto.
