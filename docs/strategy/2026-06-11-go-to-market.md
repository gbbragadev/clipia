# ClipIA — Go-to-Market & Monetização (v1)

Data: 2026-06-11. Autor: Gui + Claude. Status: rascunho para decisão.
Premissa: produto tecnicamente pronto (pipeline + editor fiel via Remotion + billing MercadoPago vivos), zero usuários externos até hoje. Objetivo do dono: validar como negócio para eventualmente sair do emprego.

---

## 1. Produto em uma frase

**"Do tema ao Short pronto em minutos, em português."** Roteiro (IA), narração pt-BR, legendas animadas, mídia e edição — com um editor de verdade onde o que você vê é o que exporta.

## 2. Público-alvo (ICP) — em ordem de foco

1. **Criadores de canais "dark"/faceless pt-BR** (curiosidades, histórias, fatos, dicas). Dor: volume — precisam de 1-3 Shorts/dia e a edição é o gargalo. Já pagam por ferramentas/editores. **Foco inicial: este nicho.** É também o nicho que o template novelinha_historica e o stock_narration servem melhor hoje.
2. Infoprodutores/afiliados que precisam de Reels diários para audiência.
3. Social media / pequenas agências que atendem PMEs.

Por que pt-BR primeiro: os concorrentes fortes (InVideo, Pictory, OpusClip) são em inglês, com roteiro/voz pt-BR de segunda classe e preço em dólar. ClipIA nasce pt-BR nativo (vozes, roteiro coloquial, preço em R$, MercadoPago/Pix).

## 3. Posicionamento

- **Categoria:** gerador automático de vídeos curtos com editor.
- **Diferenciais defensáveis hoje:** (a) pt-BR nativo de ponta a ponta; (b) editor fiel — overlays, legendas animadas e estilos que realmente saem no MP4 (pós-Fase 2); (c) preço em reais com Pix/cartão via MercadoPago; (d) 2 vídeos grátis sem cartão.
- **Mensagem da home:** já existe ("Crie vídeos que ninguém pula"). Sustentar com a prova: showcase de vídeos reais (Fase 4).

## 4. Monetização

### 4.1 Modelo atual (manter no lançamento)
Créditos pré-pagos (sem assinatura): Starter 10/R$19,90 (R$1,99/cr) · Popular 30/R$49,90 (R$1,66/cr) · Pro 100/R$129,90 (R$1,30/cr). Custo em créditos por vídeo: 1 (voz Edge), 2 (ElevenLabs), 5 (imagens IA/novelinha).

### 4.2 Economia unitária (estimativas — MEDIR no beta)
- Vídeo stock+Edge: custo direto ≈ centavos (DeepSeek ~R$0,02-0,05; Edge TTS grátis; Groq free tier; Pexels grátis). **Margem ~100%.** ✅
- Vídeo ElevenLabs: + custo de caracteres ElevenLabs (depende do plano contratado). Medir R$/vídeo real.
- Vídeo novelinha (gpt-image, 6 imagens medium): custo OpenAI estimado R$2-6/vídeo. A 5 créditos, receita R$6,50-9,95 → **margem apertada no pacote Pro; medir e, se preciso, subir para 6-7 créditos ou reduzir qualidade default.**
- Infra: PC próprio → custo marginal ~zero, mas worker solo = **1 vídeo por vez (~3 min)** → teto ~400-450 vídeos/dia. Suficiente para validar; gargalo conhecido para escala.

### 4.3 Evolução (somente após validar retenção)
Assinatura mensal (ex.: R$49/mês ≈ 40 créditos + fila prioritária + vozes premium) quando houver ≥20 compradores repetidos. Não lançar assinatura antes de provar uso recorrente — créditos medem disposição a pagar com menos atrito.

## 5. Canais (CAC ≈ zero primeiro)

1. **Dogfooding — o produto é o marketing.** Canal próprio (TikTok + YT Shorts + Reels) "feito 100% no ClipIA", 1 vídeo/dia gerado pelo pipeline (o batch da Fase 4 já automatiza). Watermark `clipia.com.br` (default ON) em todo vídeo distribui a marca. Custo: ~10 min/dia de curadoria.
2. **Comunidades pt-BR** de criadores faceless/dark channels (grupos de Telegram/Discord/WhatsApp, subreddits BR, comentários de vídeos "como criar canal dark"). Oferecer acesso beta + créditos.
3. **Programa de referral** (JÁ EXISTE no produto: referral_code + UTM tracking) — dar créditos por indicação convertida.
4. Mais tarde: parceria com 2-3 micro-influencers do nicho "renda com canais dark" (afiliação com créditos/comissão); SEO via blog (já existem 3 posts).

## 6. Plano de lançamento

### Fase A — Beta fechado (semanas 1-3)
- Pré-requisito técnico: Fases 3+4 entregues; e-mail SMTP configurado (verificação de conta) — **checar SMTP_* em produção**.
- Convidar 10-20 criadores do nicho (das comunidades) com 10 créditos cada.
- Metas: ≥60% geram o 1º vídeo; ≥5 dão feedback estruturado; coletar 3+ depoimentos reais (vão para a landing no lugar de social proof inventado).
- Instrumentar: funil signup→1º vídeo→export→compra (admin dashboard já mostra; conferir eventos).

### Fase B — Lançamento público (semanas 4-6)
- Ligar `NEXT_PUBLIC_PUBLIC_SIGNUP=true` (+ rebuild).
- Canal dogfooding rodando há ≥2 semanas (corpo de prova).
- Post de lançamento nas comunidades + referral ativo.
- Meta de validação do negócio (90 dias): **≥30 pagantes** e **≥10 compradores repetidos**. Se atingir → investir (infra dedicada, assinatura). Se não → diagnosticar funil antes de mais features.

## 7. Métricas norte

| Métrica | Meta beta | Meta 90d |
|---|---|---|
| Signup → 1º vídeo gerado | ≥60% | ≥50% |
| 1º vídeo → export/download | ≥70% | ≥70% |
| Free → pagante | — | ≥8% |
| Compradores repetidos | — | ≥10 |
| Custo direto médio/vídeo | medido | < 30% da receita/crédito |

## 8. Riscos & mitigação

- **Uptime no PC pessoal**: scheduled task cobre reboot, mas PC desligado = site fora. Mitigar: monitor externo (UptimeRobot no /health via clipia.com.br) + plano de migração para VPS/GPU cloud quando houver pagantes (~R$150-400/mês).
- **Capacidade (worker solo)**: fila cresce em pico. Mitigar: mensagem de fila honesta na UI; segundo worker é trivial se a GPU aguentar (compose é curto; o gargalo é o LLM/render).
- **Conteúdo abusivo/moderação**: gpt-image moderation já em "low"; TOS publicado; revisar jobs falhos por bloqueio no admin.
- **Custo ElevenLabs/OpenAI em escala**: medir por vídeo no beta antes de abrir público; ajustar créditos.
- **Burnout do fundador**: manter emprego até a meta de 90 dias; o produto opera sozinho (pipeline + scheduled task), o trabalho diário é curadoria do canal + suporte.

## 9. Decisões em aberto (para o dono)

1. Subir preço do novelinha (5→6-7 créditos) ou reduzir qualidade default da imagem? → decidir após medir custo real no beta.
2. Nome do canal dogfooding e nicho do conteúdo (sugestão: curiosidades/histórias — os templates mais fortes).
3. SMTP de produção (qual provedor) para verificação de e-mail em escala.
4. Quando contratar infra dedicada (gatilho sugerido: 10 pagantes OU fila média >30 min).
