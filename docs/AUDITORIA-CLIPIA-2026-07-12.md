# Auditoria e otimização completa do ClipIA

> Snapshot de produto: 12/07/2026
> Estado de implementação atualizado em: 13/07/2026
> Branch: codex/clipia-audit-hardening
> Persona primária: criador faceless/temático, em português, pagando em BRL

| Marcador | Definição metodológica |
|---|---|
| Fato confirmado | Observado no código, em teste local, em rota pública, em fonte oficial citada ou definido como decisão explícita no plano aprovado. A coluna de evidência sempre distingue decisão planejada de implementação verificada. |
| Problema | Falha reproduzida ou incompatibilidade objetiva entre contrato e comportamento. |
| Hipótese | Mudança plausível cujo efeito de produto, CRO ou receita ainda precisa de validação. |
| Requer analytics | Pergunta de comportamento, conversão, retenção ou economia sem dados reconciliados. |

Confiança: alta = evidência direta; média = inferência forte; baixa = depende de uso real. Esforço: XS (até 2 h), S (até 1 dia), M (2–5 dias), L (1–3 semanas), XL (mais de 3 semanas). Essa escala é método, não conclusão de negócio.

### Estado autoritativo desta branch

| Marcador | Estado | Página/fluxo | Evidência rastreável | Confiança | Impacto | Esforço restante | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Checkout/verificação e saldo aditivo foram implementados no commit 8b55829; pagamentos serializados, identidade/snapshot canônicos e recuperação crash-safe do checkout estão nos commits cc4d476, 5ac23d6, bf2ac41, e7de16a e 95f4ab7. | Auth, checkout, webhooks e créditos | app/auth/routes.py, app/payments/service.py, tests/test_email_otp.py, tests/test_payment_transactions.py, tests/test_payment_webhook_stripe.py e testes de recovery do checkout. | Alta local | Crítico | M | Repetir os cenários concorrentes com provedores em test mode e stack candidata antes de publicar. |
| Fato confirmado | Operações duráveis e corridas de cancel/finalize foram implementadas nos commits 5b14570, 2cbdc5c e 6b9c2c8. | Geração, rerender e worker | app/services/job_operations.py, app/worker/tasks.py, tests/test_job_operation_integrity.py e tests/test_rerender_refund.py. | Alta | Crítico | M | Migration, testes de interleaving e smoke com broker real verdes. |
| Fato confirmado | O commit e885021 substitui a tentativa rejeitada por outbox durável, snapshots imutáveis de débito, heartbeat SQL, compensação classificada e gate bidirecional de rollback; a revisão adversarial final não encontrou achado Critical/Important. | Débito → dispatch | app/services/dispatch_outbox.py, app/services/refine_balance.py, app/worker/tasks.py, scripts/pre_rollback_refine_gate.py e testes 1C2. Gate local: 137 testes focados; Ruff/pre-commit; PostgreSQL 16 upgrade→gate→downgrade→upgrade. | Alta local | Crítico | M | Antes de publicar, passar broker/provider em test mode, multiprocessos reais, backup e smoke externo. |
| Fato confirmado | O commit ba03321 implementou CI com .[dev], timeout declarado, typegen antes de tsc, readiness aceitando 202 e provenance no health profundo; dez testes locais focais passaram. | CI, readiness e health | .github/workflows/ci.yml, scripts/validate_readiness.py, app/config.py, app/observability.py, tests/test_health_deep.py e tests/test_release_a_operational_contracts.py. | Alta local; nenhuma para CI remoto | Alto | S | CI remoto, candidato e smoke de publicação ainda precisam passar. |
| Fato confirmado | A suíte backend completa passou localmente com 525 testes no snapshot limpo ba03321; depois, 1C2 passou 137 testes, pagamentos passaram 161 locais + 12 PostgreSQL e a Release B backend passou 38 focados com cenários PostgreSQL concorrentes. | Backend inteiro | PowerShell com `C:\Dev\clipia\.venv312\Scripts\python.exe`, basetemp novo, Ruff/pre-commit e round-trip PostgreSQL 16; commits e885021, bf2ac41–95f4ab7 e 9d6eed6. | Alta local | Alto | M | Repetir a suíte completa no SHA final, em CI remoto e com broker/provider test mode. |
| Fato confirmado | A Release B pública está implementada localmente: oferta 2/+18, pacotes/equivalências, intenção de pacote, responsividade, catálogo, Markdown seguro, SEO/canonical e copy factual. | Landing, auth, preços e 29 rotas públicas/auth | Commits 162d8cf, 9d6eed6, aa71128 e 095fe83; typegen e tsc verdes; Playwright `26 passed`, incluindo matriz de 29 rotas × 4 viewports = 116 acessos. | Alta local | Alto | S | Repetir no SHA candidato e manter zero regressão no smoke externo. |
| Fato confirmado | O armazenamento append-only e a ingestão first-party foram implementados no commit acb647c, desabilitados por padrão: 13 eventos cliente com properties tipadas, 1–20 eventos/64 KB, autenticação opcional estrita, rate limit, idempotência e rejeição de PII/campos desconhecidos. | Analytics/API | app/analytics, migration f3a4b5c6d7e8 e 46 testes locais + 3 PostgreSQL; concorrência preservou uma linha e triggers rejeitaram UPDATE/DELETE. | Alta local | Alto | M | Manter flag off até aprovação de Privacidade; instrumentação cliente/servidor, RBAC e dashboard continuam pendentes. |
| Fato confirmado | Os agregados administrativos de jobs, créditos, refunds e compras foram reconciliados com estados financeiros canônicos e snapshots duráveis no commit e64d217. | Admin financeiro/observabilidade | app/api/routes.py, app/observability.py e tests/test_admin_financial_baseline.py; 171 testes expandidos e caso PostgreSQL real. | Alta local | Crítico | S | Usar como baseline apenas após publicação candidata e conferência contra dados reais. |
| Problema | Nenhuma Release A/B desta branch foi publicada; backup, migration no candidato, provider test mode e smoke externo continuam pendentes. | Publicação | Ausência de evidência de deploy e gates de publicação abaixo. | Alta | Crítico | M | Não reiniciar produção antes de todos os gates e manter rollback pronto. |

### Premissas e limites aprovados

| Marcador | Decisão ou limite | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | O produto continuará pré-pago, em BRL, sem assinatura automática e sem expiração; preços nominais e hero serão preservados. | Landing, preços e checkout | Plano aprovado e CREDIT_PACKAGES em app/payments/schemas.py. | Alta | Alto | XS | Diff não altera recorrência, preços nominais, expiração, hero ou identidade. |
| Fato confirmado | Novas verificações recebem 2 créditos; saldos existentes não são reduzidos. Testadores recebem +18 somente pelo ajuste administrativo existente, com motivo beta_invite_2026. | Verificação e admin | Commit 9d6eed6; testes de CAS, saldo existente e ajuste administrativo concorrente. | Alta local | Alto | XS | Manter bônus one-shot, saldo antigo intacto e ajuste admin auditável no candidato. |
| Fato confirmado | Analytics ficará atrás de flag até aprovação de Privacidade; GA/Meta e pixels de marketing permanecem desligados. | Produto inteiro | Plano aprovado e BACKLOG-AUDITORIA-2026-07-11.md. | Alta | Crítico | M | Flag off não coleta; texto jurídico só muda após revisão. |
| Fato confirmado | Nenhuma política de retenção financeira será inventada, nenhum serviço de produção será reiniciado antes dos gates e nenhum pagamento, geração paga ou envio real será usado nos testes. | Legal, QA e deploy | Limites do plano. | Alta | Crítico | XS | Checklist de release registra test mode, não objetivos e aprovação jurídica. |

## A. Veredito executivo

| Marcador | Conclusão | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Hipótese | Nota do snapshot: 58/100. O ciclo de valor existe, mas risco financeiro e ausência de baseline impedem otimização comercial segura; a nota é julgamento composto, não KPI. | Produto inteiro | Código, 29 rotas públicas/auth mapeadas e docs/INSIGHTS-GPT56-2026-07-12.md. | Média | Alto | — | Reavaliar somente após Release A aprovada, Release B publicada e 14 dias de baseline. |
| Fato confirmado | A maior qualidade é o ciclo tema → roteiro → voz → mídia → vídeo editável → exportação, com compra avulsa em BRL. | Geração, editor e créditos | app/worker/tasks.py, app/services/remotion.py, frontend/src/app/editor e app/payments/schemas.py. | Alta | Alto | XS | Preservar o ciclo, o editor e o modelo pré-pago em todas as releases. |
| Hipótese | Uma pessoa poderia não comprar porque o snapshot concedia 20 créditos grátis contra 12 totais no Starter; o efeito causal sobre compra não está provado. | Verificação → compra | Oferta do snapshot e pacote Starter 10+2. | Alta para a discrepância; média para o efeito | Alto | S | Liberar 2 só para novas verificações e medir gratuito → primeira compra por coorte. |
| Problema | O caminho financeiro P0 está corrigido e revisado localmente, inclusive identidade/snapshot canônicos e recovery crash-safe, mas ainda não é publicável sem backup, migrations no candidato, broker/provider em test mode e smoke externo. | Saldo, webhooks, jobs, dispatch e pagamentos | Commits 8b55829–95f4ab7, e885021 e matrizes concorrentes locais/PostgreSQL. | Alta local | Crítico | M | Passar todos os gates externos sem cobrança, geração paga ou envio real. |
| Requer analytics | Não é possível afirmar se o maior vazamento está em CTA, cadastro, verificação, primeira geração, exportação ou pagamento. | Funil de ativação e receita | Armazenamento/ingestão e agregados foram implementados, mas emissão cliente/servidor, dashboard, publicação e baseline ainda inexistem. | Alta | Alto | L | Após revisão de Privacidade, instrumentar o funil e coletar 14 dias por origem, nicho e dispositivo. |
| Hipótese | A direção de monetização mais coerente é pré-pago aprimorado, agora com equivalências autoritativas; recomendação após o primeiro valor ainda exige baseline. | Landing, exportação e créditos | Modelo atual, quatro benchmarks oficiais, API pública implementada e ausência de COGS/coortes reais. | Média | Alto | M | Medir COGS e testar recomendação pós-exportação somente após baseline. |
| Fato confirmado | A Release B corrigiu localmente intenção de pacote perdida, largura móvel forçada, nichos sem exemplo e crédito abstrato; a base first-party existe atrás de flag, mas o funil completo e o baseline ainda não. | Cadastro, mobile, nichos, preços e analytics | Commits 162d8cf, 9d6eed6, aa71128, 095fe83 e acb647c; 26 Playwright e gates de analytics verdes. | Alta local | Alto | L | Publicar apenas após gates, revisão de Privacidade e instrumentação autoritativa do funil. |

## B. O que já funciona bem

| Marcador | Ponto a preservar | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Fluxo completo até resultado editável e exportável. | Dashboard → editor → exportação | app/api/routes.py, app/worker/tasks.py e app/services/remotion.py. | Alta | Alto | S | Smoke cobre gerar, acompanhar, editar e exportar. |
| Fato confirmado | Pacotes pré-pagos de R$ 19,90, R$ 49,90 e R$ 129,90. | Preços e checkout | CREDIT_PACKAGES em app/payments/schemas.py. | Alta | Alto | XS | API e UI usam a mesma fonte e o checkout congela snapshot. |
| Fato confirmado | Custo aparece antes de ações pagas; o lote anterior incluiu refinamento na UI. | Criação e editor | BACKLOG-AUDITORIA-2026-07-11.md e GenerateForm. | Alta | Alto | S | E2E compara custo mostrado, debitado e devolvido. |
| Fato confirmado | Hero, sistema visual e prova em vídeo formam uma base útil; o preload pesado foi mitigado. | Landing | frontend/DESIGN.md e matriz dos 19 ajustes na seção I. | Alta | Médio | XS | Não redesenhar; medir LCP/INP sem regressão. |
| Fato confirmado | Hamburger móvel foi preservado e a causa do overflow foi removida; 320/390/393 px passam sem `overflow-x:hidden` global. | Navegação | Commit 162d8cf e matriz Playwright do commit 095fe83. | Alta local | Médio | XS | Manter navegação completa e scrollWidth dentro da viewport. |
| Fato confirmado | Nichos, exemplos, blog, suporte, termos e privacidade já oferecem superfície orgânica e de confiança. | Rotas públicas | frontend/src/app e sitemap. | Alta | Médio | S | Rotas 200, conteúdo não vazio, canonical apex. |
| Fato confirmado | Voz padrão, diálogo, mídia/refinamento por IA e vídeo IA diferenciam o produto de um editor convencional. | Criação | app/templates.py, app/pricing.py e app/worker/tasks.py. | Alta | Alto | S | Copy descreve somente capacidade existente. |
| Fato confirmado | O lote anterior saiu com 445 testes, typegen e tsc verdes e não foi deployado. | Qualidade | BACKLOG-AUDITORIA-2026-07-11.md e docs/superpowers/reviews/2026-07-12-triagem-gpt56/round1.md. | Alta | Alto | M | Preservar os 19 ajustes e repetir verificação no SHA final. |

## C. Principais problemas

| Prioridade | Marcador | Problema/estado | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|
| P0 | Problema | Cancelamento/refund após entrega foi corrigido em 1C1, mas só é publicável após migration e stack representativa. | Jobs e rerender | Commits 5b14570, 2cbdc5c, 6b9c2c8; tests/test_job_operation_integrity.py. | Alta local | Crítico | M | Entregue/editable retorna 409; refund exato one-shot em PostgreSQL. |
| P0 | Problema | Eventos fora de ordem e saldo concorrente foram corrigidos em 1A/1B; prova multiprocesso real continua pendente. | Stripe, MP, saldo e verificação | Commits 8b55829, cc4d476, 5ac23d6 e testes financeiros rastreados. | Alta local | Crítico | M | refund→paid, paid→refund, replay e concorrência preservam delta exato. |
| P0 | Fato confirmado | Débito → dispatch foi corrigido e aprovado localmente no commit e885021. | Generate, render, worker e watchdog | Outbox/heartbeat/rollback gate e 137 testes 1C2. | Alta local | Crítico | M | Completar broker/provider test mode e smoke multiprocessos antes de publicar. |
| P0 | Problema | CI/readiness/health foram implementados no commit ba03321 e têm dez testes locais, mas CI remoto/publicação estão pendentes. | Release | .github/workflows/ci.yml, scripts/validate_readiness.py e tests/test_release_a_operational_contracts.py. | Alta local | Alto | S | Workflow remoto verde e health do candidato mostra provenance sem segredo. |
| P1 | Fato confirmado | A oferta local agora concede 2 créditos a novas verificações; contas existentes não perdem saldo e beta +18 usa ajuste admin auditável. | Verificação → compra | Commit 9d6eed6 e testes Release B backend. | Alta local | Alto | XS | Repetir no candidato sem alterar contas reais. |
| P1 | Fato confirmado | selected_package atravessa cadastro, OTP e checkout; `professional` público é traduzido para o contrato legado sem checkout automático. | CTA → auth → checkout | Commits 9d6eed6 e aa71128; testes backend e Playwright de persistência/troca/reload. | Alta local | Alto | XS | Candidato preserva pacote e permite troca antes do checkout. |
| P1 | Fato confirmado | A causa de 426 px foi removida e as 29 rotas passam em desktop e 320/390/393. | Rotas públicas/auth | Commits 162d8cf e 095fe83; 116 acessos Playwright sem overflow. | Alta local | Alto | XS | Manter scrollWidth ≤ clientWidth sem remendo global. |
| P1 | Fato confirmado | Nichos sem vídeo omitem a grade e exibem “Ver todos os exemplos”; nichos com vídeo usam apenas o catálogo canônico. | /criar/[nicho] | Commit 162d8cf e teste dos sete nichos em 095fe83. | Alta local | Médio | XS | Zero grade vazia no candidato. |
| P1 | Fato confirmado | Os três artigos renderizam Markdown GFM sem raw HTML, com componentes permitidos e links externos seguros. | Blog | Commit 162d8cf e Playwright de todos os artigos. | Alta local | Médio | XS | Sem Markdown literal, script/iframe ou link externo inseguro. |
| P1 | Fato confirmado | Redirect 308 `www→apex`, canonical por rota, metadata específica, datas consistentes e viewers no sitemap foram implementados. | Rotas indexáveis | Commits 162d8cf e 095fe83; teste das 24 rotas indexáveis. | Alta local | Alto | XS | Um canonical apex por rota e sitemap sem `www`. |
| P1 | Problema | Tabela/endpoint first-party e agregados reconciliados existem localmente, mas eventos de produto, dashboard/coortes, RBAC específico e baseline não. | Funil inteiro | Commits acb647c e e64d217; flag desabilitada por padrão. | Alta | Alto | L | Aprovação de Privacidade, instrumentação autoritativa, RBAC, coortes e 14 dias de baseline. |
| P2 | Fato confirmado | IDs opacos server-owned, reset one-time, consentimento versionado e upload streaming com MIME/magic bytes foram concluídos localmente. | Mídia, auth e upload | Commits e6225d6, 63169e3 e e802fd6; 101 testes focados de assets/voz e suites específicas anteriores. | Alta local | Crítico | L | Repetir threat/regression tests no SHA candidato; nenhum path/URL do cliente é resolvido. |
| P2 | Fato confirmado | A Release 1 de autenticação por cookie foi concluída localmente: sessão host-only HttpOnly/SameSite=Lax, Secure em produção, CSRF vinculado ao JWT, origem validada, logout e Bearer/localStorage compatíveis. | Auth e infraestrutura | Commit 5060447; `app/auth/session.py`, frontend, testes de cookie/CSRF e métrica `clipia_auth_transport_total`. | Alta local | Crítico | M | Publicar candidato, acompanhar cookie vs Bearer e só remover localStorage na Release 2 após telemetria verde. |
| P2 | Fato confirmado | O ledger append-only em `shadow`, o backfill, os triggers de cobertura total e a reconciliação diária foram concluídos localmente; `User.credits` segue como projeção autoritativa. | Créditos | Commit 3643178; migration b5c6d7e8f9a0, testes SQLite/PostgreSQL e seis concorrências financeiras reais. | Alta local | Crítico | L operacional | Manter `shadow` e obter sete dias UTC consecutivos sem diferença; startup recusa `enforce` antes desse gate. |

## D. Mapa do funil

| Etapa | Marcador | Diagnóstico/objetivo | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Evento autoritativo e aceite |
|---|---|---|---|---|---|---|---|---|
| Origem/landing | Requer analytics | Atribuir aquisição e compreensão inicial sem assumir conversão. | Landing/nichos | Baseline ausente; hero existe. | Alta | Alto | M | landing_viewed; UTMs enumeradas e sem PII direta. |
| Exemplo | Fato confirmado | A grade vazia foi removida e o catálogo canônico está aplicado; a resposta comportamental ainda exige eventos. | Landing/nichos/exemplos | Commit 162d8cf e testes dos sete nichos. | Alta local | Alto | S | Instrumentar example_played/completed; manter zero grade vazia. |
| CTA/pacote | Fato confirmado | A intenção escolhida persiste até checkout e pode ser trocada antes da compra. | Preço → cadastro | Commits 9d6eed6 e aa71128; testes de cadastro/OTP/reload. | Alta local | Alto | XS | Instrumentar pricing_package_selected sem perder `professional`. |
| Cadastro | Hipótese | Reduzir fricção sem coletar dados desnecessários. | Auth/register | Fluxo atual. | Média | Alto | M | signup_started cliente; signup_completed servidor; erros acessíveis. |
| OTP/verificação | Fato confirmado | A conta é verificada por CAS, recebe 2 créditos de forma aditiva e retoma o pacote; a copy “Enviar código” foi corrigida. | Auth/verify | Commits 8b55829, 9d6eed6 e aa71128; testes backend/Playwright. | Alta local | Alto | S | Instrumentar email_verified no servidor sem alterar a idempotência. |
| Dashboard/configuração | Hipótese | Levar ao primeiro valor com objetivo/nicho opcionais e exemplo preenchido. | Dashboard | Não há baseline. | Média | Alto | L | onboarding e video_creation_started; tudo pulável/editável. |
| Geração | Fato confirmado | Debitar e despachar uma vez, com reconciliação durável. | Generate/worker | 1C1 e 1C2 aprovados localmente; gates externos pendentes. | Alta local | Crítico | M | video_generation_requested servidor ligado a operation_id; terminal reconciliável e smoke multiprocessos antes do deploy. |
| Espera/resultado | Hipótese | Manter retorno sem ETA inventado e abrir resultado editável. | Status/editor | E-mail pronto existe; impacto não medido. | Média | Alto | M | completed/failed servidor; e-mail one-shot e estado sem regressão. |
| Exportação | Problema | Consolidar primeiro valor sem refund incorreto. | Editor/render | Operação durável de rerender. | Alta | Crítico | M | video_export_requested servidor; exported/failed após DB commit. |
| Pacote/checkout | Fato confirmado | A API pública explica equivalências e o checkout congela pacote, valor, moeda, créditos e bônus. | Créditos/checkout | Commits bf2ac41, 9d6eed6 e aa71128. | Alta local | Alto | M | Instrumentar checkout_started no servidor sem aceitar snapshot do cliente. |
| Pagamento/crédito | Fato confirmado | Webhooks e reconciliação local creditam ou estornam exatamente uma vez nas ordens e repetições testadas. | Webhooks/saldo | Commits cc4d476, 5ac23d6, bf2ac41, e7de16a e 95f4ab7; 161 testes locais + 12 PostgreSQL. | Alta local | Crítico | M | Instrumentar payment_completed/credits_added e passar provider test mode. |
| Segundo vídeo/recompra | Requer analytics | Medir ativação profunda e repetição. | Dashboard/créditos | Eventos/coortes inexistentes. | Alta | Alto | L | second_video_generated servidor one-shot; coortes 7/30/90. |

## E. Monetização recomendada

### Benchmark oficial

| Marcador | Conclusão | Página/fluxo | Evidência oficial | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | CapCut informa variação de preço por região, dispositivo e promoção e oferece mensal/anual. | Benchmark | [CapCut Help](https://www.capcut.com/pt-br/help/how-much-does-capcut-pro-cost), consultado em 13/07/2026. | Alta | Médio | — | Não congelar preço concorrente na copy. |
| Fato confirmado | VEED apresenta entrada gratuita, upgrades, créditos de IA e add-ons. | Benchmark | [VEED Pricing](https://www.veed.io/pricing), consultado em 13/07/2026. | Alta | Médio | — | Usar somente como referência de framing. |
| Fato confirmado | InVideo combina planos, créditos e top-ups; créditos mensais não usados não rolam. | Benchmark | [InVideo Pricing](https://invideo.io/pricing/), consultado em 13/07/2026. | Alta | Alto | — | Preservar diferenciação pré-paga em BRL e sem expiração. |
| Fato confirmado | Pictory separa criação, edição, escala, equipes e API. | Benchmark | [Pictory Pricing](https://pictory.ai/pricing), consultado em 13/07/2026. | Alta | Médio | — | Não construir oferta agência antes de demanda/COGS. |

### Economia unitária e pacotes

| Marcador | Conclusão/cálculo | Página/fluxo | Evidência/inputs | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Requer analytics | COGS real não é calculável neste snapshot. Config versionada não substitui faturas, compute, storage, tráfego, suporte, taxas, impostos, chargebacks e câmbio. | Economia unitária | app/config.py e ausência de custo reconciliado por operation_id. | Alta | Crítico | L | COGS p50/p95 por modo/provedor fecha com faturas e câmbio auditável. |
| Requer analytics | Fórmula aprovada: preço = [créditos × custo médio real × margem de segurança + custos fixos] / [1 − taxas − impostos − chargebacks − margem alvo]. O resultado é indeterminado sem inputs reais. | Pricing | Inputs ainda não reconciliados. | Alta | Crítico | L | Versionar cada input, período, moeda e output antes de decidir preço. |
| Fato confirmado | Starter permanece R$ 19,90, 10+2=12: até 12 vídeos de voz padrão, 6 de diálogo, 24 refinos de roteiro, 2 vídeos com imagem IA e 0 com vídeo IA. | Preços | GET público `/api/v1/credits/packages`; custos 1/2/0,5/5/30 em app/credits.py e config. | Alta local | Alto | XS | API calcula floor(total/custo), separa modos distintos e usa “até”. |
| Fato confirmado | Popular permanece R$ 49,90, 30+6=36: até 36 vídeos de voz padrão, 18 de diálogo, 72 refinos de roteiro, 7 vídeos com imagem IA e 1 com vídeo IA. | Preços | GET público `/api/v1/credits/packages` e snapshot do checkout. | Alta local | Alto | XS | Checkout congela base, bônus, total, preço e moeda. |
| Fato confirmado | Profissional permanece R$ 129,90, 100+20=120: até 120 vídeos de voz padrão, 60 de diálogo, 240 refinos de roteiro, 24 vídeos com imagem IA e 4 com vídeo IA; a API pública usa `professional` e mantém compatibilidade controlada com `pro`. | Preços/checkout | Commit 9d6eed6, app/credits.py, app/payments/schemas.py e testes de contrato/checkout. | Alta local | Alto | XS | Candidato aceita intenção pública sem alterar compras legadas. |

### Quatro modelos, inputs e outputs

| Modelo | Marcador | Inputs reais necessários | Output calculável | Cenário ilustrativo, não recomendação | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|---|---|
| A — pré-pago aprimorado | Requer analytics | COGS/crédito por modo, mix de uso, fixos alocados, taxas, impostos, chargebacks e margem alvo. | Preço mínimo por pacote, margem por operação/pacote e sensibilidade ao bônus. | Substituir os símbolos da fórmula pelos inputs medidos para 12/36/120 créditos; nenhum número gerado aqui é preço real. | Landing, créditos e checkout | Modelo atual e benchmark. | Alta para aderência; nenhuma para margem | Alto | M | Medição por operation_id e pacote antes de qualquer ajuste nominal. |
| B — assinatura | Requer analytics | Inputs de A + consumo mensal, churn, inadimplência, rollover, suporte e custo dos benefícios. | Mensalidade mínima, margem mensal, passivo de créditos e LTV/CAC observável. | P_B = fórmula aplicada aos créditos mensais + benefícios/rollover; sem inputs, P_B é indeterminado. | Futuro pricing recorrente | Concorrentes usam assinatura; ClipIA não tem coortes. | Baixa | Alto | L | Só reavaliar após gates da seção N; não lançar automaticamente. |
| C — híbrido | Requer analytics | Inputs A/B + canibalização do avulso, attach rate de clube e top-ups. | Mensalidade, margem combinada e efeito sobre recompra/ticket. | P_C = mensalidade mínima calculada + top-ups atuais; cenário apenas algébrico. | Futuro pricing | Hipótese de recorrência sem baseline. | Baixa | Alto | XL | Pesquisa de intenção e duas coortes qualificadas antes de cobrança. |
| D — agência/volume | Requer analytics | COGS p95, volume contratado, assentos, suporte/SLA, infra incremental, inadimplência e margem alvo. | Mínimo contratual, preço incremental, capacidade e margem por conta. | P_D = [volume × COGS p95 × segurança + suporte/SLA/fixos] / denominador; não é proposta comercial. | B2B futuro | Persona secundária e demanda não comprovada. | Baixa | Alto | XL | 5 entrevistas, 3 propostas e 1 piloto pago antes de produto dedicado. |
| Recomendação | Fato confirmado | Inputs reais de A–D ainda ausentes. | Manter A; nenhum preço/margem novo é calculável. | Cenário de escopo, não cenário econômico: B/C/D ficam fechados até os gates. | Produto/preços | Plano aprovado e ausência de inputs reais. | Alta para a decisão | Crítico | XS | Nenhuma assinatura/híbrido/agência é publicada automaticamente. |

## F. Nova estrutura da landing

| Ordem | Marcador | Seção/recomendação | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---:|---|---|---|---|---|---|---|---|
| 1 | Fato confirmado | Preservar navegação e hamburger: Produto, Exemplos, Como funciona, Preços, Entrar. | Landing | Componentes existentes. | Alta | Médio | S | Teclado e 320/390/393 completos. |
| 2 | Hipótese | Hero preservado com promessa factual, vídeo real e 2 créditos. | Landing | Base visual atual. | Média | Alto | S | Sem redesign; copy vem de fonte autoritativa. |
| 3 | Hipótese | Exemplos/prova imediatamente após hero. | Landing → exemplos | Nichos vazios e ceticismo observados. | Média | Alto | M | Catálogo real, sem grade vazia; medir K2. |
| 4 | Hipótese | Como funciona: tema → ajuste → vídeo editável. | Landing → cadastro | Pipeline real. | Alta | Alto | S | Três passos correspondem ao produto e mostram custo. |
| 5 | Hipótese | Públicos/nichos, com faceless/temático primário. | Landing → nichos | Persona aprovada. | Média | Médio | S | Uma persona domina headline/casos. |
| 6 | Fato confirmado | Recursos/resultados reais: roteiro, voz, diálogo, mídia, legendas, editor e exportação. | Landing | Capacidades em código. | Alta | Médio | M | Cada claim tem tela ou exemplo. |
| 7 | Hipótese | Preços/equivalências e CTAs Escolher Starter/Popular/Profissional. | Preços → cadastro | Crédito abstrato/intenção perdida. | Média | Alto | M | professional persiste até checkout. |
| 8 | Hipótese | FAQ/confiança: custo, tempo variável, edição, Pix e cartão, falhas, privacidade e suporte. | Landing | Dúvidas do fluxo. | Média | Alto | S | Sem garantia jurídica/prazo inventado. |
| 9 | Hipótese | CTA final com 2 créditos. | Landing → cadastro | Dead-end possível. | Média | Médio | XS | Evento único e origem/pacote preservados. |
| 10 | Fato confirmado | Rodapé preserva suporte, legal, exemplos, nichos e identidade. | Landing | Rotas existentes. | Alta | Médio | S | Links 200, metadata e canonical por rota. |
| Gate | Hipótese | A ordem acima é experimento K10, não autorização de substituição: instrumentar, medir a atual e testar isoladamente. | Landing inteira | Baseline inexistente. | Alta | Alto | M | Uma variante, poder/guardrails definidos e rollback. |

## G. Copy pronta

| Marcador | Decisão/copy | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Hipótese | Posicionamento: “Para criadores de páginas faceless e temáticas, o ClipIA transforma um tema em vídeo narrado, legendado e editável, reunindo roteiro, voz, mídia e edição com créditos pré-pagos em reais.” | Landing | Persona e capacidades reais. | Média | Alto | XS | Teste de compreensão; nenhum claim de resultado comercial. |
| Hipótese | Hero factual recomendado: “Crie vídeos curtos com IA, do tema ao arquivo pronto para publicar.” Sub: “Gere roteiro, narração, mídia e legendas em português. Revise no editor antes de exportar.” | Hero | Capacidades reais. | Alta | Alto | XS | Publicar somente após validar oferta de 2 na API. |
| Fato confirmado | Microcopy publicada localmente: “Comece com 2 créditos grátis — até 2 vídeos com voz padrão. Sem cartão.” | Hero/cadastro | Fonte compartilhada no frontend e config/backend com custo padrão 1. | Alta local | Alto | XS | Novas verificações recebem 2; saldos existentes intactos. |
| Hipótese | Alternativa 2: “Transforme uma ideia em um vídeo faceless editável.” | Hero | Persona. | Média | Alto | XS | Somente experimento com baseline. |
| Hipótese | Alternativa 3: “Seu tema entra. Um vídeo pronto para ajustar e publicar sai.” | Hero | Diferencial funcional. | Média | Alto | XS | Teste qualitativo; sem promessa de viralização. |
| Fato confirmado | Decisão editorial: publicar a opção factual 1; opções 2/3 só em experimento elegível. | Hero | Plano aprovado. | Alta para a decisão | Alto | XS | Uma copy por vez e evento de exposição. |
| Fato confirmado | CTAs “Escolher Starter”, “Escolher Popular” e “Escolher Profissional” foram aplicados aos pacotes. | Preços → auth | Pricing e CreditPackageCard; Playwright de atribuição. | Alta local | Alto | XS | selected_package usa professional no contrato público. |
| Fato confirmado | O botão foi corrigido para “Enviar código”. | Auth | Commit aa71128 e Playwright específico. | Alta local | Médio | XS | String e acessibilidade verificadas. |
| Hipótese | Checkout: “Você escolheu {pacote}: {total} créditos por {preço}. Pagamento por Pix e cartão.” | Checkout | Snapshot financeiro congelado. | Alta | Crítico | S | Dados vêm do servidor e não alteram texto jurídico. |
| Hipótese | Falha: “Não conseguimos concluir esta operação. Consulte o status usando o código {id}.” Só afirmar devolução quando o servidor confirmar. | Geração/exportação | 1C2 aprovado localmente; broker/provider e smoke externo ainda pendentes. | Alta | Crítico | S | Nenhuma promessa de refund antes do estado autoritativo. |
| Hipótese | Saldo insuficiente: “Faltam {n} créditos para esta ação. Veja quantos vídeos cada pacote permite.” | Criação/editor | Upsell contextual. | Média | Alto | S | Abrir preços preserva projeto/formulário. |
| Requer analytics | Não usar números de clientes/depoimentos sem base auditada e autorização. | Landing | Prova social não validada. | Alta | Alto | S | Zero prova fabricada; consentimento rastreável. |
| Fato confirmado | A correção móvel passou no gate local: a copy “Funciona no celular” pode ser usada, sujeita à repetição no candidato. | FAQ/mobile | Matriz Playwright das 29 rotas em 320/390/393, sem overflow. | Alta local | Alto | XS | Repetir a matriz no SHA candidato antes de publicar. |

## H. Novo onboarding

| Etapa | Marcador | Ação/recomendação | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Evento e critério de aceite |
|---:|---|---|---|---|---|---|---|---|
| Gate | Requer analytics | Implementar somente após 14 dias de baseline; manter curto e pulável quando apropriado. | Auth → primeiro valor | Funil sem baseline. | Alta | Alto | L | Não ativar flag antes de coorte, agregados e Privacidade aprovados. |
| 1 | Hipótese | Cadastro mínimo e verificação com 2 créditos. | Auth | Fluxo atual + direção de oferta. | Alta | Alto | M | signup_completed/email_verified server-side; bônus one-shot. |
| 2 | Fato confirmado | Se houver intenção, o fluxo atual confirma o pacote e permite troca; `professional` público é traduzido com compatibilidade no checkout. | Pós-OTP | Persistência implementada em 9d6eed6/aa71128. | Alta local | Alto | XS | E2E cadastro → OTP → checkout preserva starter/popular/professional. |
| 3 | Hipótese | Sem pacote, objetivo e nicho opcionais, com “Pular”. | Onboarding | Persona/nichos. | Média | Médio | M | Sem texto livre no analytics; não bloqueia primeiro valor. |
| 4 | Hipótese | Primeiro vídeo com template/roteiro preenchido e custo/saldo antes de gerar. | Dashboard | Tela vazia pode criar fricção. | Média | Alto | L | Tudo editável; custo server-authoritative. |
| 5 | Hipótese | Progresso, resultado editável e exportação com deep-link seguro. | Geração/editor | Produto e e-mail existentes. | Alta | Alto | M | Estado sobrevive refresh; requested/export requested são servidor. |
| 6 | Hipótese | Feedback e pacote somente após primeira exportação. | Resultado → preços | Venda pós-valor. | Média | Alto | M | Sem modal bloqueante; medir K5. |

## I. Auditoria técnica

### Release A e estado técnico

| Marcador | Estado/achado | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | 1A/1B usam CAS, atualização SQL relativa, compra/eventos serializados e snapshot de checkout validado. | Auth, saldo e webhooks | Commits 8b55829, cc4d476, 5ac23d6; testes financeiros rastreados. | Alta local | Crítico | M | PostgreSQL concorrente e fixtures assinadas em test mode. |
| Fato confirmado | 1C1 persiste operação/custo/snapshot, bloqueia cancel inválido e coordena finalize/cancel. | Jobs/rerender | Commits 5b14570, 2cbdc5c, 6b9c2c8. | Alta local | Crítico | M | Migration e interleavings em stack representativa. |
| Fato confirmado | 1C2 foi corrigido no commit e885021 e aprovado por revisão adversarial sem achado Critical/Important. | Dispatch/reconciler/watchdog | 137 testes focados, Ruff/pre-commit e PostgreSQL 16 upgrade→gate→downgrade→upgrade. | Alta local | Crítico | M | Preservar quiescência no rollback e executar broker/provider/multiprocessos reais antes de deploy. |
| Fato confirmado | ba03321 atende contrato local de CI/readiness/provenance e teve dez testes focais verdes. | Release/health | Arquivos e testes da matriz inicial. | Alta local | Alto | S | CI remoto e smoke do candidato. |
| Problema | 525 testes do snapshot e 137 testes 1C2 não substituem PostgreSQL multiprocesso, broker/provider test mode, backup ou smoke externo. | Gate de release | Limitação dos doubles e do smoke de migração local. | Alta | Crítico | M | Executar todos os gates M sem cobrança, geração paga ou envio real. |

### Matriz dos 19 ajustes presentes no HEAD de origem

| # | Marcador | Ajuste preservado | Página/fluxo | Evidência/estado | Sobreposição com este plano | Teste/evidência de verificação | Confiança | Impacto | Esforço | Critério de aceite |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | Fato confirmado | Custo exibido inclui floor(refinePending) e credit_cost tipado. | GenerateForm | BACKLOG e round1: aplicado, não deployado. | CRO financeiro; não substituir pela nova operação. | Typegen/tsc verdes no lote; preservar E2E custo mostrado=debitado. | Alta | Alto | XS | Sem regressão 402 por custo omitido. |
| 2 | Fato confirmado | E-mail “vídeo pronto” idempotente com deep-link. | Worker → editor | round1 e tests/test_video_ready_email.py; aplicado, não deployado. | Analytics K7/onboarding. | Teste rastreado específico, três casos no lote. | Alta | Alto | XS | Um envio por conclusão; falha de e-mail não muda job. |
| 3 | Fato confirmado | Copy de bônus tornou-se estável, sem número hardcoded nas superfícies SSG. | Landing/blog/nichos | BACKLOG/round1 preservados; Release B passou a servir 2 por config autoritativa. | Release B concluída localmente. | Typegen/tsc e Playwright de copy/config verdes. | Alta local | Alto | XS | Nenhuma divergência API/copy. |
| 4 | Fato confirmado | ai_video ganhou teto MAX_SCENES_AI_VIDEO=8 escalado, validação de custom_script e telemetria len(scenes)×5 s. | Script/geração/telemetria | round1; aplicado, não deployado. | COGS/segurança financeira. | tests/test_ai_video_guardrail.py e tests/test_telemetry_economy.py. | Alta | Crítico | XS | Teto atua antes do custo e segundos batem com clipes enviados. |
| 5 | Fato confirmado | Cancelamento é checado durante poll do provider e tratado como cancelamento no worker. | Vídeo IA | round1; aplicado; reuso de clipes segue backlog. | 1C1 cobre operação, não substitui cancel externo. | tests/test_video_gen_cancel.py, dois testes no lote. | Alta | Crítico | S | Cancel interrompe novos polls; clipes órfãos completos continuam backlog explícito. |
| 6 | Fato confirmado | dialogue_duo é precificado server-side pelo template efetivo. | Generate/pricing | round1; aplicado. | Integridade financeira. | tests/test_narration_mode.py e teste direto citado no round1. | Alta | Crítico | XS | dialogue_duo não aceita payload que cobre 1 crédito. |
| 7 | Fato confirmado | POST /generate responde 202. | API/generation | round1; aplicado. | ba03321 atualiza readiness para 200/202. | Treze asserts migrados no lote; tests/test_release_a_operational_contracts.py. | Alta | Alto | XS | OpenAPI/readiness/clientes aceitam 202. |
| 8 | Fato confirmado | Hero usa poster e preload=metadata, preservando autoplay. | Landing | round1 preservado. | Release B preservou hero; ordem continua experimento. | Typegen/tsc e Playwright funcional verdes; CWV de campo pendente. | Alta local | Alto | XS | Sem download antecipado de 7,1 MB e sem regressão visual. |
| 9 | Fato confirmado | Sliders usam ThrottledRange. | Editor | round1; aplicado. | Performance do editor. | Typegen/tsc verdes; fidelity browser pendente. | Alta estática | Médio | XS | Drag não remonta por cada passo; preview=export. |
| 10 | Fato confirmado | Dois canvases não mantêm RAF ocioso. | Editor | round1; aplicado. | Performance/RUM. | Typegen/tsc verdes; medir INP/CPU em campo. | Alta estática | Médio | XS | Pausado não agenda loop contínuo. |
| 11 | Fato confirmado | Texto de cena usa rascunho local e debounce 400 ms/blur. | Editor | round1; aplicado. | Onboarding/editor. | Typegen/tsc verdes; teste de undo/blur pendente. | Alta estática | Médio | XS | Digitação não cria um undo por tecla e flush ocorre no blur. |
| 12 | Fato confirmado | FilmGrain virou textura estática. | Layout global | round1; aplicado. | Performance pública. | Typegen/tsc verdes; RUM pendente. | Alta estática | Médio | XS | Nenhum timer/ImageData contínuo. |
| 13 | Fato confirmado | Modal tem focus trap. | Auth/dashboard/editor | round1; aplicado. | Acessibilidade das ações pagas. | Verificação do lote; Playwright teclado pendente. | Alta estática | Alto | XS | Tab/Shift+Tab permanecem no modal e foco retorna. |
| 14 | Fato confirmado | Erros de auth têm role=alert. | Login/cadastro | round1; aplicado. | Release B corrige copy OTP. | Typegen/tsc verdes; teste leitor/DOM pendente. | Alta estática | Médio | XS | Erro é anunciado sem mover foco indevidamente. |
| 15 | Fato confirmado | Cards /v têm OG image, Twitter e VideoObject próprios, 16 posters reais e link da galeria. | Showcase/viewer | round1; aplicado, não deployado. | SEO/examples. | Typegen/tsc verdes; debugger social/build pendentes. | Alta estática | Médio | S | Cada card identifica o vídeo, asset resolve e link abre viewer. |
| 16 | Fato confirmado | signup_intent de nicho reaparece uma vez após OTP. | Nicho → auth → dashboard | round1 preservado; selected_package foi adicionado como intenção distinta. | Release B mantém as duas intenções sem checkout automático. | Typegen/tsc e E2E Playwright de pacote/OTP/reload verdes. | Alta local | Alto | XS | Nicho e pacote não se perdem nem reaplicam indevidamente. |
| 17 | Fato confirmado | Sitemap inclui blog/viewers e exclui auth; cinco rotas auth têm noindex. | Sitemap/auth | round1 preservado e ampliado em 095fe83. | Release B corrigiu canonical/datas/metadata. | Crawl Playwright das 29 rotas verde. | Alta local | Alto | XS | Sitemap/noindex não regridem. |
| 18 | Fato confirmado | Blog forma cluster com footer, canonical, Twitter, BlogPosting e interlinks; claims falsos foram corrigidos. | Blog/nichos | round1 preservado; Release B renderiza GFM e alinha datas. | Release B concluiu o hardening público local. | Build isolado e crawl dos três artigos verdes. | Alta local | Alto | XS | Links/schema resolvem e não reaparecem claims falsos. |
| 19 | Fato confirmado | JSON-LD SoftwareApplication fica somente na home. | Layout/home/viewer/blog | round1 preservado. | Release B preserva schemas por rota. | Crawl Playwright das 24 rotas indexáveis verde. | Alta local | Médio | XS | Artigo/viewer não herda SoftwareApplication global. |

### Produto, SEO, segurança e operação futura

| Marcador | Achado/recomendação | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Pacotes são públicos, incluem total/equivalências e traduzem professional público↔pro legado. | Preços/auth/checkout | 9d6eed6, aa71128 e testes de contrato/E2E. | Alta local | Alto | XS | Repetir GET e E2E no candidato; compra legada continua válida. |
| Fato confirmado | Markdown seguro, catálogo canônico, 308/canonical/metadata/datas e carregamento único de headlines foram concluídos localmente. | Público/SEO | 162d8cf, aa71128 e 095fe83. | Alta local | Alto | XS | Playwright das 29 rotas e checks SEO permanecem verdes. |
| Fato confirmado | Música usa `musicAssetId` allowlisted e caminhos de voz arbitrários foram removidos; legado só migra URLs relativas exatas. | Mídia/voz | e6225d6; resolver contido, sanitização de estado e contrato frontend/backend. | Alta local | Crítico | L | 16 casos de abuso e 101 testes focados verdes; repetir no candidato. |
| Fato confirmado | Upload é streaming, com limite antecipado, MIME, magic bytes, escrita por chunks e limpeza parcial. | Upload | e802fd6; `audio_uploads.py` e testes de clone/upload. | Alta local | Alto | M | 45 testes de upload/voz e 90 testes expandidos verdes no gate local. |
| Fato confirmado | Reset usa JTI persistido/`used_at`, consumo atômico e invalidação; cadastro exige consentimento e congela versões legais. | Auth/legal | 63169e3; migration `a4b5c6d7e8f9`, testes concorrentes em PostgreSQL. | Alta local | Alto | L | Replay e corrida falham; cadastro ausente/falso/nulo retorna 422. |
| Fato confirmado | Produção explícita restringe CORS/hosts, protege metrics por Bearer, desliga docs, aplica CSP e usa templates de rota sem UUID nos labels. | Infra | 2b94239; produção simulada e build Next isolado. | Alta local | Alto | M | 24 testes de infra/auth/metrics e build das 39 páginas verdes; configurar secrets/hosts antes do candidato. |
| Fato confirmado | Geração e rerender publicam artefato/Redis somente após CAS e commit final no banco; rollback restaura o artefato anterior. | Worker/status | `job_operations.py`, publicação preparada e testes de falha DB. | Alta local | Crítico | M | 55 testes de infraestrutura + integridade; falha DB forçada mantém Redis não-terminal e remove/restaura artefato. |
| Fato confirmado | A primeira das duas releases de auth foi implementada localmente: login/cadastro emitem cookie host-only HttpOnly/Secure em produção/SameSite=Lax e CSRF vinculado à claim; mutações por cookie exigem token e origem permitida. | Sessão | Commit 5060447; `app/auth/session.py`, `app/auth/dependencies.py`, `frontend/src/lib/session.ts` e 40 testes focais/regressivos. | Alta local | Alto | M | Build isolado verde; publicar candidato e observar `clipia_auth_transport_total`. |
| Problema | Bearer e JWT em localStorage permanecem deliberadamente durante a compatibilidade e ainda ampliam o impacto de XSS. | Sessão Release 2 | Estratégia em duas releases e telemetria implementada. | Alta | Alto | M operacional | Remover Bearer/localStorage somente após clientes por cookie estarem verdes; manter CSRF e testes de rollback. |
| Requer analytics | Retenção/exclusão financeira depende de matriz jurídica. | Privacidade | Premissa aprovada. | Alta | Crítico | L | Jurídico aprova antes de anonimizar/excluir. |
| Hipótese | Build candidato 3004 reduz indisponibilidade; proxy blue/green permanente é infraestrutura separada. | Deploy Windows | Plano operacional. | Alta | Alto | L | NEXT_DIST_DIR versionado, smoke e rollback automático. |

### Máquinas de estado e invariantes

| Marcador | Domínio/regra | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Estado implementado hoje: `pending→approved/refunded`, com `refunded` terminal para crédito; provider/evento únicos e snapshot congelado já existem. | Pagamentos | app/payments/service.py e commits cc4d476/5ac23d6. | Alta local | Crítico | M | Repetição e ordem de webhook mantêm delta único enquanto a compatibilidade é migrada. |
| Problema | O contrato público exigido ainda é `pending→paid/refunded/void`, com `paid→refunded`; o código usa `approved` e não implementa `void`. | Pagamentos/API | Divergência entre app/payments/service.py e o contrato desta auditoria. | Alta | Crítico | M | Adapter/migration preserva compras históricas, APIs publicam somente os quatro estados canônicos e testes cobrem `approved→paid`, `void` e todas as ordens. |
| Fato confirmado | Geração: queued→dispatched→processing→finalizing→editable, ou failed/cancelled; cancel só antes de finalizing/editable. | Jobs | 1C1. | Alta local | Crítico | M | Uma operação, custo e dispatch/compensation; DB antes de terminal Redis. |
| Fato confirmado | Rerender: idle→debited→dispatched→running→completed/failed/cancelled; UUID atual em toda mutação e reconciliação 1C2 aprovada localmente. | Rerender/watchdog | 1C1 + e885021. | Alta local | Crítico | M | Operação stale não altera saldo/status; smoke multiprocessos antes do deploy. |
| Fato confirmado | Toda mutação de `User.credits` é capturada por trigger append-only; fluxos financeiros principais anexam origem, referências e idempotency key na mesma transação, e caminhos legados aparecem como `unclassified` em vez de sumirem. | Créditos | 3643178; `credit_ledger.py`, migration b5c6d7e8f9a0 e testes de projeção. | Alta local | Crítico | S operacional | Reconciliação diária permanece zero; qualquer divergência alerta e mantém `enforce` bloqueado. |
| Problema | Compra refunded/void nunca credita; job entregue nunca cancela/refunda como ativo. | Pagamento/jobs | 1B/1C1. | Alta local | Crítico | M | Testes concorrentes em PostgreSQL. |
| Fato confirmado | Falha antes da aceitação do broker compensa; falha ambígua após aceitação é revalidada pelo outbox e não autoriza refund cego. | Dispatch | e885021 e revisão adversarial 1C2. | Alta local | Crítico | M | Broker real confirma replay/claim/heartbeat sem débito órfão. |
| Fato confirmado | `User.credits` continua projeção autoritativa durante ledger `shadow`; Redis é cache/telemetria, nunca autoridade financeira, e nenhuma divergência é auto-reparada. | Ledger/status | 3643178; reconciliador append-only e gate de startup. | Alta local | Crítico | S operacional | Sete dias zero antes de `enforce`; rollback mantém a projeção e o modo padrão segue `shadow`. |

## J. Plano de analytics

### Contrato, privacidade e acesso

| Marcador | Decisão/requisito | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Tabela PostgreSQL append-only com event_id UUIDv4, schema_version, occurred_at/received_at, anonymous_session_id, user opcional server-derived, page, attribution, device_class, properties tipadas e payload hash foi implementada. | Analytics | Commit acb647c; migration f3a4b5c6d7e8, teste PostgreSQL concorrente e triggers de UPDATE/DELETE. | Alta local | Alto | S | Repetir migration no candidato; manter inserts idempotentes e mutações rejeitadas. |
| Fato confirmado | POST /api/v1/analytics/events aceita auth opcional estrita, 1–20 eventos/64 KB, rate limit 30/min e rejeição por contrato; a flag é false por padrão. | API | app/analytics/routes.py e tests/test_analytics_ingestion.py. | Alta local | Alto | XS | Lote excessivo 413; replay idêntico zero-delta; conflito 409; campos desconhecidos 422. |
| Fato confirmado | O schema aceita somente cinco UTMs normalizadas de até 100 caracteres e deriva acquisition_source no servidor como direct/organic/referral/social/email/paid/campaign. | Aquisição | app/analytics/schemas.py, app/analytics/service.py e testes de armazenamento. | Alta local | Alto | XS | Não aceitar source arbitrário nem chave/valor fora do contrato. |
| Fato confirmado | O endpoint rejeita PII direta e campos server-only; user_id é derivado da autenticação, IP/UA não são persistidos e o access log omite identificadores nessa rota. Pseudônimos continuam sendo dados pessoais. | Privacidade | Schemas extra=forbid, model sem colunas de rede e app/observability.py; testes de rejeição. | Alta local | Crítico | M | Antes de habilitar: aprovar inventário, retenção, acesso, exclusão e texto de Privacidade. |
| Hipótese | anonymous_session_id aleatório vive em sessionStorage; vínculo pós-cadastro é server-side, sem cookie de marketing/fingerprint. | Landing → auth | Plano. | Alta | Alto | M | Mesma aba preserva; nova sessão muda; cliente não envia user_id. |
| Problema | Dashboard administrativo exige RBAC de admin, autenticação forte, consultas agregadas e audit log; usuários comuns não acessam eventos brutos. | Admin analytics | Requisito de segurança. | Alta | Crítico | M | 401/403 para não-admin; teste de autorização e log de acesso/export. |
| Fato confirmado | Agregados de jobs, créditos, refunds e compras foram corrigidos para usar estados financeiros canônicos e snapshots duráveis; ainda não há baseline de produção. | Dashboard | Commit e64d217; tests/test_admin_financial_baseline.py e caso PostgreSQL real. | Alta local | Crítico | S | Conferir no candidato que pending não vira receita e que operações/refunds não duplicam totais. |

### Allowlist estrita por evento

| Evento | Marcador | Autoridade | Properties allowlisted por evento | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|---|
| Envelope comum | Fato confirmado | Cliente envia somente event_id UUIDv4, schema_version, occurred_at, anonymous_session_id, page, device_class e UTMs permitidas; servidor deriva received_at, user_id e não persiste dados de rede. | event_id:UUIDv4; schema_version:int=1; occurred_at:datetime com janela; anonymous_session_id:UUIDv4; page:enum; device_class:desktop/mobile/tablet/unknown; cinco UTMs. | Os 13 eventos cliente implementados | Commit acb647c e teste do catálogo completo em um batch. | Alta local | Crítico | XS | Campo comum extra é 422; user_id/IP/UA bruto do cliente são rejeitados; emissão no frontend permanece pendente. |
| landing_viewed | Hipótese | Cliente | landing_variant:enum; niche:enum/null; cinco UTMs; referrer_domain:string≤100 | Landing/nichos | Plano | Alta | Alto | S | Sem URL/query/texto livre; um por page view. |
| hero_cta_clicked | Hipótese | Cliente | placement:hero/nav/final; cta_variant:enum; selected_package:starter/popular/professional/null | Landing → auth | Plano | Alta | Alto | XS | Pacote público válido e exposição correlacionável. |
| example_played | Hipótese | Cliente | example_id:ID de catálogo; niche:enum; placement:enum | Exemplos | Catálogo | Alta | Médio | XS | ID inexistente é rejeitado. |
| example_completed | Hipótese | Cliente | example_id:ID de catálogo; completion_bucket:25/50/75/100 | Exemplos | Plano | Alta | Médio | XS | Bucket enum, sem timestamp por frame. |
| pricing_viewed | Hipótese | Cliente | placement:landing/credits; pricing_variant:enum | Preços | Plano | Alta | Alto | XS | Um por exposição visível. |
| pricing_package_selected | Hipótese | Cliente | package:starter/popular/professional; placement:enum | Preços → auth | Plano | Alta | Alto | XS | Nunca aceitar pro do cliente público. |
| support_opened | Hipótese | Cliente | placement:footer/faq/app/error; reason_code:enum/null | Suporte | Plano | Média | Médio | XS | Sem mensagem livre. |
| signup_started | Hipótese | Cliente | selected_package:enum/null; source_page:enum | Auth/register | Plano | Alta | Alto | XS | Sem e-mail/nome. |
| signup_completed | Problema | Servidor | selected_package:enum/null; result:success; signup_id:UUID server-derived | Auth/register | Evento autoritativo requerido, ainda não instrumentado. | Alta | Alto | S | Só após commit do usuário; idempotente. |
| email_verification_sent | Problema | Servidor | verification_attempt:int; delivery_result:accepted/failed | Auth/OTP | Evento autoritativo requerido, ainda não instrumentado. | Alta | Médio | S | Sem e-mail/domínio bruto. |
| email_verified | Problema | Servidor | credits_granted:int; selected_package:enum/null; verification_id:UUID | Auth/OTP | CAS existe no commit 8b55829; evento analytics ainda não. | Alta | Alto | S | Uma vez por CAS; user_id derivado. |
| onboarding_started | Hipótese | Cliente | entry:post_verify/dashboard; variant:enum | Onboarding | Plano | Média | Médio | XS | Só após exposição. |
| goal_selected | Hipótese | Cliente | goal:faceless/education/sales/news/other_predefined | Onboarding | Plano | Média | Médio | XS | Enum; sem texto livre. |
| niche_selected | Hipótese | Cliente | niche:enum de catálogo | Onboarding | Catálogo | Média | Médio | XS | Nicho allowlisted. |
| onboarding_completed | Hipótese | Cliente | last_step:enum; variant:enum | Onboarding | Plano | Média | Alto | XS | Ordem de etapas validada. |
| onboarding_skipped | Hipótese | Cliente | step:enum; variant:enum | Onboarding | Plano | Média | Médio | XS | Motivo livre proibido. |
| video_creation_started | Hipótese | Cliente | template:enum; mode:enum; duration_bucket:enum | Dashboard | Plano | Média | Alto | XS | Sem tema/roteiro. |
| video_template_selected | Hipótese | Cliente | template:enum; mode:enum | Dashboard | Templates | Alta | Médio | XS | Template precisa existir. |
| video_generation_requested | Problema | Servidor | job_id:UUID; operation_id:UUID; template:enum; mode:enum; duration_bucket:enum; credit_cost:int | Generate | Operação Release A existe; evento analytics ainda não. | Alta | Crítico | M | Emitir após débito+job commit; um por operação. |
| video_generation_completed | Problema | Servidor | job_id; operation_id; latency_ms:int; mode:enum | Worker | Estado Release A existe; evento analytics ainda não. | Alta | Alto | M | Emitir somente após DB editable commit. |
| video_generation_failed | Problema | Servidor | job_id; operation_id; failure_code:enum; compensated:bool; latency_ms:int | Worker | Estado Release A existe; evento analytics ainda não. | Alta | Crítico | M | failure_code allowlisted; estado reconciliável. |
| video_editor_opened | Hipótese | Cliente | job_id:UUID; entry:dashboard/email/return | Editor | Plano | Média | Alto | XS | Job ownership validado no backend de ingestão. |
| video_export_requested | Problema | Servidor | job_id:UUID; operation_id:UUID; credit_cost:int | Render API | Autoridade definida; evento analytics ainda não implementado. | Alta | Crítico | M | Emitir após operação aceita/debitada, não no clique cliente. |
| video_exported | Problema | Servidor | job_id; operation_id; latency_ms:int | Worker/export | Estado Release A existe; evento analytics ainda não. | Alta | Alto | M | Só após persistência final no DB. |
| video_export_failed | Problema | Servidor | job_id; operation_id; failure_code:enum; compensated:bool | Worker/export | Estado Release A existe; evento analytics ainda não. | Alta | Crítico | M | Terminal corresponde à mesma operação. |
| credits_viewed | Hipótese | Cliente | balance_bucket:zero/low/medium/high; placement:enum | Créditos | Plano | Média | Médio | XS | Nunca enviar saldo exato pelo cliente. |
| credits_low | Hipótese | Cliente | balance_bucket:zero/low; required_bucket:enum; placement:enum | Criação/editor | Experimento K6 | Média | Alto | XS | Dedupe por sessão/ação. |
| checkout_started | Problema | Servidor | purchase_id:UUID; provider:stripe/mercadopago; package:enum; amount_brl_cents:int; currency:BRL | Checkout | Compra 1A/1B existe; evento analytics ainda não. | Alta | Crítico | M | Emitir após criação da compra/sessão validada; nunca pelo cliente. |
| payment_pending | Problema | Servidor | purchase_id; provider:enum; package:enum; amount_brl_cents:int; currency:BRL | Webhook | Estado 1B existe; evento analytics ainda não. | Alta | Alto | S | Idempotency por evento/provedor. |
| payment_completed | Problema | Servidor | purchase_id; provider:enum; package:enum; amount_brl_cents:int; currency:BRL | Webhook | Estado 1B existe; evento analytics ainda não. | Alta | Crítico | M | Única fonte de receita; paid commitado. |
| payment_failed | Problema | Servidor | purchase_id; provider:enum; failure_code:enum; terminal:bool | Webhook | Estado 1B existe; evento analytics ainda não. | Alta | Alto | S | Não converter paid/refunded em falha. |
| payment_refunded | Problema | Servidor | purchase_id; provider:enum; amount_brl_cents:int; currency:BRL; refund_scope:full/partial | Webhook | Estado refunded 1B existe; evento analytics ainda não. | Alta | Crítico | M | Emitir uma vez após estado/refund commitados; reduzir receita uma vez. |
| credits_added | Problema | Servidor | purchase_id/null; credit_delta:int; reason:purchase/welcome/admin; operation_id:null | Créditos | Mutação 1A/1B existe; evento analytics ainda não. | Alta | Crítico | M | Idempotency key única; beta usa motivo separado no domínio, não propriedade livre. |
| credits_refunded | Problema | Servidor | purchase_id/null; operation_id:UUID/null; credit_delta:int; reason:provider_refund/operation_compensation | Créditos | Refund Release A existe; evento analytics ainda não. | Alta | Crítico | M | Delta uma vez e ligado à origem. |
| second_video_generated | Problema | Servidor | job_id; operation_id; days_since_signup:int; cohort_week:string ISO | Retenção | Evento requerido, ainda não instrumentado. | Alta | Alto | S | Uma vez por usuário quando segunda geração completa. |
| user_returned | Hipótese | Cliente | entry:email/direct/dashboard; days_since_last_value_bucket:enum | Retenção | Plano | Média | Médio | XS | Sem referrer URL completa. |
| referral_shared | Hipótese | Cliente | channel:whatsapp/copy_link/other; placement:enum | Referral | Experimento K9 | Baixa | Médio | XS | Sem contato do destinatário. |
| feedback_submitted | Hipótese | Cliente | score:1/2/3/4/5; context:first_export/general | Feedback | Plano | Média | Médio | XS | Texto livre fora deste evento/contrato. |

### Dashboard e coortes

| Marcador | Dashboard/recomendação | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Requer analytics | Funil visita → CTA → cadastro → verificação → geração → exportação → checkout → pagamento → segundo vídeo. | Admin | Objetivo central. | Alta | Alto | M | Usuários/sessões, conversão e tempo entre etapas. |
| Requer analytics | Coortes por semana, origem, nicho e device; first-touch e last-non-direct definidos. | Admin aquisição/retenção | Baseline ausente. | Alta | Alto | M | Timezone e janela documentados. |
| Requer analytics | Receita/COGS reconcilia paid/refunded/void, ticket, ARPPU, delta e fatura. | Admin financeiro | Agregados atuais incorretos. | Alta | Crítico | L | Sem pending como receita e sem dupla contagem. |
| Problema | Todo dashboard e export requer role admin; dados brutos ficam restritos e acesso é auditado. | Admin/RBAC | Requisito de segurança. | Alta | Crítico | M | Testes 401/403 e audit log. |

## K. Dez experimentos

| # | Marcador | Hipótese/alteração | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Métrica/guardrails | Critério de aceite |
|---:|---|---|---|---|---|---|---|---|---|
| Regra | Fato confirmado | Executar um por vez; iniciar só com 80% de poder em até 6 semanas, alfa/MDE definidos; senão usar qualitativo/coortes sem claim causal. | Experimentação | Plano aprovado. | Alta | Alto | S | Guardrails por teste. | Pré-registro e exposição idempotente. |
| 1 | Hipótese | CTA genérico vs Escolher pacote. | Preços → auth | Intenção perdida. | Média | Alto | S | preço→cadastro verificado; auth/refund. | Pacote persiste e lift pré-definido. |
| 2 | Hipótese | Exemplos após hero vs posição atual. | Landing | Prova pode reduzir ceticismo. | Média | Alto | M | CTA→cadastro; LCP/play error. | Lift sem piorar LCP móvel. |
| 3 | Hipótese | Créditos puros vs equivalências. | Preços | Crédito abstrato. | Alta | Alto | S | pacote→checkout; ticket/refund. | Checkout melhora sem piorar guardrails. |
| 4 | Hipótese | Primeiro projeto preenchido vs vazio. | Onboarding | Tela vazia possível. | Média | Alto | L | verificado→geração; falha/cancel. | Conclusão aumenta sem arrependimento. |
| 5 | Hipótese | Recomendação pós-exportação vs nenhuma. | Resultado → preços | Venda após valor. | Média | Alto | M | export→paid; refund/feedback. | Compra cresce sem piorar refund. |
| 6 | Hipótese | Alerta de saldo baixo vs erro 402. | Criação/editor | Momento contextual. | Média | Médio | S | checkout; abandono/suporte. | Compra cresce sem derrubar criação. |
| 7 | Hipótese | Variação do e-mail pronto. | E-mail → editor | Feature existe. | Média | Alto | M | conclusão→export; bounce/duplicata. | Export cresce sem complaint. |
| 8 | Hipótese | Personalização por nicho vs genérico. | Nicho/onboarding | signup_intent existe. | Média | Alto | M | cadastro→geração; qualidade/suporte. | Apenas nichos com amostra consistente. |
| 9 | Hipótese | Referral após segunda exportação. | Resultado/referral | Momento de satisfação não provado. | Baixa | Médio | M | share→signup; spam/fraude. | Signup incremental e fraude controlada. |
| 10 | Hipótese | Ordem F vs ordem atual. | Landing inteira | Reordenação ampla. | Média | Alto | M | visita→cadastro; LCP/preço/bounce. | Último teste, copy/CTA congelados. |

## L. Backlog P0–P3

| ID | Prioridade | Marcador/estado | Tarefa | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|---|
| FIN-01 | P0 | Fato confirmado | Operações duráveis/cancel/refund concluídas localmente. | Jobs | 1C1 commits/testes. | Alta local | Crítico | M | PostgreSQL/broker/migration gates. |
| FIN-02 | P0 | Fato confirmado | Eventos de pagamento/snapshot/saldo SQL e recovery concluídos localmente. | Webhooks | 1A/1B + bf2ac41–95f4ab7; 161 locais + 12 PostgreSQL. | Alta local | Crítico | M | Provider test mode e concorrência multiprocessos. |
| OPS-01 | P0 | Fato confirmado | Compensation/reconciler/watchdog corrigidos em e885021. | Dispatch | 137 testes, Ruff/pre-commit, PostgreSQL 16 e revisão adversarial. | Alta local | Crítico | M | Broker/provider test mode, multiprocessos, backup e smoke externo. |
| REL-01 | P0 | Fato confirmado | CI .[dev]/timeout/typegen, readiness 202 e health provenance concluídos localmente; remoto pendente. | Release | ba03321 e 10 testes. | Alta local | Alto | S | CI remoto e smoke candidato. |
| REL-02 | P0 | Problema | Backup, migrations no candidato, fixtures e smoke ainda pendem. | Release A | Limitações dos gates. | Alta | Crítico | M | Sem ação real; rollback pronto. |
| CRO-01 | P1 | Fato confirmado | 2 créditos novos e +18 admin beta implementados localmente. | Oferta/auth | 9d6eed6 e testes concorrentes. | Alta local | Alto | XS | Antigos intactos; motivo auditável. |
| CRO-02 | P1 | Fato confirmado | Pacotes públicos/equivalências implementados. | Preços | 9d6eed6 e GET público testado. | Alta local | Alto | XS | total_credits e equivalências calculadas com custos 1/2/0,5/5/30. |
| CRO-03 | P1 | Fato confirmado | `professional` público e compatibilidade `pro` persistem por cadastro/OTP/checkout. | Auth→checkout | 9d6eed6, aa71128 e testes backend/Playwright. | Alta local | Alto | XS | Repetir E2E no candidato sem checkout automático. |
| UX-01 | P1 | Fato confirmado | Causa de 426 px removida. | Mobile | 162d8cf e matriz 095fe83. | Alta local | Alto | XS | Zero overflow 320/390/393. |
| UX-02 | P1 | Fato confirmado | Catálogo/fallback de exemplos implementado nos sete nichos. | Nichos | 162d8cf e 095fe83. | Alta local | Médio | XS | Zero grade vazia. |
| SEO-01 | P1 | Fato confirmado | Markdown GFM seguro implementado nos três artigos. | Blog | 162d8cf e 095fe83. | Alta local | Médio | XS | Sem literal/raw HTML. |
| SEO-02 | P1 | Fato confirmado | 308, canonical, metadata, datas e sitemap de viewers implementados. | Público | 162d8cf e 095fe83. | Alta local | Alto | XS | 100% canonical apex. |
| COPY-01 | P1 | Fato confirmado | “Enviar código”, uma busca de headline e “Pix e cartão” corrigidos fora do texto jurídico. | Auth/landing | aa71128 e Playwright. | Alta local | Médio | XS | Legal permanece sem alteração até redline. |
| ANA-01 | P1 | Fato confirmado | Tabela/endpoint first-party append-only atrás de flag foram implementados localmente. | Analytics | acb647c, 46 testes locais + 3 PostgreSQL. | Alta local | Alto | XS | Flag off até Privacidade; allowlist de 13 eventos, 20/64 KB, rate limit e replay zero-delta. |
| ANA-02 | P1 | Requer analytics | Eventos servidor/cliente, RBAC, dashboard/coortes. | Funil/admin | Seção J. | Alta | Alto | L | Sem PII direta; pseudônimos protegidos; funil reconciliado. |
| ONB-01 | P1 | Hipótese | Onboarding preenchido e recomendação pós-valor, somente pós-baseline. | Auth→export | Seção H. | Média | Alto | L | Teste isolado após 14 dias. |
| SEC-01 | P2 | Fato confirmado | IDs opacos, contenção de path e upload streaming foram implementados localmente. | Mídia/upload | e6225d6, e802fd6 e Seção I. | Alta local | Crítico | L | Payloads maliciosos rejeitados; gates focados verdes. |
| SEC-02 | P2 | Fato confirmado | Reset one-time e consentimento versionado foram implementados localmente. | Auth/legal | 63169e3 e Seção I. | Alta local | Alto | L | Concorrência PostgreSQL e regressões auth verdes. |
| SEC-03 | P2 | Fato confirmado | Hardening de CORS/hosts/metrics/docs/CSP por ambiente foi implementado localmente. | Infra | 2b94239 e Seção I. | Alta local | Alto | M | Produção simulada bloqueia superfície e cardinalidade indevidas. |
| LED-01 | P2 | Fato confirmado | Ledger append-only em `shadow` implementado com delta assinado, origem, referências, idempotência e `balance_after`. | Créditos | 3643178 e b5c6d7e8f9a0. | Alta local | Crítico | XS operacional | Triggers cobrem toda alteração; UPDATE/DELETE do ledger falham. |
| LED-02 | P2 | Fato confirmado | Backfill e reconciliação diária implementados; `enforce` permanece deliberadamente bloqueado até sete dias zero. | Créditos | 3643178; Celery 05:00 UTC e gate de startup. | Alta local | Crítico | S operacional | Sete dias consecutivos limpos no ambiente publicado; rollback mantém `User.credits`. |
| AUTH-01 | P2 | Fato confirmado | Release 1 de cookie HttpOnly + CSRF com Bearer compatível. | Sessão | Commit 5060447, testes e métrica por transporte. | Alta local | Alto | M | Cookie seguro em produção, mutações sem CSRF 403 e Bearer sem regressão. |
| AUTH-02 | P2 | Problema | Remover Bearer e token de localStorage na Release 2. | Sessão | Release 1 mantém compatibilidade de propósito. | Alta | Alto | M operacional | Telemetria cookie verde no candidato, rollback validado e zero cliente ativo dependente de Bearer. |
| DEP-01 | P2 | Hipótese | NEXT_DIST_DIR candidato 3004→3003. | Deploy | Plano. | Alta | Alto | L | Candidato falho não afeta ativo. |
| EXP-01 | P2 | Hipótese | K1–K10 um por vez. | CRO | Seção K. | Média | Alto | Contínuo | Poder ou qualitativo, sem falso vencedor. |
| MON-01 | P3 | Requer analytics | Reavaliar assinatura/híbrido. | Monetização | Seções E/N. | Baixa | Alto | XL | Gates objetivos satisfeitos. |
| AGY-01 | P3 | Hipótese | Piloto de agência antes de produto dedicado. | B2B | Modelo D. | Baixa | Médio | L | 5 entrevistas, 3 propostas, 1 piloto pago. |

## M. Execução 24h/7d/30d/90d

| Horizonte/gate | Marcador | Entrega/ordem | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|
| 24 h | Fato confirmado | 1A/1B/1C1/1C2 e recovery de checkout estão corrigidos e revisados localmente; a suíte completa final e gates externos ainda precisam rodar. | Financeiro/release | Commits 8b55829–95f4ab7 e e885021. | Alta local | Crítico | M | Review limpa, suíte completa final, Ruff tocado e gates externos. |
| 24 h | Problema | Gate 1: backup verificado e migrations expansivas no candidato. | PostgreSQL | Publicação pendente. | Alta | Crítico | M | Restore testado e rollback documentado. |
| 24 h | Problema | Gate 2: backend completo, concorrência PostgreSQL, fixtures assinadas/provider test mode. | Backend | 525 local não basta. | Alta | Crítico | M | Zero cobrança, geração paga ou envio real. |
| 24 h | Fato confirmado | Gate 3 local: typegen, tsc, build NEXT_DIST_DIR isolado e Playwright passaram; precisa repetir no SHA candidato. | Frontend | 26 Playwright verdes, matriz 29×4, typegen e tsc em 13/07/2026. | Alta local | Alto | S | Repetir sem alteração no SHA candidato. |
| 24 h | Problema | Gate 4: candidato 3004 com health, homepage, login, chunks, API, worker/fila e smoke; só então 3003. | Deploy | Plano Windows. | Alta | Crítico | M | Falha não toca ativo; anterior retido. |
| 24 h | Problema | Gate 5 futuro: health/smoke externo falhou → rollback automático; proxy blue/green permanente fica fora. | Deploy/rollback | Decisão aprovada, implementação/publicação pendentes. | Alta | Crítico | S | Rollback ensaiado e mensurável. |
| 7 dias | Fato confirmado | Release B implementada localmente: 2 créditos, +18 admin, pacotes/equivalências, professional↔pro, mobile, exemplos, Markdown, canonical/datas e copy. | Público/CRO/SEO | 162d8cf, 9d6eed6, aa71128 e 095fe83. | Alta local | Alto | S | 29 rotas em desktop + 320/390/393, zero regressões no candidato. |
| 7 dias | Fato confirmado | Preservar hero, identidade, preços, pré-pago, hamburger e matriz dos 19; legal só após redline. | Público/legal | Premissas e seção I. | Alta | Alto | S | Diff limitado e aprovação jurídica. |
| 30 dias | Requer analytics | Após Privacidade, publicar a base já implementada, instrumentar eventos cliente/servidor, criar RBAC/dashboard/coortes e coletar 14 dias antes de onboarding/experimento. | Funil | acb647c, e64d217 e H/J/K. | Alta | Alto | XL | Flag off antes da aprovação; sem PII direta; funil reconciliado. |
| 30 dias | Requer analytics | Instrumentar COGS real por operação/fatura. | Economia | E. | Alta | Crítico | L | p50/p95 reconciliados; preço não muda sem dado. |
| 90 dias | Problema | Após concluir localmente assets/upload/reset/consentimento/infra, DB-first, ledger `shadow` e auth Release 1, restam sete dias zero do ledger, remoção de Bearer/localStorage e deploy versionado. | Segurança/operação | e6225d6, e802fd6, 63169e3, 2b94239, 3643178 e I/L. | Alta | Crítico | L | Repetir gates no candidato, obter sete dias de ledger zero e telemetria cookie verde antes da Release 2. |
| 90 dias | Requer analytics | Avaliar, não lançar, assinatura/agência somente pelos gates N. | Monetização | E/N. | Alta | Alto | S | Nenhuma recorrência automática. |

## N. Métricas e metas

| Marcador | Métrica/decisão | Página/fluxo | Baseline e evidência | Meta/período | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|---|
| Problema | Criação, perda ou duplicação de créditos. | Financeiro | Testes concorrentes + reconciliação. | Zero em cada CI e diário. | Alta | Crítico | L | Nenhum delta sem origem/idempotency. |
| Problema | Operação debitada sem dispatch/compensation. | Jobs | Aging de operações. | Zero contínuo. | Alta | Crítico | L | Toda operação fecha, despacha ou compensa. |
| Fato confirmado | Overflow horizontal e grade vazia estão zerados no candidato local. | Mobile/nichos | 29 rotas × 4 viewports e catálogo dos sete nichos. | Zero por release. | Alta local | Alto | M | 320/390/393 e fallback acionável no smoke candidato. |
| Problema | Canonical apex. | SEO | Crawl indexável. | 100% por release. | Alta | Alto | M | Um canonical apex; www 308. |
| Problema | A ingestão já rejeita PII direta e replay duplicado; acesso administrativo aos eventos/dashboard ainda precisa de RBAC e audit log. | Analytics/admin | acb647c prova payload estrito e event_id idempotente; dashboard ainda pendente. | Zero contínuo. | Alta | Crítico | M | Campos proibidos 422; replay zero-delta; não-admin 403 quando o dashboard existir. |
| Requer analytics | CTA→cadastro. | Landing/auth | 14 dias por origem/device. | +20% relativo em 4–6 semanas. | Média | Alto | M | 80% poder ou sem claim causal. |
| Requer analytics | Verificado→primeira geração. | Onboarding | 14 dias. | +25% relativo em 4–6 semanas. | Média | Alto | L | Falha/cancel como guardrails. |
| Requer analytics | Primeira exportação→pagamento. | Resultado/preços | 14 dias. | +15% relativo em 4–6 semanas. | Média | Alto | M | Receita, refund e ticket como guardrails. |
| Requer analytics | Recompra em 30 dias. | Créditos | Duas coortes maduras. | +15% relativo; gate de assinatura ≥25% absoluto. | Média | Alto | L | Paid líquido de refund. |
| Requer analytics | Tempo/falha até primeiro vídeo por modo. | Operação | p50/p75/p95 server-side. | Definir após baseline; regressão zero na release. | Alta | Crítico | M | failure_code allowlisted e operação reconciliada. |
| Requer analytics | Ticket, ARPPU e margem por modo/pacote. | Receita/economia | paid líquido + COGS/fatura. | Não fixar antes do baseline; margem ≥65% apenas como gate. | Alta | Crítico | L | Fatura e ledger/eventos convergem. |
| Requer analytics | Estabilidade de COGS p95. | Economia | Série por modo/model version. | ±15% em duas coortes mensais. | Alta | Crítico | L | Troca de provider/model segmenta ou reinicia janela. |
| Requer analytics | Retenção 7/30/90. | Retenção | Coortes por signup/primeiro valor. | Definir após duas coortes maduras. | Alta | Alto | L | Ativo = geração/exportação, não login vazio. |
| Fato confirmado | Gate para apenas reavaliar assinatura: duas coortes mensais com ≥50 pagantes cada, recompra 30d ≥25%, margem ≥65% e COGS p95 ±15%; falhar mantém pré-pago. | Monetização | Decisão aprovada; métricas ainda ausentes. | Aplicar somente após coortes maduras. | Alta para a regra | Alto | S | Todos os critérios satisfeitos simultaneamente; nenhum lançamento automático. |

### Rastreabilidade e limites finais

| Marcador | Limite/fonte | Página/fluxo | Evidência | Confiança | Impacto | Esforço | Critério de aceite |
|---|---|---|---|---|---|---|---|
| Fato confirmado | Fontes internas: código/testes desta branch, BACKLOG-AUDITORIA-2026-07-11.md, INSIGHTS-GPT56-2026-07-12.md e round1 rastreado em docs/superpowers/reviews. | Auditoria | Arquivos versionados no repositório. | Alta | Alto | — | Cada claim técnico aponta para commit, arquivo ou teste rastreado. |
| Fato confirmado | Benchmark externo restrito às quatro URLs oficiais da seção E. | Benchmark | CapCut, VEED, InVideo e Pictory. | Alta | Médio | — | Nenhum preço concorrente vira input econômico do ClipIA. |
| Requer analytics | Tráfego, conversão, faturamento, recompra, ARPPU, retenção e COGS real não foram fornecidos reconciliados. | Negócio | Ausência de dados autoritativos. | Alta | Crítico | L | Coletar conforme J antes de afirmar resultado. |
| Problema | Testes locais/fakes não equivalem a produção. | Release | 525 testes locais e dez focais ba03321. | Alta | Crítico | M | Repetir no SHA final, CI remoto e stack candidata. |
