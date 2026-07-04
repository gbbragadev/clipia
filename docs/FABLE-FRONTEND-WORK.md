# Prompt de Tarefa — GLM-5.2 MAX: Engenharia frontend de alto impacto no ClipIA

> Cole este prompt como **mensagem do usuário** numa sessão GLM-5.2 MAX (via cglm, com /effort max) no repositório
> `C:\Dev\clipia`. Ele sobrescreve o modo "advisor" (`docs/FABLE-ADVISOR-SYSTEM-PROMPT.md`):
> aqui você **analisa E implementa** — escolhe, codifica, builda, committa. Não é auditoria pontual.

---

## MODO: engenheiro sênior product+frontend (você constrói)

Você é engenheiro sênior dono do frontend do ClipIA, com autonomia total para **editar código,
buildar e commitar**. Diferente do modo advisor, aqui seu combustível é **entregar melhorias
reais no produto**, não só apontar riscos. Use raciocínio de longo horizonte: leia o estado real,
escolha os 2-3 ataques de maior ROI, implemente com diff mínimo (lazy senior dev — reuse o que
existe, prefira stdlib/nativo, nenhum scaffolding especulativo), valide e commite.

## O que é o ClipIA (contexto essencial)

SaaS de geração automática de vídeos curtos (Shorts/Reels/TikTok) com IA. Stack frontend:
**Next.js 16 + React 19 + Remotion 4 + Tailwind 4**, identificidade coral/grafite (tokens CSS em
`var(--*)`, fontes Geist+Sora via `next/font`), ícones lucide-react, motion em `lib/motion.ts`.
Backend Python/FastAPI (não é seu foco direto, mas o frontend consome `/api/v1/*`). Deploy **=
este checkout** rodando no PC Windows do fundador via Cloudflare Tunnel — código não-commitado pode
estar em produção; sobreviva a `git reset` commitando.

## Estado atual (snapshot factual — 2026-07-02, branch `feat/frontend-elevacao`)

Já blindado (NÃO refazer — sonsole o `git log`):
- `25331ae` webhook Stripe normalizado (SDK≥15) · `c61f4fc` checkout Stripe-only (MP oculto) ·
  `27e7a9a` auto-restart nos launchers + health retry + fix do backup · `84cc357` admin credits
  reduzidos · `a81e10d` SECURITY.md + ROADMAP reordenado · `3544620` blocklist temp-mail 32→54.
- **337 testes pytest verdes** · `tsc --noEmit` limpo (após `npx next typegen`).
- **Produção está CAÍDA** (esperando o fundador rodar `start-production.ps1` com rede). Isso é
  **vantagem**: você pode editar/buildar livremente sem divergência working-tree × runtime; tudo
  que commitar entra na próxima subida.

## Sua missão (3 passos)

1. **Diagnóstico rápido (≤15 min):** leia `frontend/src/` — `app/`, `components/`, `lib/`,
   `contexts/`. Mapeie o que é polido vs o que parece cru/inconsistente/quebrado em mobile.
   Cruze com `docs/ROADMAP.md` (Eixo A — Qualidade; quick wins #1/#2/#3) e `docs/SECURITY.md`.

2. **Escolha 2-3 melhorias de ALTO IMPACTO** ordenadas por esforço×valor percebido. Candidatos
   prováveis (confirme lendo o código antes de adotar):
   - **UI de áudio rico** (SFX/música/mood já existem no backend por flag; expor toggles no
     editor/dashboard = vídeos mais profissionais sem novo backend). Provável maior ROI.
   - **Força de senha / feedback no register** (débito listado em `frontend-elevacao-fases`).
   - **Polish mobile dos fluxos logados** (gerar/editar no celular — há prints de smoke em `/`).
   - **Bottom-nav animada / drawer no editor mobile** (débito da elevação F2-3).
   - **Vozes pt-BR no diálogo** (`DIALOGUE_VOICE_A/B` ainda EN — quick win #2 do ROADMAP; 1 linha
     de config se as vozes existirem na conta ElevenLabs).
   - Consistência da design system (tokens, espaçamentos, estados de loading/erro/vazio).

3. **Implemente + valide + commite** cada melhoria em commit próprio (deploy = checkout).
   Para cada uma: diff mínimo, reusando padrões existentes.

## Guardrails INVIOLÁVEIS

- **Deploy = checkout:** todo trabalho precisa estar commitado ao terminar. Nada fica só no
  working tree.
- **Não mexa em `app/payments/` nem `app/auth/`** (pagamento e crédito já blindados nesta leva)
  sem um motivo forte e declarado.
- **Gates antes de commitar:** `cd frontend && npx next typegen && npx tsc --noEmit` limpo;
  `.venv312\Scripts\python.exe -m pytest -q` verde (só se tocou algo que o teste cobre).
- **prod caída = janela segura:** pode `npm run build` / editar à vontade. O fundador sobe depois.
- **Ponytail:** reutilize componentes/hooks/util que já existem; nenhum boilerplate "para depois".
- Commits em pt-BR, no padrão `feat(frontend): ...` / `fix(frontend): ...`.

## ⚠️ GOTCHAS DO AMBIENTE (vão te travar se não ler — já confirmados nesta máquina)

1. **O hook do plugin `claude-mem` (thedotmack) bloqueia `Read`** (worker morto, `PreToolUse:Read`
   retorna erro e a tool falha). **Contorne lendo via shell** (`cat -n <file>` no Bash tool) **ou
   use `Write`** (não passa por esse hook). Para editar arquivos existentes sem poder dar `Read`:
   crie um script `.cjs` via `Write` que faz o string-replace e rode com `node`.
2. **O wrapper de shell (RTK/lean-ctx) colapsa `\\` → `\` em comandos bash** (quebra paths Windows
   e escapes). **Solução:** escreva scripts `.cjs` via `Write` (o conteúdo é preservado literal) e
   execute com `node /tmp/x.cjs`. Evite heredoc bash com barras invertidas.
3. **Next 16:** `npx next typegen` é obrigatório antes de `tsc --noEmit` (gera tipos de PageProps).
4. **MSYS path-mangling:** argumentos que começam com `/` no Git Bash viram path Windows
   (ex.: `/create` → `C:\...\create`). Para `schtasks` e afins, use o **PowerShell tool**.
5. `lean-ctx` reclama de paths Windows com `\` em `tail`/`cat` — use paths POSIX (`/c/...`).

## Pendências do FUNDO (NÃO TENTE — precisam de painel/rede, fora do agente)

- Subir prod: `! powershell -File scripts\start-production.ps1` (rede).
- Ligar Turnstile: passo a passo em `docs/SECURITY.md` (gerar chave no painel Cloudflare).
- Confirmar webhook Stripe + ativar Pix no painel Stripe.
- Uptime externo (UptimeRobot) + cópia do backup pra fora via rclone.

## Formato de saída (ao terminar)

Recap curto em 4 blocos (🎯 pedido · ✅ feito c/ status de verificação · 🧭 decisões+pendências do
fundo · 📍 arquivos/commits). Máximo de honestidade: se algo não foi validado de verdade, diga.
Verde de teste não é evidência se mockou o runtime — prefira `next build` + smoke visual quando
fizer sentido.

---

**Primeira ação esperada:** não pergunte "por onde começo" — leia `frontend/src/`, faça o
diagnóstico, declare os 2-3 ataques escolhidos (com `arquivo:linha` justificando), e execute o
primeiro. Há permissão total de edição/build/commit dentro dos guardrails.
