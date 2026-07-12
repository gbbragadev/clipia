# AUDITORIA CLIPIA — insights acionáveis (produto · desempenho · qualidade × backend · frontend · SEO)

## Quem você é nesta tarefa
Consultor sênior de produto + engenharia fazendo due diligence técnica **read-only** no repo `C:\dev\clipia`. Seu entregável é UM relatório acionável — não código. O dono precisa abrir o relatório amanhã e começar a executar sem te perguntar nada.

## O produto (contexto que não está óbvio no código)
- **ClipIA** (clipia.com.br): gera vídeos curtos (Shorts/Reels/TikTok) em pt-BR com IA — tema → roteiro (LLM) → narração TTS → mídia → composição com legendas → editor interativo (Remotion) → export.
- **Modelo de negócio**: compra única de créditos em R$, sem assinatura — contraste deliberado com concorrentes (AutoShorts $19-69/mês, Revid $39-199, Crayo, Fliki, Submagic, OpusClip).
- **Estágio**: beta fechado com pagamento LIVE (Stripe + Mercado Pago). O gargalo declarado é VENDA/conversão, não código. Meta: primeiro pagante fora do beta e R$ 1.500/mês até 30/jul.
- **Time**: 1 dev (o dono) + 1 pessoa de social/ads. Toda recomendação precisa caber nessa capacidade — nada de "contrate um time de growth".

## Stack e ambiente (Windows — atenção)
- **Backend**: Python 3.12 + FastAPI + Celery (worker `--pool=solo` = 1 task por vez) + Redis (porta 6382) + PostgreSQL (SQLAlchemy async). Pipeline Celery: `generate_script → synthesize_audio (ElevenLabs/EdgeTTS) → transcribe_audio (Groq Whisper) → fetch_media (Pexels + biblioteca CLIP local) → compose_video (FFmpeg/NVENC) → finalize`. Export do editor renderiza via Remotion (`app/services/remotion.py`).
- **Frontend**: Next.js 16 + React 19 + Remotion 4 + Tailwind 4. Superfícies: landing `/`, `/criar/[nicho]` (7 páginas SSG), `/exemplos`, `/v/[id]` (vídeo público), `/dashboard`, `/editor/[jobId]`, `/suporte`.
- **LLM**: OpenRouter (DeepSeek) com cascata de fallback em `app/services/llm.py`; imagem IA; template premium `ai_video` gera vídeo via OpenRouter `/api/v1/videos`.
- **PRODUÇÃO RODA NESTA MÁQUINA** — Cloudflare Tunnel → localhost:3003 (frontend) e 8005 (backend).

## Regras rígidas (violar qualquer uma = tarefa falhou)
1. **NÃO altere código do produto. NÃO commite, NÃO push, NÃO crie branch.** Seu único write permitido: `docs/INSIGHTS-GPT56-2026-07-12.md`.
2. **NÃO reinicie/mate serviços, processos, docker, túneis** — produção é local, derrubar = site fora do ar.
3. **NÃO toque em `.env`, secrets ou env vars.** Não imprima valores de chaves no relatório.
4. **NÃO instale dependências** (pip/npm).
5. Verificações permitidas: ler qualquer arquivo; `git log/diff/blame`; subconjuntos de teste (`.\.venv312\Scripts\Activate.ps1` e depois `pytest tests/caminho -q`); no frontend `npx next typegen` seguido de `npx tsc --noEmit`. **Evite `next build`** (pesado, compete com o servidor de prod).
6. Shell = PowerShell 5.1: `&&` não existe (use `;` ou linhas separadas); paths com `\`.

## Disciplina de tempo (janela dura de ~5h — o relatório NUNCA fica pra depois)
- Rode `Get-Date` AGORA e anote: deadline = início + 4h15. Cheque o relógio ao fim de cada fase.
- Crie `docs/INSIGHTS-GPT56-2026-07-12.md` com o esqueleto de todas as seções JÁ na Fase 0 e **salve cada seção assim que fechar a fase**. Nada de acumular achados só em memória — se a janela cortar, o que está no arquivo é o que existe.
- Fase estourou o orçamento → feche a seção com o que tem, marque `[CORTADO POR TEMPO]`, siga.
- A Fase 5 (síntese) é INEGOCIÁVEL: reserve os 30 min finais custe o que custar.

## FASE 0 — Ground (20 min máx)
Leia nesta ordem — é o mapa do que já sabemos:
1. `CLAUDE.md` (raiz) — arquitetura + gotchas de ambiente
2. `docs/BACKLOG-AUDITORIA-2026-07-11.md` — auditoria multi-agente de 11/07 + rodada de 12/07: o que JÁ foi corrigido, o que está aberto e a seção "❌ Refutados". **Não reapresente NADA dessas listas.**
3. `docs/GO-LIVE-CHECKLIST.md` + `docs/PLANO-ESCALA.md` — prioridades de negócio
4. `docs/ROADMAP-QUALIDADE-VIDEO.md` — qualidade de vídeo (P0 feito; P1/P2 mapeados)
5. `frontend/DESIGN.md` — sistema de design (fonte de verdade do frontend)
6. Estrutura: árvore de 2 níveis de `app/` e `frontend/src/`

**Já sabemos (não gaste UM minuto redescobrindo)**: split do PlayerFrameContext (re-render ~10×/s no playback do editor) é pendência conhecida; `_prepare_scene` sequencial idem; ducking/loudnorm, refunds de créditos, race do flushSave pré-render e fidelidade editor→export foram corrigidos e validados; a suíte tem 435 testes verdes; pricing transparente na landing e referral já existem. **Seu valor está no que as passadas anteriores (46 agentes em 2 auditorias) NÃO viram.**

## FASE 1 — PRODUTO (60 min): o caminho do dinheiro
Reconstrua POR CÓDIGO o funil completo: landing → cadastro/OTP → primeiro vídeo → editor → export → compra de créditos → retorno. Procure:
- Fricção que mata conversão em beta fechado: quanto tempo/quantos passos até o primeiro vídeo? Welcome credits são comunicados? Existem dead-ends sem CTA?
- **Valor invisível**: coisas que o produto faz bem e a UI não mostra nem celebra.
- Promessa da landing vs capacidade real do código — gaps nos DOIS sentidos (promete e não faz / faz e não conta).
- Retenção: o que traz o usuário de volta amanhã? (e-mail de render pronto? histórico? biblioteca?)
- Monetização: onde o usuário fica sem créditos e a recarga não é óbvia; custo real por vídeo × créditos cobrados (calcule com os números do código — preços de API estão nas integrações) — o preço está calibrado?

## FASE 2 — BACKEND & PIPELINE (70 min): custo, latência, robustez
- **Custo por vídeo**: rastreie cada chamada paga (tokens LLM, chars ElevenLabs, Groq ASR, Pexels, OpenRouter vídeo/imagem) e estime custo unitário por template; aponte os 3 maiores ganhos de margem.
- **Wall-clock da geração**: onde o tempo vai por task Celery; o que paraleliza sem risco (lembre: worker solo).
- Robustez: pontos de falha sem retry/timeout/refund; worker solo = fila única — o que acontece com 5 usuários gerando ao mesmo tempo? A espera é comunicada?
- Consistência Redis (status quente) × Postgres (fonte fria): onde divergem e o que o usuário vê quando divergem.
- Contratos de API: erros que o frontend não trata; status codes enganosos; respostas sem `cost` onde ação é paga.

## FASE 3 — FRONTEND & PERF PERCEBIDA (50 min)
- Bundle e LCP das páginas públicas (landing, `/criar/[nicho]`, `/v/[id]`): análise estática — imports pesados, client components que podiam ser server, imagens sem otimização, fontes bloqueantes. (Sem `next build`.)
- Editor: trabalho no caminho do keystroke/playback ALÉM do PlayerFrameContext já conhecido; contexts largos; polling redundante; efeitos que rodam à toa.
- Mobile no caminho do dinheiro: gerar → exportar → comprar em viewport pequena.
- Acessibilidade básica onde afeta conversão (foco, contraste, labels em forms de auth/pagamento).

## FASE 4 — SEO & DISTRIBUIÇÃO ORGÂNICA (40 min)
- Estado real por página: title/description/OG/twitter card, `sitemap.xml`, `robots.txt`, canonical, JSON-LD — existem? corretos? (procure em `frontend/src/app/**` e `next.config.ts`)
- `/criar/[nicho]`: avalie conteúdo/keywords pt-BR ("criar vídeo com IA", "gerador de shorts automático"...), inter-linking, profundidade de conteúdo — a concorrência BR nessas keywords é fraca, oportunidade real.
- `/v/[id]` como loop viral: quando compartilhada no WhatsApp (O canal no Brasil), a página mostra OG image/preview do vídeo correto? Renderiza rápido deslogado?
- Core Web Vitals como fator de rank nas páginas públicas.
- **Páginas programáticas que NÃO existem e deveriam** (ex.: template × nicho, exemplos por tema) — com estimativa de esforço dado o SSG já montado.

## FASE 5 — SÍNTESE (30 min, OBRIGATÓRIA) — vai no TOPO do relatório
1. **TOP 10 por ROI** (impacto no negócio ÷ esforço), 2 linhas cada: o quê + por que agora.
2. **Quick wins** (<1 dia de dev) — lista separada.
3. **3 apostas estruturais** (M/L) que mais mudariam a trajetória do produto.
4. Um parágrafo honesto: "se eu fosse o dono e tivesse 1 semana, faria X → Y → Z nesta ordem, porque…".

## Formato de CADA achado (nas seções por fase)
```
### [P0|P1|P2] Título curto — (eixo: produto|perf|qualidade|seo)
- Evidência: caminho/arquivo.py:123 (real e verificado — sem evidência não entra)
- Impacto: efeito concreto em usuário / receita / custo / rank
- Ação: o menor passo que resolve (comando, diff conceitual ou decisão a tomar)
- Esforço: S (<2h) | M (1 dia) | L (semana)
```
- Claim que não deu tempo de verificar → marque `[NÃO VERIFICADO]`. Honestidade > volume.
- Qualidade > quantidade: 15-25 achados fortes valem mais que 50 rasos.
- Achado de SEGURANÇA grave encontrado de passagem: registre numa seção à parte "Flags de segurança" (sem caçar ativamente — está fora do escopo desta rodada por decisão do dono).

Escreva TODO o relatório em português (pt-BR). Comece agora pela Fase 0.
