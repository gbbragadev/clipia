# Auditoria ClipIA — insights acionáveis

> **Status:** FINALIZADO — auditoria estática read-only; verificações e limites no fim do documento
> **Data:** 12/07/2026
> **Início:** 03:36 (UTC−3)
> **Deadline operacional:** 07:51 (UTC−3)
> **Escopo:** produto, desempenho e qualidade × backend, frontend e SEO
> **Método:** due diligence técnica read-only, com evidência em código; sem reiniciar serviços, sem build e sem acessar/imprimir segredos.

## Síntese executiva

### TOP 10 por ROI

1. **Limitar `ai_video` a seis cenas e medir o custo na unidade real.** Hoje 30 créditos compram um job, mas a despesa cresce por clipe de 5 s e pode ultrapassar a receita com 12+ cenas. É o único risco capaz de transformar venda em prejuízo; o teto e a telemetria correta cabem em menos de um dia.

2. **Mostrar o custo total dos refinamentos antes de gerar.** Dois refinamentos acrescentam 1 crédito no servidor, porém a UI continua prometendo só o custo-base e pode terminar em 402. Corrigir restaura o principal guardrail de confiança no ponto de maior intenção.

3. **Corrigir a subcobrança do `dialogue_duo` no servidor.** O worker usa duas vozes ElevenLabs por definição do template, mas um payload `single + edge` paga 1 crédito. É um fix pequeno que fecha vazamento direto de margem sem depender do frontend.

4. **Preservar a intenção de nicho através de cadastro e OTP.** Quem chega procurando drama histórico ou finanças cai num formulário genérico depois de confirmar o e-mail. Reaplicar uma vez tema/template/estilo encurta o caminho do tráfego orgânico até o primeiro vídeo.

5. **Trocar o preload do MP4 de 7,1 MB do hero por poster→vídeo sob demanda.** Mantém a melhor prova do produto, mas deixa de competir com copy e CTA no 4G. É o quick win de performance pública com evidência estática mais forte.

6. **Demonstrar os diferenciais já prontos na landing.** Rascunho editável, diálogo, lote, vozes e mídia IA só aparecem depois do cadastro; antes disso, o ClipIA parece um gerador básico. Uma seção real curta melhora percepção sem criar feature nova.

7. **Notificar quando o vídeo ficar pronto.** Jobs levam 3–10 min, o template de e-mail já existe e o pipeline não o chama. Uma notificação idempotente com deep-link recupera ativação, edição/download e futura recarga.

8. **Consertar o caminho editorial em um passe.** Remover auth do sitemap, adicionar `/blog`, `noindex` em auth, linkar o hub e apontar artigos para nichos. O esforço é pequeno e aproveita conteúdo/páginas já existentes em vez de fabricar mais conteúdo.

9. **Dar card social específico aos oito vídeos atuais e ligar a galeria ao viewer.** Hoje `/v` não tem `og:image` por vídeo e a galeria nem leva até ele. Poster + link + share de WhatsApp valida o mecanismo antes da aposta maior de publicação por usuário.

10. **Cortar trabalho contínuo do editor quando pausado.** Timeline e preview mantêm RAF a 60 fps, enquanto sliders remontam o Player. Condicionar desenho ao playback e parar remount por passo melhora a superfície central sem repetir o split de contexto já conhecido.

### Quick wins (<1 dia de dev)

- Teto de seis cenas em `ai_video` + telemetria `cenas × 5 s`.
- Custo da geração = custo-base + `floor(refinePending)` em gate, microcopy e modal.
- Pricing server-side do `dialogue_duo` pelo template efetivo.
- `POST /generate` com HTTP 202 e response schema explícito.
- `signup_intent` de nicho aplicado uma vez após OTP.
- Hero com poster e `preload="metadata"`; `FilmGrain` trocado por textura estática.
- Seção curta “rápido quando quer, controle quando precisa” com screenshots reais das features premium.
- `/blog` no sitemap, auth fora dele/com `noindex`, link no footer e interlinks dos três posts.
- Posters/OG específicos e links `/v/{id}` nos oito exemplos atuais.
- `Modal` nativo/focus trap e `role="alert"` em login/cadastro.
- Copy pública de bônus sem número hardcoded.

### 3 apostas estruturais

1. **Publicação opt-in + loop WhatsApp (`M/L`).** Slug revogável, thumbnail, página pública rápida e tracking `share→view→signup`; é a única aposta que transforma cada output em canal de aquisição. Começar só após provar o mini-loop com os oito exemplos.
2. **Orquestrador de cenas pagas (`M/L`).** Ledger por cena, concorrência limitada, cancelamento entre polls, retomada/reuso de clipes e preço por segundos reservados. Estabiliza margem e robustez do template mais caro.
3. **Aquisição por intenção (`M`).** Cinco páginas curadas de alta intenção + preservação do nicho até o formulário + dashboard de conversão por UTM. Escalar páginas somente depois de 30 dias de impressões e cadastros, não por volume de URLs.

### Se eu fosse o dono e tivesse uma semana

Eu faria **proteção de caixa → confiança/conversão → venda**, nessa ordem: no dia 1, teto/telemetria de `ai_video`, pricing de diálogo e custo correto de refino; no dia 2, intenção de nicho, hero leve, prova das features premium e higiene SEO; no dia 3, e-mail de vídeo pronto e mini-loop dos exemplos com OG/WhatsApp. **Pararia de codar aí.** Usaria os quatro dias restantes com a pessoa de social/ads para levar prospects às páginas de nicho, acompanhar cadastro→primeiro vídeo→recarga e fechar o primeiro pagante manualmente. Não construiria ainda o loop público completo nem as cinco novas páginas: sem tráfego/conversão observados, seriam apostas maiores atacando o gargalo errado.

---

## Fase 0 — Ground e limites da auditoria

### Estado verificado

- Branch analisada: `feat/editor-reforma`.
- Working tree inicial: apenas `docs/PROMPT-AUDITORIA-GPT56-2026-07-12.md` estava untracked; este relatório é o único write desta auditoria.
- O repositório não estava no índice do codebase-memory; foi indexado em modo `moderate` para busca estrutural e call graph.
- Estrutura backend: FastAPI em `app/api`, auth em `app/auth`, pagamentos em `app/payments`, pipeline em `app/worker/tasks.py` e integrações em `app/services`.
- Estrutura frontend: App Router em `frontend/src/app`, superfícies reutilizáveis em `frontend/src/components`, estado do editor em `frontend/src/contexts/EditorContext.tsx` e composição em `frontend/src/remotion`.

### Exclusões deliberadas — não reapresentar como achado

Esta rodada não recicla itens já corrigidos, abertos ou refutados em `docs/BACKLOG-AUDITORIA-2026-07-11.md`, nem os itens já mapeados em `docs/ROADMAP-QUALIDADE-VIDEO.md`. Em particular: split do `PlayerFrameContext`, `_prepare_scene` sequencial, ducking/loudnorm, refunds, race do `flushSave`, fidelidade editor→export, `pending_credits` stale, dashboard mobile comprimido, transições/drift e demais itens P1/P2 já documentados estão fora da lista de novos achados. Pricing transparente e referral já existem.

### Fontes-base lidas

1. `CLAUDE.md`
2. `docs/BACKLOG-AUDITORIA-2026-07-11.md`
3. `docs/GO-LIVE-CHECKLIST.md`
4. `docs/PLANO-ESCALA.md`
5. `docs/ROADMAP-QUALIDADE-VIDEO.md`
6. `frontend/DESIGN.md`
7. Árvores de dois níveis de `app/` e `frontend/src/`

---

## Fase 1 — Produto: o caminho do dinheiro

### Funil real reconstruído no HEAD

1. Landing e páginas de nicho levam a `/auth/register`; cadastro exige dados, aceite dos termos e Turnstile quando configurado.
2. O usuário confirma um OTP de seis dígitos; só então recebe `WELCOME_CREDIT_BONUS` e entra no dashboard (`app/auth/routes.py:158-220`).
3. No dashboard, escolhe tema, template, estilo, duração e voz; pode revisar/refinar o roteiro antes da geração. O custo-base vem de `/templates` e aparece antes do clique (`frontend/src/components/dashboard/GenerateForm.tsx:74-98,701-707`).
4. `POST /generate` debita atomicamente e enfileira o job; o formulário libera imediatamente e a grid passa a acompanhar fila/progresso (`frontend/src/components/dashboard/GenerateForm.tsx:222-257`). Apesar de comentários do frontend chamarem isso de “202 aceito”, o backend hoje responde 200 — achado registrado na Fase 2.
5. O vídeo concluído entra como editável; o usuário pode baixar o primeiro resultado ou editar e reexportar. Ações pagas mostram custo e confirmação conforme `frontend/DESIGN.md`.
6. Sem saldo, o modal leva diretamente a `/dashboard/credits` (`frontend/src/components/dashboard/GenerateForm.tsx:748-761`). Pacotes são compra única; após retorno `success`, a tela atualiza o usuário a cada três segundos por até 30 segundos enquanto o webhook credita (`frontend/src/app/dashboard/credits/page.tsx:42-65`).

### [P1] Custo prometido ignora refinamentos já acumulados — (eixo: produto)
- Evidência: o frontend calcula `creditCost` apenas pelo template/voz e usa esse valor no gate, na microcopy e no modal (`frontend/src/components/dashboard/GenerateForm.tsx:83-98,260-275,701-728`); embora mostre `refinePending` separadamente (`frontend/src/components/dashboard/GenerateForm.tsx:601-605`), o backend soma `int(refine_owed)` ao débito (`app/api/routes.py:236-245`) e devolve o total em `credit_cost` (`app/api/routes.py:368`), campo descartado pelo tipo de `generateVideo` (`frontend/src/lib/editor-api.ts:239-245`).
- Impacto: depois de dois refinamentos, a tela pode afirmar “1 crédito será usado” e até deixar o clique passar com saldo 1, mas o servidor tenta debitar 2 e responde 402. É quebra direta do guardrail “custo antes da ação” no momento de maior intenção.
- Ação: somar `Math.floor(refinePending)` ao custo exibido/gate e tipar/consumir `credit_cost` da resposta como confirmação do débito real; manter o restante de 0,5 explicitamente separado.
- Esforço: S (<2h)

### [P1] Jobs demoram minutos, mas “vídeo pronto” não chama o usuário de volta — (eixo: produto)
- Evidência: os tempos planejados são stock 3–4 min, imagens IA 5–7 min e vídeo IA 6–10 min (`docs/PLANO-ESCALA.md:10-16`); `task_finalize` conclui DB/Redis e retorna sem notificar (`app/worker/tasks.py:1088-1137`). Existe um HTML `email_video_ready`, mas a única outra ocorrência no repo é a própria definição (`app/email_templates.py:97-106`), portanto ele não está ligado ao pipeline.
- Impacto: o produto diz que o usuário pode gerar outras coisas enquanto espera, porém não oferece motivo para voltar se a aba for fechada; isso perde ativação do primeiro vídeo, edição, download e a chance de recarga.
- Ação: no `finalize`, enfileirar uma notificação transacional idempotente apenas na primeira transição para `editable`, com deep-link para `/editor/{job_id}`; começar por e-mail e medir abertura→editor antes de adicionar push.
- Esforço: M (1 dia)

### [P2] A promessa de boas-vindas tem duas fontes de verdade — (eixo: produto)
- Evidência: o bônus é configurável (`app/config.py:140-143`) e exposto por `/config` (`app/api/routes.py:595-600`); cadastro e dashboard consomem esse valor dinâmico. Em contraste, artigos, CTAs de nicho e FAQ codificam “2 créditos/vídeos grátis” (`frontend/src/app/blog/[slug]/page.tsx:136`, `frontend/src/lib/blog-posts.ts:38,93`, `frontend/src/lib/niches.ts:60,79-355`).
- Impacto: elevar temporariamente o bônus do beta — cenário previsto no próprio config — não atualiza páginas orgânicas. A oferta mais forte fica invisível; ao reduzir para 2, páginas geradas/caches também podem divergir do backend.
- Ação: nas superfícies SSG usar a copy estável “créditos de boas-vindas” (como a landing já faz) ou gerar o número a partir de uma única fonte de build; não buscar config client-side só para uma frase.
- Esforço: S (<2h)

### [P2] Diferenciais premium existem no produto, mas não são demonstrados na aquisição — (eixo: produto)
- Evidência: a landing resume valor a tema→roteiro→narração→legenda→editor (`frontend/src/components/landing/sections/Hero.tsx:54-56`, `frontend/src/components/landing/lib/data.ts:244-250`), enquanto o produto já expõe rascunho editável/refino, lote, modo diálogo, escolha de vozes e templates de imagem/vídeo IA (`frontend/src/components/dashboard/GenerateForm.tsx:51-70,146-220`; `app/templates.py:159-296`).
- Impacto: o visitante compara o ClipIA como mais um gerador básico e só descobre os diferenciais após cadastrar; isso enfraquece conversão e não cria desejo pelos templates de 5/30 créditos que sustentam ticket maior.
- Ação: adicionar uma única seção curta “do modo rápido ao controle pro” com captura real do rascunho, diálogo e um exemplo IA premium; não criar tour nem nova página antes de medir clique/registro.
- Esforço: S (<2h)

### Hipóteses refutadas no HEAD

- “Roteiro avançado não entra na geração”: falso; `custom_script` é montado e enviado (`frontend/src/components/dashboard/GenerateForm.tsx:146-180`) e persistido antes do dispatch (`app/api/routes.py:326-331`).
- “Modal sem créditos tem CTA desabilitado”: falso; ele aponta para `/dashboard/credits` (`frontend/src/components/dashboard/GenerateForm.tsx:756-761`).
- “Retorno de pagamento afirma crédito antes do webhook”: já corrigido; a copy diz “em instantes” e há polling de 30 s (`frontend/src/app/dashboard/credits/page.tsx:42-57`).
- “Falha no polling do formulário prende geração”: obsoleto; o formulário cobre somente o POST e a grid assume o tracking após o `202` (`frontend/src/components/dashboard/GenerateForm.tsx:45-47,222-257`).

---

## Fase 2 — Backend e pipeline: custo, latência e robustez

### Unidade econômica reconstruída

Os valores abaixo são **estimativas versionadas no repo**, não fatura: `app/config.py:85-92`. Receita por crédito, antes de bônus promocional, varia de **R$ 1,30** (Pro) a **R$ 1,99** (Starter), conforme `app/payments/schemas.py:7-9`. O percentual efetivo de bônus em produção não foi lido por regra de escopo; se estiver em 20%, a receita por crédito entregue cai 16,7% **[NÃO VERIFICADO EM RUNTIME]**.

| Operação/template | Créditos | Receita nominal | Custo externo estimado pelo código |
|---|---:|---:|---:|
| Stock/Pexels/local + Edge/custom | 1 | R$ 1,30–1,99 | US$ 0,006: 1 LLM (US$ 0,005) + ASR (US$ 0,001); Pexels/Edge/local sem custo marginal versionado |
| Stock/Pexels/local + ElevenLabs/diálogo | 2 | R$ 2,60–3,98 | Base + `0,11 × caracteres/1.000` USD |
| `ai_image` (4–6 cenas típicas) | 5 | R$ 6,50–9,95 | Base + US$ 0,06/imagem = ~US$ 0,246–0,366 com Edge |
| `ai_video` (4–6 cenas típicas) | 30 | R$ 38,97–59,70 | Payload real = 5 s/cena; ~US$ 0,60/cena = ~US$ 2,406–3,606 com Edge |
| Voice Design / Clone | 5 cada | R$ 6,50–9,95 | Preço externo não está versionado; não há base honesta para estimar |
| Refino de roteiro | 0,5 acumulado | R$ 0,65–1,00 | 1 chamada LLM estimada em US$ 0,005 |
| Reset / re-render | 1 / `ceil(pending)` | R$ 1,30–1,99+ | Computação local; custo de energia/host não modelado |

Fórmulas: `app/pricing.py:7-28`, `app/worker/tasks.py:1024-1052`. O prompt normal pede 4–6 cenas (`app/services/scriptwriter.py:23-31`); o guardrail aceita até `min(40, ceil(duração/4))` (`app/services/scriptwriter.py:179-195`, `app/models.py:65-72`).

### Capacidade, espera e tolerância a falhas

**Cinco usuários ao mesmo tempo:** o worker `--pool=solo` executa uma task por vez; como cada vídeo é uma chain, etapas de jobs diferentes podem intercalar na fila. A carga agregada de cinco jobs stock homogêneos representa ~15–20 min de trabalho; imagens IA, ~25–35 min; vídeo IA, ~30–50 min até concluir o lote, sem garantir qual usuário termina primeiro. São extrapolações lineares dos tempos-base de `docs/PLANO-ESCALA.md:10-16`, não stress test. A UI comunica posição/progresso nos cards (`app/api/routes.py:1391-1472`), mas a posição omite re-renders — achado P2 abaixo. O gatilho de escala já decidido é espera média >10 min ou >5 aguardando com frequência (`docs/PLANO-ESCALA.md:24-31`); portanto um lote simultâneo de cinco já pode ultrapassar o SLA desejado, embora não implique perda de job por si só.

> Os valores `soft_time_limit`/`time_limit` abaixo estão configurados nos decorators, mas no Celery `--pool=solo` do Windows eles não são o mecanismo efetivo de interrupção. A proteção real vem de timeouts dos providers, checks de cancelamento e watchdog — limitação já conhecida e deliberadamente não reapresentada como novo achado.

| Etapa | Limites configurados | Retry explícito |
|---|---:|---|
| Roteiro | 120/150 s | 10 s, 30 s |
| Imagens IA | 180/210 s | provider: até 3 tentativas transitórias; task sem retry integral |
| Vídeos IA | 720/780 s | sem retry integral; cada clipe tem poll até 600 s |
| TTS | 120/150 s | 5 s, 15 s |
| ASR | 120/150 s | sem retry integral |
| Busca/download de mídia | 300/360 s | 10 s, 30 s, 60 s |
| Composição | 480/540 s | sem retry integral |
| Finalização | 120/150 s | sem retry integral |
| Re-render | 300/360 s | sem retry integral; custo específico é restaurado em falha |

Evidência: decorators e chamadas de retry em `app/worker/tasks.py:259-276,338-349,382-390,679-849,849-968,968-1146`. Falhas terminais da geração passam por estado final, estorno idempotente e dead-letter/admin alert (`app/worker/tasks.py:137-195`); isso protege o cliente, mas não recupera custo externo já incorrido em cenas — achado P1 abaixo.

### [P0] `ai_video`: preço por job, custo por cena e teto por job não fecham a conta — (eixo: produto)
- Evidência: o preço é fixo em 30 créditos (`app/config.py:130-137`, `app/pricing.py:16-28`); cada cena vira um request paralelo de 5 s (`app/worker/tasks.py:349-379`, `app/services/video_gen_provider.py:71-115`); o teto diário conta jobs, não cenas (`app/api/routes.py:247-305`); scripts customizados podem chegar a 40 cenas (`app/models.py:65-72`).
- Impacto: no caso normal de seis cenas, a estimativa interna é ~R$ 20,10 de Seedance (6 × 5 s × R$ 0,67/s, valor documentado em `app/config.py:120-137`) para receita nominal mínima de R$ 38,97. Com 12 cenas permitidas num vídeo de 45 s, vira ~R$ 40,20 e já supera a receita mínima antes de LLM/ASR; no teto de 40, ~R$ 134. Três jobs/dia permitem até 120 clipes/600 s pagos por usuário.
- Ação: imediato: teto duro de seis cenas para `ai_video` e telemetria baseada em `len(scenes) × VIDEO_GEN_CLIP_SECONDS`. Em seguida, cobrar créditos por segundos/clipes reservados, não por job, e só então decidir se o teto pode subir.
- Esforço: S para o teto/telemetria; M para preço dinâmico

### [P1] Cancelar ou falhar um clipe não impede o restante do gasto externo — (eixo: produto)
- Evidência: cancelamento é checado apenas antes de entrar na etapa (`app/worker/tasks.py:349-353`); `generate_scenes` cria todos os requests e aguarda `asyncio.gather` sem sinal de cancelamento (`app/services/video_gen_provider.py:107-115`). Uma exceção falha o job e devolve todos os créditos (`app/worker/tasks.py:382-387`, `app/worker/tasks.py:146-195`), mas requests externos já submetidos podem continuar e ser cobrados.
- Impacto: o usuário recebe estorno correto, porém a empresa absorve clipes órfãos. Uma única cena que falha pode descartar o valor das cenas que terminaram; cancelar durante os 6–10 min não economiza a chamada mais cara.
- Ação: trocar o fan-out irrestrito por concorrência limitada (2–3); persistir IDs por cena; checar cancelamento antes de cada nova submissão e entre polls; reaproveitar clipes concluídos em retry do mesmo job.
- Esforço: M (1 dia)

### [P1] Imagens IA são geradas serialmente apesar de serem I/O independente — (eixo: perf)
- Evidência: `task_generate_images` percorre cenas com `for` e bloqueia em `provider.generate` uma a uma (`app/worker/tasks.py:276-335`); cada chamada tem timeout de 60 s e até três tentativas (`app/services/image_provider.py:25-43,57-95`).
- Impacto: a principal etapa de `ai_image` soma latência por cena e ajuda a levar o template a 5–7 min. O worker continua solo, mas chamadas de rede independentes não usam CPU/GPU local enquanto esperam.
- Ação: paralelizar somente a API com `Semaphore(2)` e `asyncio.to_thread`, preservando ordem, cache e cancelamento por cena; validar rate limit e um job real antes de aumentar para 3.
- Esforço: M (1 dia)

### [P1] `dialogue_duo` pode usar duas vozes ElevenLabs e cobrar como Edge — (eixo: produto)
- Evidência: o request default é `narration_mode="single"`, `voice_provider="edge"` (`app/models.py:15-33`); o preço força ElevenLabs apenas quando o modo recebido é `dialogue` (`app/api/routes.py:231-245`). Porém `dialogue_duo` é diálogo nativo/ElevenLabs (`app/templates.py:277-291`) e o worker chama `synthesize_dialogue` por `template.script.is_dialogue` independentemente do modo (`app/worker/tasks.py:756-762`).
- Impacto: a UI atual tende a enviar o provider correto, mas qualquer cliente autenticado/replay de payload pode pagar 1 crédito por uma operação de 2 créditos. É contrato server-side inconsistente e trivial de explorar.
- Ação: calcular `cost_provider` a partir de `req.narration_mode == "dialogue" OR template.script.is_dialogue OR template.voice.provider == "elevenlabs"`; piná-lo com teste direto do endpoint usando `dialogue_duo + edge + single`.
- Esforço: S (<2h)

### [P2] Posição da fila ignora re-renders que ocupam o mesmo worker — (eixo: perf)
- Evidência: a fila global nasce somente de jobs cujo status PostgreSQL é `queued` (`app/api/routes.py:1391-1418`). O re-render muda o status quente no Redis para `rendering`, mas o job no banco segue `editable` (`app/worker/tasks.py:1146-1157`); portanto ele não entra na consulta inicial.
- Impacto: um novo vídeo pode mostrar posição 0/“você é o próximo” enquanto aguarda um export Remotion de vários minutos no worker solo. A espera existe, mas a comunicação prometida fica errada justamente sob concorrência.
- Ação: manter uma fila Redis/Celery única de unidades ativas ou persistir `rendering` no DB; no mínimo, somar re-renders ativos à posição e exibir “há um export em andamento”.
- Esforço: M (1 dia)

### [P2] `/generate` é assíncrono, mas responde 200 e documenta “Job queued” como 200 — (eixo: qualidade)
- Evidência: o decorator não define `status_code=202` e registra apenas resposta 200 (`app/api/routes.py:217-224`), enquanto o frontend e a arquitetura tratam a aceitação como enqueue assíncrono (`frontend/src/components/dashboard/GenerateForm.tsx:45-47,235-240`).
- Impacto: SDKs, observabilidade e futuros clientes não distinguem “processado” de “aceito para processar”; contratos e testes podem passar mesmo quando a semântica de fila muda.
- Ação: retornar HTTP 202 explicitamente, documentar o schema `{job_id,status,credit_cost}` e manter 402/429/503 no OpenAPI.
- Esforço: S (<2h)

### Três maiores alavancas de margem

1. **Limitar e depois precificar `ai_video` por clipe/segundo** — elimina o único caminho com margem potencialmente negativa por construção.
2. **Concorrência limitada + reaproveitamento de cenas pagas** — reduz clipes órfãos em cancel/retry sem sacrificar todos os ganhos de wall-clock.
3. **Experimento controlado 480p/modelo mais barato** — a resolução já é configurável (`app/config.py:116-125`); só promover após A/B visual em tela de celular e fatura real, não por estimativa.

### Guards confirmados (não são achados)

- Débito da geração é atômico e serializado por usuário (`app/api/routes.py:256-301`).
- Falha de enqueue estorna e devolve a cota diária de vídeo IA (`app/api/routes.py:333-357`).
- Imagem IA já tem cache SHA-256 e retry transitório (`app/services/image_provider.py:44-95`).
- SFX é um asset global cacheado, não um custo ElevenLabs por vídeo (`app/services/sfx.py:42-67`).
- A lista `/jobs` cruza Redis quente e Postgres frio e esconde output antigo durante render (`app/api/routes.py:1387-1472`); a lacuna específica é a posição da fila de re-render.

---

## Fase 3 — Frontend e performance percebida

> Análise estática, conforme a restrição de não executar `next build`. O mecanismo e o volume de trabalho abaixo foram verificados no código; o delta real de LCP/INP precisa de medição posterior em aparelho/rede representativos.

### [P1] Hero prioriza download automático de MP4 de 7,1 MB no mobile — (eixo: perf)
- Evidência: o Hero marca o primeiro `VideoPhone` como `priority` (`frontend/src/components/landing/sections/Hero.tsx:92-98`); isso vira `autoPlay` e `preload="auto"` (`frontend/src/components/landing/preview/VideoPhone.tsx:74-84`). O ativo inicial `frontend/public/showcase/cerebro-fatos.mp4` tem 7.466.076 bytes (7,1 MB, verificado no filesystem).
- Impacto: em 375 px/4G, o vídeo de prova disputa rede com HTML, fontes e JavaScript antes de o visitante decidir interagir. É o maior payload conhecido acima da dobra e pode atrasar LCP/CTA, além de consumir franquia. **[IMPACTO CWV NÃO MEDIDO EM RUNTIME]**
- Ação: servir poster estático otimizado como estado inicial e trocar para vídeo em `IntersectionObserver` após a primeira pintura; no mínimo, remover `priority` e usar `preload="metadata"`. Preservar o vídeo real — ele é prova de produto, não removê-lo.
- Esforço: S (<2h)

### [P1] Sliders desmontam e remontam o Remotion Player a cada passo — (eixo: perf)
- Evidência: `VideoPlayer` serializa estilo/música, incrementa `version` quando qualquer campo muda e usa essa versão como `key` do Player (`frontend/src/components/editor/VideoPlayer.tsx:34-59,83-85`). Sliders disparam `updateSubtitleStyle`/`updateMusic` em todo `onChange` (`frontend/src/components/editor/SubtitleEditor.tsx:72-79,166-187,217-224`; `frontend/src/components/editor/MusicSelector.tsx:80-84`).
- Impacto: arrastar tamanho, margem, contorno, palavras por bloco ou volume pode causar dezenas de desmontagens por segundo, interrompendo preview e competindo com Canvas/React na máquina do cliente.
- Ação: deixar `inputProps` atualizar o Player sem trocar `key`; se algum campo realmente exigir remount, fazê-lo apenas em `pointerup`/`change` final e piná-lo com teste visual de posição/frame.
- Esforço: M (1 dia)

### [P1] Dois canvases redesenham a 60 fps mesmo com playback pausado — (eixo: perf)
- Evidência: `SubtitleTimeline` percorre todas as palavras e faz layout de texto, depois agenda `requestAnimationFrame` incondicional (`frontend/src/components/editor/SubtitleTimeline.tsx:15-65,68-75`). `PretextSubtitlePreview` também mede/layouta/pinta o chunk ativo e mantém RAF incondicional (`frontend/src/components/editor/PretextSubtitlePreview.tsx:36-63,126-376,379-386`); ele fica montado sobre o Player (`frontend/src/components/editor/VideoPlayer.tsx:83-98`).
- Impacto: com o vídeo parado — exatamente quando o usuário digita ou arrasta controles — a main thread continua pintando duas superfícies até 60 vezes/s. A timeline escala com todas as palavras do vídeo.
- Ação: quando `isPlaying=false`, desenhar apenas em mudança de frame/composição/resize; durante playback, manter um único RAF. Pré-calcular geometria da timeline quando `words`, largura ou fonte mudarem.
- Esforço: M (1 dia)

### [P1] Cada tecla em uma cena invalida a árvore inteira do editor e o histórico — (eixo: perf)
- Evidência: o textarea chama `updateScene` em todo caractere (`frontend/src/components/editor/SceneGrid.tsx:101-105`); isso copia `scenes`, cria nova `composition`, empilha histórico e recria o valor monolítico do contexto (`frontend/src/contexts/EditorContext.tsx:165-198,312-321`). Player, timeline, grid e painéis consomem o mesmo contexto.
- Impacto: digitação disputa render com Remotion e canvases; até 50 snapshots rasos da composição são mantidos. Abas inativas não estão montadas e o Player não remonta por texto, portanto o problema é rerender/fan-out — não clone profundo nem o `PlayerFrameContext` já conhecido.
- Ação: manter o texto do textarea local e consolidar no contexto em debounce/blur, preservando `narrationStale`; agrupar uma sessão de digitação como uma entrada de undo. Não fazer outro grande refactor de contexts antes de medir esse corte simples.
- Esforço: M (1 dia)

### [P2] `FilmGrain` gasta CPU globalmente sem agregar conversão mensurável — (eixo: perf)
- Evidência: o layout monta `FilmGrain` em toda rota (`frontend/src/app/layout.tsx:5,87-94`); o componente cria `ImageData` 128×128, percorre 16.384 pixels e repete a cada 150 ms (`frontend/src/components/FilmGrain.tsx:9-21`).
- Impacto: landing, login, cadastro, dashboard e editor fazem ~6,7 gerações de ruído/s mesmo parados. Em celular de entrada, é consumo contínuo de CPU/bateria concorrendo com as ações que geram receita. **[DELTA DE INP/BATERIA NÃO MEDIDO]**
- Ação: substituir por PNG/WebP minúsculo ou gradiente/textura CSS estática; manter a mesma opacidade visual. É remoção de JavaScript, não redesign.
- Esforço: S (<2h)

### [P1] Modal canônico deixa o foco escapar para controles atrás dele — (eixo: qualidade)
- Evidência: o componente foca o painel, fecha com Esc e restaura foco, mas não trata `Tab`/`Shift+Tab` nem torna o fundo inerte (`frontend/src/components/ui/Modal.tsx:30-44,55-66`). Ele protege confirmações pagas e o CTA de recarga (`frontend/src/components/dashboard/GenerateForm.tsx:711-768`).
- Impacto: usuário de teclado/leitor de tela pode atravessar e acionar o dashboard por trás da confirmação de lote/saldo, quebrando a semântica modal justamente no caminho do dinheiro.
- Ação: preferir `<dialog>.showModal()` no componente compartilhado (fundo inerte/foco nativo) e preservar Esc/restauração; alternativa mínima é focus trap com primeiro/último foco testado por Tab/Shift+Tab.
- Esforço: S (<2h)

### [P2] Erros de login/cadastro são apenas visuais — (eixo: qualidade)
- Evidência: login e cadastro atualizam `error`, mas renderizam a mensagem sem `role="alert"`/`aria-live` (`frontend/src/app/auth/login/page.tsx:16-29,49-53`; `frontend/src/app/auth/register/page.tsx:23-53,89-93`).
- Impacto: credencial inválida, senha fora da política ou termos não aceitos podem não ser anunciados ao leitor de tela; o usuário permanece bloqueado sem feedback perceptível.
- Ação: aplicar `role="alert"` ao bloco condicional compartilhando o padrão de `InlineError`; manter foco no campo responsável quando a validação for local.
- Esforço: S (<2h)

### Achados descartados por baixo ROI ou refutação

- Botão de compra com ~40 px de altura: melhoria válida, mas abaixo de problemas que bloqueiam confiança/performance; ajustar quando tocar no card.
- Waveform continua durante pausa da gravação: real, porém fluxo raro e impacto pequeno; corrigir junto de Voice Clone, não abrir sprint própria.
- “Thumbnails recarregam a cada tecla” e “autosave serializa a cada tecla”: refutados; thumbnail depende de `videoUrl` e o save tem debounce de 1,5 s.
- Providers globais hidratam a landing, mas sem `next build` não há evidência suficiente para atribuir peso de bundle; medir antes de separar layouts.

---

## Fase 4 — SEO e distribuição orgânica

### Estado técnico por superfície

- `/`: metadata/OG/Twitter e `SoftwareApplication` globais existem (`frontend/src/app/layout.tsx:17-80`); o gargalo está no peso acima da dobra, tratado na Fase 3.
- `/criar/[nicho]`: sete páginas SSG com title/description, canonical, OG, H1, intro único, benefícios, processo, temas, FAQ e schemas de FAQ/Breadcrumb (`frontend/src/app/criar/[nicho]/page.tsx:19-43,58-218`; conteúdo em `frontend/src/lib/niches.ts:68-391`).
- `/exemplos`: canonical/OG e links para todos os nichos (`frontend/src/app/exemplos/page.tsx:10-22,39-58`).
- `/blog`: posts entram no sitemap, mas o hub não; metadata editorial é incompleta e o cluster está órfão da navegação.
- `/v/[id]`: SSG restrito ao showcase; canonical existe, mas o card social não identifica o vídeo.
- `robots.txt`: permite o site e bloqueia dashboard/editor/API e fluxos sensíveis de verify/reset (`frontend/src/app/robots.ts:3-11`).

### [P0] O “loop viral” `/v` não publica nem compartilha vídeos de usuários — (eixo: produto)
- Evidência: a página declara que hoje serve somente o showcase, lê IDs de JSON e usa `dynamicParams=false` (`frontend/src/app/v/[id]/page.tsx:6-25`); qualquer job de usuário é 404. A galeria renderiza cards sem `Link` para `/v/{id}` (`frontend/src/components/ShowcaseSection.tsx:11-75`), e o viewer tem CTA de cadastro, mas nenhum botão de compartilhar/WhatsApp (`frontend/src/app/v/[id]/page.tsx:56-104`).
- Impacto: o canal orgânico mais natural no Brasil não tem objeto compartilhável. O usuário termina/exporta um vídeo, mas não consegue gerar um link público opt-in que leve espectadores de volta ao ClipIA; nem os exemplos existentes alimentam o viewer nominalmente criado para isso.
- Ação: criar publicação **opt-in** com slug/token revogável, thumbnail estável e apenas o MP4 final; após export/conclusão, oferecer “Criar link público” e “Compartilhar no WhatsApp”. Medir `share_created → v_view → signup` com UTM. Não tornar jobs públicos por padrão.
- Esforço: L (até 1 semana, incluindo privacidade/revogação)

### [P1] Cards de `/v/[id]` não identificam o vídeo no WhatsApp — (eixo: seo)
- Evidência: a metadata específica contém title, description, canonical e `type`, mas não `openGraph.url`, `images`, `videos` nem `twitter` (`frontend/src/app/v/[id]/page.tsx:28-44`). No Next.js 16, metadata é mesclada superficialmente: ao redefinir `openGraph`, a página substitui o objeto global inteiro, portanto fica sem `og:image`; como `twitter` não é redefinido, mantém o card genérico global (`frontend/src/app/layout.tsx:25-47`; comportamento oficial em `generateMetadata`, seção “Merging”). O manifesto não possui thumbnail/poster por vídeo (`frontend/public/showcase/showcase.json`).
- Impacto: o WhatsApp não recebe imagem/frame específico do vídeo; Twitter/outros consumidores que usam o bloco herdado mostram o mesmo card genérico. O espectador não vê o tema compartilhado, reduzindo CTR e anulando parte do valor do viewer mesmo para os exemplos atuais.
- Ação: primeiro, adicionar `poster` 1200×630 ao manifesto e metadata específica para os oito vídeos atuais (S). No loop de usuário, gerar a mesma thumbnail no finalize e expô-la via URL pública estável (incluído no P0).
- Esforço: S (<2h para showcase; M junto do loop de usuário)

### [P1] A intenção da página de nicho se perde depois do cadastro/OTP — (eixo: produto)
- Evidência: cada nicho já declara template e estilo recomendados (`frontend/src/lib/niches.ts:22-38`), mas o CTA envia somente `utm_campaign=nicho-{slug}` (`frontend/src/app/criar/[nicho]/page.tsx:15-17,68-73`). `useUTM` guarda isso para atribuição e limpa após o cadastro (`frontend/src/hooks/useUTM.ts:5-47`); o dashboard só preenche template/estilo quando o usuário clica posteriormente no `TrendingPanel` (`frontend/src/app/dashboard/page.tsx:17-20,174-181`).
- Impacto: quem chega buscando “vídeo de drama histórico com IA” confirma e-mail e encontra o formulário genérico, sem o template Drama Histórico, estilo storytelling ou um tema de exemplo. O produto perde o contexto de maior intenção no último passo da ativação.
- Ação: guardar um `signup_intent={niche}` separado da atribuição; após OTP, aplicar uma única vez `recommendedTemplate`, `generateStyle` e um tema editável, então apagar. Preservar UTM no usuário para analytics.
- Esforço: S (<2h)

### [P1] Sitemap privilegia auth e omite o hub editorial — (eixo: seo)
- Evidência: o sitemap inclui `/auth/login` e `/auth/register`, não inclui `/blog`, embora liste todos os posts (`frontend/src/app/sitemap.ts:5-29`). Os layouts de login/cadastro definem title/description, mas não `robots: noindex` (`frontend/src/app/auth/login/layout.tsx:3-6`; `frontend/src/app/auth/register/layout.tsx:3-6`); `robots.ts` não os bloqueia (`frontend/src/app/robots.ts:3-11`).
- Impacto: crawl e sinais internos são enviados a páginas utilitárias sem valor de aquisição, enquanto a página que organiza os artigos não recebe descoberta explícita. Também abre espaço para login/register aparecerem em consultas de marca.
- Ação: remover auth do sitemap, adicionar `/blog`, e aplicar `robots: {index:false, follow:false}` ao layout `/auth` inteiro; manter páginas de nicho e posts.
- Esforço: S (<2h)

### [P1] Blog não forma cluster nem conduz à intenção de produto — (eixo: seo)
- Evidência: hub e posts têm OG básico, mas não canonical/Twitter; posts não emitem `BlogPosting` (`frontend/src/app/blog/page.tsx:5-15`; `frontend/src/app/blog/[slug]/page.tsx:11-30`). Navbar e Footer não linkam `/blog` (`frontend/src/components/Navbar.tsx:50-51,108-109`; `frontend/src/components/Footer.tsx:22-41`). Há três posts, com links para a raiz e CTA final genérico de cadastro (`frontend/src/lib/blog-posts.ts:8-134`; `frontend/src/app/blog/[slug]/page.tsx:115-121`).
- Impacto: artigos recebem pouco PageRank interno e não empurram o leitor para a página de nicho correspondente, onde existe prova, conteúdo profundo e CTA atribuído. O blog produz visitas, mas não uma jornada editorial→produto.
- Ação: link `Blog` no footer, canonical/Twitter e `BlogPosting`; em cada artigo, 2–3 links contextuais para `/criar/{nicho}` e CTA final específico. Só depois publicar novos artigos baseados em dúvidas reais de suporte/search console.
- Esforço: S (<2h para infraestrutura + links atuais)

### [P2] Expansão programática: reutilizar o SSG, sem criar uma matriz rasa — (eixo: seo)
- Evidência: o manifesto de nichos já encapsula metadata, copy, FAQs, templates e temas únicos (`frontend/src/lib/niches.ts:22-38,68-391`), e a página SSG consome tudo de uma fonte (`frontend/src/app/criar/[nicho]/page.tsx:19-52`).
- Impacto: existe infraestrutura para cobrir intenções brasileiras de alta intenção, mas um cartesiano `template × nicho × plataforma` repetiria texto e diluiria qualidade. A oportunidade real é pequena e curada.
- Ação: criar primeiro **três** páginas transversais únicas — `/criar/youtube-shorts`, `/criar/instagram-reels`, `/criar/tiktok` — e **duas** de problema — `/criar/video-faceless` e `/criar/video-com-narracao`. Cada uma precisa de exemplo real próprio, copy/FAQ únicos, canonical e links para 2–3 nichos. Publicar 5, medir impressões/cadastros por 30 dias, só então expandir. **Volume de busca não foi validado externamente nesta auditoria.**
- Esforço: M (1 dia de estrutura + conteúdo curado)

### [P2] JSON-LD global descreve `SoftwareApplication` em artigos e viewers — (eixo: seo)
- Evidência: o schema é injetado no `RootLayout`, portanto aparece em todas as rotas (`frontend/src/app/layout.tsx:64-80`). Artigos não adicionam `BlogPosting`, e `/v` não adiciona `VideoObject`.
- Impacto: não é penalidade automática, mas a entidade contextual mais útil está ausente; parsers recebem o mesmo software schema em artigo, auth e vídeo, reduzindo precisão de rich results.
- Ação: manter `Organization`/`WebSite` globais e mover `SoftwareApplication` para home/pricing; adicionar `BlogPosting` nos posts e `VideoObject` apenas quando `/v` tiver thumbnail, uploadDate e contentUrl públicos confiáveis.
- Esforço: S (<2h)

### O que já está correto e não deve ser refeito

- Páginas de nicho têm conteúdo único e profundidade; não são thin content (`frontend/src/lib/niches.ts:1-4,68-391`).
- Canonical, OG, FAQ e Breadcrumb já existem nos nichos; `/exemplos` já é hub de linking.
- Viewer usa vídeo nativo com `preload="metadata"` (`frontend/src/app/v/[id]/page.tsx:72-81`); o problema não é autoplay/payload integral.
- `robots.txt` protege dashboard/editor/API e fluxos sensíveis; a correção é complementar auth, não refazer o arquivo.

---

## Flags de segurança e privacidade

A busca ativa por vulnerabilidades ficou fora do escopo. Não foi encontrada incidentalmente uma vulnerabilidade grave confirmada. Há, porém, uma inconsistência de privacidade que precisa de decisão antes de escalar mídia paga:

### [P1] Política afirma “sem tracking cookies”, mas GA/Meta Pixel podem carregar globalmente — (eixo: qualidade)
- Evidência: a política diz que o ClipIA não usa tracking cookies e usa apenas `localStorage` de sessão (`frontend/src/app/privacidade/page.tsx:64-68`). O layout monta `TrackingScripts` em todas as rotas (`frontend/src/app/layout.tsx:87-94`); quando IDs públicos existem, o componente carrega Google Analytics e Meta Pixel após hidratação (`frontend/src/components/TrackingScripts.tsx:5-27`). **A presença desses IDs no ambiente de produção não foi verificada por proibição de ler `.env`.**
- Impacto: se qualquer tracker estiver ativo, a declaração absoluta pode ficar materialmente incorreta e o carregamento ocorre antes de consentimento. Isso cria risco LGPD/confiança justamente quando social/ads começar a enviar tráfego.
- Ação: decidir e documentar uma das duas políticas: (a) analytics sem publicidade, com configuração de consentimento e texto jurídico correto; ou (b) CMP/consentimento prévio antes de GA/Pixel. Até decidir, não afirmar “apenas localStorage” e não ativar Pixel globalmente.
- Esforço: S para alinhar texto/configuração; M se adotar CMP

---

## Verificação, premissas e claims não verificados

### O que foi verificado

- Código e documentação lidos no `HEAD 5218593a4165676cc7af7813690e683d006fb00c`, branch `feat/editor-reforma`.
- Achados de agentes foram tratados como hipóteses. Três agentes isolados partiram do snapshot antigo `d89117d`; todos os achados promovidos ao relatório foram relidos no HEAD atual. Isso refutou quatro falsos positivos de produto registrados na Fase 1.
- Contratos, callers e guards foram rastreados estaticamente; constantes de custo foram diferenciadas de fatura real.
- Comportamento de merge da Metadata API foi confirmado na documentação oficial do Next.js 16: objetos aninhados como `openGraph` são substituídos, não mesclados, quando redefinidos no segmento filho.
- O relatório foi verificado por placeholders, estrutura pedida, caminhos/linhas citados e estado Git ao final; resultados constam no recap da sessão.

### O que deliberadamente não foi executado

- Nenhum serviço, processo, Docker, worker, tunnel ou banco foi reiniciado/tocado.
- Nenhum `.env`, secret ou valor de chave foi lido.
- Nenhum teste de produto, `next build`, typecheck ou benchmark foi executado: o único write é documentação e a auditoria exigia análise estática; executar build pesado competiria com produção.
- Nenhuma chamada paga de API, geração real, checkout real ou consulta de fatura foi feita.

### Claims que permanecem limitados

- **Custos:** são estimativas de `app/config.py`, não cobrança observada. Câmbio e bônus efetivo de produção não foram lidos; margens em reais devem ser reconciliadas com fatura/provider antes de reprecificar.
- **CWV/editor:** mecanismos de trabalho e tamanhos foram verificados, mas o delta de LCP/INP/fps/bateria não foi medido em runtime.
- **SEO:** metadata, conteúdo e linking foram auditados no código; volume de busca, posição, cobertura do Google e CTR não foram pesquisados externamente nem consultados no Search Console.
- **Privacidade:** a contradição é condicional à presença de `NEXT_PUBLIC_GA_ID`/`NEXT_PUBLIC_META_PIXEL_ID` em produção, valor não acessado nesta rodada.
- **Produção:** nenhum smoke ao vivo foi feito; “código no HEAD” não implica “processo local já reiniciado com esse HEAD”.

### Definição de esforço

- **S:** menos de 2 horas.
- **M:** aproximadamente 1 dia.
- **L:** até 1 semana para uma pessoa, incluindo validação e rollout seguro.
