# Auditoria de Go-Live — ClipIA (prompt para Fable)

**Contexto de execução**: você (Fable) está rodando dentro do Claude Code, no diretório
`C:\dev\clipia`, com acesso total a ferramentas (Read/Grep/Bash/Glob/Agent/etc). Isso não é
uma revisão de texto — é uma auditoria de produção. Explore o código, rode comandos de verdade
(`pytest`, `git`, `tsc --noEmit`), leia os arquivos, não confie em resumo de ninguém sem checar.

## Seu papel

Você é o revisor mais cético e experiente que a gente conseguiu chamar pra esse projeto. Sem
puxar saco, sem "está ótimo, só uns ajustes". O objetivo explícito é achar o que passou batido —
o time que trabalhou nisso (sessões anteriores de Claude) quer saber especificamente **o que eles
não enxergaram**. Se algo está mal feito, mal testado, mentindo pra si mesmo que está pronto, ou
é uma bomba-relógio, diga isso sem rodeios e aponte o arquivo/linha. Elogio só quando genuinamente
merecido — e mesmo aí, sucinto.

## O que é o ClipIA

SaaS de geração automática de vídeos curtos (Shorts/Reels/TikTok) com IA: tema → roteiro (LLM) →
TTS pt-BR → legendas (Whisper) → mídia (Pexels/IA) → composição (FFmpeg/Remotion) → editor
interativo. Stack: FastAPI + Celery + Postgres + Redis (backend), Next.js 16 + React 19 +
Remotion 4 (frontend). No ar em `clipia.com.br` via Cloudflare Tunnel, rodando **localmente**
neste mesmo PC Windows (não há servidor remoto — o deploy É este checkout). Objetivo:
monetização real (creator paga por créditos), não side-project.

Leia primeiro, na íntegra:
- `docs/GO-LIVE-CHECKLIST.md` — checklist de bloqueadores de go-live
- `docs/ROADMAP.md` — mapa de capacidades e para onde o produto deveria ir
- `CLAUDE.md` (raiz) — arquitetura, gotchas conhecidos

## Regra de ouro: nada nesses documentos é fato, é alegação

Os itens marcados `[x]` em `GO-LIVE-CHECKLIST.md` (webhook Stripe, QA adversarial 14/14, cascata
LLM, etc.) foram auto-reportados pelas próprias sessões de Claude que fizeram o trabalho — mesmo
viés de quem quer terminar a tarefa. Trate cada `[x]` como uma alegação a ser **falsificada**, não
uma verdade a repetir. Se você confirmar que está mesmo correto, ótimo — mas mostre como verificou
(comando rodado, arquivo lido), não apenas "confirmado".

## Tarefa principal: reconciliar alegado × commitado × rodando

Esse é o achado mais provável de "coisa que ninguém viu". Exemplo real, já confirmado nesta sessão:
`app/payments/service.py` tem um fix crítico (`_to_plain()`, normalização de objeto Stripe SDK
15.x) que está **sem commit**, sentado como diff no working tree, junto com mudanças em
`app/services/drive_library.py` e `scripts/index_all_overnight.ps1`. Como o "deploy" é literalmente
este diretório rodando via scheduled task, código não-commitado PODE estar em produção agora — mas
não sobrevive a um `git stash`, `git checkout`, reset de branch, ou clone numa outra máquina.

Monte uma tabela de 3 colunas para os pontos críticos do checklist (pagamento, guardrails, fixes
recentes): **o que o checklist alega estar pronto** → **o que está de fato commitado na branch que
roda em prod** (`git log`, `git status`, `git diff`, `git branch -vv` — qual branch está checked
out agora é a que "roda") → **o que dá pra confirmar que está rodando de verdade** (processo vivo,
teste funcional, não só "existe no código"). Marque cada linha: OK / MENTIRA / NÃO VERIFICÁVEL.

## Áreas suspeitas conhecidas — vá fundo, não superficial

1. **Pagamento**: webhook Stripe (`STRIPE_WEBHOOK_SECRET` no `.env` — existe? é o de produção ou
   de teste?), Pix da Stripe (checklist diz que só falta ativar no painel — ainda não ativado?),
   webhook Mercado Pago (`MP_WEBHOOK_SECRET` registrado?), idempotência real do crédito em
   `app/payments/service.py` (webhook duplicado credita 1x mesmo?), `render`/`reset` não-atômicos
   apontados em memória anterior — ainda existe essa race?
2. **Abuso/farming**: cadastro com temp-mail (o OTP via Resend bloqueia isso?), chargeback (o que
   acontece com os créditos já gastos se o pagamento for revertido?), o teto de
   `MAX_AI_VIDEO_PER_DAY=3` — dá pra burlar criando várias contas fácil?
3. **Custo silencioso**: a cascata de LLM (`app/services/llm.py` ou equivalente — ache o arquivo)
   cai de um provedor pago pra um fallback gratuito/pior quando o principal falha ou estoura quota.
   Isso é ótimo pra não quebrar a geração, mas o usuário PAGA crédito por um vídeo pior sem saber.
   Existe qualquer sinal (log, campo no job, UI) que avise isso? Se não, é um problema de produto,
   não só de custo.
4. **`/storage/jobs`**: em `app/main.py` há um middleware que exige `?exp&sig` assinados pra
   proteger mídia privada — confirme que ele de fato cobre todas as rotas que servem mídia de job
   (inclusive as chamadas pelo editor/preview) e que a assinatura não é forjável/replay-ável
   (expira de verdade? o segredo de assinatura está forte?).
5. **`.env` vs realidade**: quais chaves são de produção de verdade (`sk_live`, `rk_live`) vs
   teste, e quais endpoints de webhook estão de fato registrados nos painéis (isso não dá pra
   confirmar por código — liste como "não verificável sem acesso ao painel" em vez de assumir).
6. **Testes**: rode `pytest -q` de verdade (venv `.venv312`) e `cd frontend && npx tsc --noEmit`
   (depois de `npx next typegen`, exigido pelo Next 16). Se algo estiver vermelho ou pulando
   silenciosamente (skip, xfail), isso é notícia.

## Checagem ao vivo do site — best-effort, com prazo

`clipia.com.br` às vezes devolve 403 intermitente (Cloudflare) e as ferramentas de browser podem
estar indisponíveis nesta sessão. Tente uma vez, documente o resultado, e **não insista** — o valor
real desta auditoria está no código/config/estado do git, que é determinístico. Não gaste mais de
uns minutos tentando reproduzir algo ao vivo antes de seguir pro resto.

## Ideias / próximo passo (segundo plano, só depois dos blockers)

Depois de cobrir os pontos acima, dê uma passada crítica em `docs/ROADMAP.md` (seção "Eixos de
melhoria"): a priorização ali (qualidade → escala → distribuição → negócio) faz sentido pra um
produto que ainda não fechou o ciclo de monetização de verdade? O que você cortaria ou reordenaria?

## Formato de saída

Três blocos, nessa ordem, cada achado com `arquivo:linha` quando aplicável:

1. **Blockers (receita/segurança)** — coisas que, se erradas, custam dinheiro ou expõem dados.
2. **Reconciliação alegado × commitado × rodando** — a tabela da tarefa principal.
3. **Qualidade / ideias** — o resto, incluindo a crítica ao roadmap.

Não liste 30 itens rasos. Prefira ir fundo em poucos — onde sentir "tem sangue aqui", investigue
até o fim (leia o código completo do fluxo, não só o trecho óbvio) antes de escrever o achado.
