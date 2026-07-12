# Backlog da Auditoria Total — 11/07/2026

> Sprint Fable: auditoria multi-agente (7 dimensões, 24 agentes, verificação adversarial)
> + fix sprint. Este doc registra o que foi CORRIGIDO e o que ficou aberto, com prioridade.
> Segurança ficou fora de escopo por decisão do Gui.
>
> **UPDATE 12/07**: rodada /loops R1 com a agência de agentes (`C:\agency-agent`) — 22 agentes,
> 4 CONFIRMED, 3 fixes aplicados + 1 quick win deste backlog fechado (pendingCredits stale).
> Delta completo em `docs/superpowers/reviews/2026-07-12-agency-loops/round1.md`.
>
> **UPDATE 12/07 (madrugada)**: triagem adversarial da auditoria externa GPT-5.6 Sol
> (`docs/INSIGHTS-GPT56-2026-07-12.md`, 25 achados) — 6 céticos `agency-cetico`, **19 achados
> aplicados** em 5 commits (dinheiro: dialogue_duo server-side, teto 8 cenas ai_video,
> cancel no poll do vídeo IA, custo c/ refino na UI, /generate 202; ativação: email "vídeo
> pronto" + signup_intent; SEO: blog cluster, auth noindex, OG/VideoObject no /v, posters
> reais, copy de bônus estável; perf: hero sem 7MB, RAF ocioso, throttle sliders, debounce
> texto, focus trap). Suíte 435→**445 verdes**; typegen+tsc 0 erros. **NÃO deployado**
> (aguardando OK). Round file: `docs/superpowers/reviews/2026-07-12-triagem-gpt56/round1.md`.

## ✅ Corrigido neste sprint (commits na feat/editor-reforma)

| Commit | O quê |
|---|---|
| `9daf7ea` | gitignore de artefatos pesados de sessão (223MB untracked) |
| `a99e9e2` + updates | ROADMAP-QUALIDADE-VIDEO marcado com a verdade (P0 6/6 feitos; docs mentiam) |
| `3b4e25a` | Suíte imune ao ambiente: bonus do .env zerado + Redis real isolado (10 falhas → 427 verdes) |
| `f6b0b59` | **Ducking + loudnorm** nos 3 layouts (P1 #7/#8 do roadmap) — validado com encode real (-7,2dB música sob voz; -13,6 LUFS) |
| `ac04d58` | Acentos pt-BR em 13 strings de UI + alts + fetchJson com await |
| `d23c0ec` | **Créditos confiáveis**: export que falha devolve o custo exato (rerender_cost), refund falho alerta admin, reset/render atômicos, ai-suggest com dedup 429, cleanup de status "error", compose não trunca vídeo, nvenc cacheado |
| `e3f9264` | /jobs sem bloquear o event loop (to_thread) + índice em jobs.status (migration `b7c8d9e0f1a2`) |
| (este) | Preview das vozes Edge (paridade com concorrentes; play grátis na aba Voz) |

## 🟡 Aberto — P1/P2 verificados ou plausíveis

- ~~**ExportPanel: pendingCredits pode ficar stale no banner**~~ → **FECHADO 12/07** (R1 da
  agência): `/status` expõe `pending_credits` e o modal consome no mount + polls.
- **AIAssistant handleApply "race"** (P2, nota): o finding original superestimou — o trecho updateScene→fetch é síncrono. O caso real (usuário edita DURANTE o regen de 15-40s) já é coberto por `narrationStale`. Só mexer se aparecer report real.
- **Paralelizar _prepare_scene por cena** (P2, M) — encode CPU sequencial antes do NVENC; ganho real de wall-clock na geração. Risco médio (pipeline quente): fazer com encode real de validação.
- **Refino carry 0.25-0.5 crédito pode expirar silencioso no Redis TTL 24h** (P2, produto decide): liquidar no refine ou estender TTL.
- **Console error `%c%d ... NaN` (4×/página)** — NÃO é do nosso código (zero `%c` no src); vem de lib de terceiro (investigar qual — provável Remotion/Next devtools). Baixa prioridade.
- **Landing seções 01-03 "vazias" em desktop 1366×768** (achado do walkthrough headless) — pode ser animação Reveal não disparada no headless; validar A OLHO em browser real antes de mexer.
- **Dashboard mobile: cards de vídeo comprimidos sem metadados legíveis** (P2, S).
- **Ken Burns p/ vídeos, `_prepare_card_scene`, suppress_windows, xfade na geração inicial, SFX beat-level** — P1/P2 restantes do ROADMAP-QUALIDADE (itens 9-13), esforço M cada.
- **Coerência trend→template + subtemas dinâmicos** (PROXIMA-SESSAO-UX-GERACAO itens 3-4).

### Da triagem GPT-5.6 (12/07) — backlog novo

- **Clipes órfãos completo** (P1, M): persistir IDs OpenRouter por cena + reusar clipes
  prontos em retry do mesmo job (o check de cancel no poll já foi aplicado — captura 99%).
- **Imagens IA em paralelo** (P1→validar, M): `Semaphore(2)` + `to_thread` no
  `task_generate_images` — pipeline quente, exige job real de validação pós-deploy.
- **Fila ignora re-renders** (P2, M): posição "0 na frente" enquanto um export Remotion
  ocupa o worker solo (query só conta `status="queued"` no DB).
- **Remover `key=version` do Player** (perf, M + risco): a fidelidade E2E foi validada COM
  os remounts; só mexer com browser real validando preview==export (throttle já mitiga).
- **Loop viral /v de usuário** (P0 estrutural, L): publicação opt-in c/ slug revogável +
  thumbnail + share WhatsApp; o mini-loop do showcase (OG + link da galeria) já está no ar
  p/ provar o mecanismo antes.
- **Seção "diferenciais premium" na landing** (P2, vitrine): rascunho/diálogo/lote/IA só
  aparecem pós-cadastro; precisa de screenshots reais (pendência de vitrine).
- **5 páginas programáticas** (P2, M): 3 transversais (shorts/reels/tiktok) + 2 de problema
  — só após 30 dias de impressões das 7 atuais.
- **Guarda pré-ads de privacidade** (decisão do Gui): GA/Meta Pixel estão INATIVOS hoje
  (IDs ausentes — política correta), mas `TrackingScripts` carrega sem consentimento se os
  IDs entrarem no env. Antes de social/ads: decidir analytics-only + texto vs CMP.
- **A/B 480p do ai_video** (decisão): resolução configurável; só promover com A/B visual
  em celular + fatura real.

## 🧭 Concorrentes — pesquisado 11/07 (10 players)

Implementado agora: preview multi-voz (Edge). Já existia (o finder errou): pricing transparente na landing, programa de referral (+2 créditos).

Quick wins que ficaram (ordenados por impacto/esforço):
1. **Legendas com efeitos virais** (presets bounce/pop/shake) — Submagic/Crayo; word-timestamps já existem; mexe no export path → exige validação de fidelidade (1-2h).
2. **Modo Quick vs Pro no GenerateForm** — InVideo; defaults 1-click p/ novato (1,5h; decisão de UX do fluxo de conversão — validar com o Gui).
3. **Watermark removível por compra** — padrão do mercado; exige gating (produto é créditos, não planos — decidir modelo).
4. **Auto-agendamento YouTube/TikTok/IG** — AutoShorts; retenção alta, MAS OAuth de 3 plataformas (2h+ cada, apps de developer) — não é quick win de verdade.
5. **Série de vídeos (tema → 5-7 variações + calendário)** — o lote ×5 já existe no form; falta o calendário (M).
6. **Tradução/dublagem multi-idioma** — Braiv/Fliki (M).
7. **Clips de vídeo longo (repurposing)** — OpusClip; NOVO nicho, não quick win (L).

Referência de preços (2026): AutoShorts $19-69/mês · Revid $39-199 · Crayo $19-79 · Fliki free-$99 · Submagic $20+ · OpusClip $15+ · Braiv (BR) ~$20+. ClipIA compete por compra única em R$ sem assinatura — manter esse contraste na comunicação.

## ❌ Refutados pela verificação adversarial (NÃO gastar tempo)

- `useState(generateCaptions)` no ExportPanel — initializer correto de React.
- Race de pending_credits no render_video — lock + commit/refresh cobrem; teste prova.
- Commits múltiplos em _debit/_refund como "janela de inconsistência" — desenho intencional (enqueue não pode estar em TX aberta).
- design_voice refund "silencioso" — evidência era falsa (linha 179 é métrica, exceção propaga).
- Aviso "Linha do tempo" sem explicação no editor mobile — é o FAB da timeline (ícone de relógio), com aria-label; falso positivo do walkthrough.
