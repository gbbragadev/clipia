# /loops R1 — Agência de agentes no Clipia (2026-07-12)

Primeira rodada com a **agência** (`C:\agency-agent`, git próprio): 5 reviewers + 1 researcher
+ céticos adversariais via Workflow. **22 agentes, ~1,53M tokens de subagente, 22 min, 0 erros.**
Funil: 17 achados brutos → 8 sérios (severity≥3) → 4 CONFIRMED / 3 PLAUSIBLE / 1 REFUTED + 9 leves.

Nota operacional: a descoberta de `agentType` custom demorou minutos (não segundos) — a rodada
usou os bodies inline (fallback planejado). Os 8 `agency-*` ficaram disponíveis nativamente ainda
na sessão; próximas rodadas podem usar `agentType: agency-*` direto.

## ✅ Aplicados nesta rodada (verify na seção final)

1. **Fidelidade export: flush do auto-save antes do render** (do CONFIRMED #1, severity 5).
   O achado do finder ("scenes nunca chega ao export por faltar em `_EDITABLE_KEYS`") estava
   **errado no mecanismo** — o `/edit` sincroniza `composition.scenes → script.json`
   (routes.py:1001-1004) e o `build_composition_props` lê `transition` de lá. O 1º cético
   confirmou errado; o 2º achou o bug REAL: **race** entre o auto-save com debounce de 1,5s e o
   POST /render imediato — editar e exportar em <2s renderiza estado velho do disco **e debita
   créditos por ele**; com `saveError`, renderiza edições que NUNCA foram salvas.
   Fix: `flushSave()` no EditorContext (cancela debounce, salva agora, retorna sucesso) +
   `handleRender` aguarda o flush e **aborta sem cobrar** se o save falhou.
   `frontend/src/contexts/EditorContext.tsx` + `frontend/src/components/editor/ExportPanel.tsx`.

2. **Refund que falha não mascara mais o erro original** (CONFIRMED #3, severity 4).
   `_refund_credits` sem try/except em 5 call sites (generate/enqueue, design_voice, clone_voice,
   regenerate_tts, render/enqueue): estorno quebrando (BD piscando) virava 500 genérico por cima
   da causa real e o estorno se perdia em silêncio. Fix: `_refund_credits_safe()` — rollback+retry,
   e na falha definitiva CRITICAL + alerta admin p/ estorno manual (mesmo contrato do worker
   d23c0ec). Teste de regressão: `tests/test_credits_integrity.py::test_refund_failure_does_not_mask_original_error`.
   `app/api/routes.py`.

3. **pendingCredits fresco no ExportPanel** (quick win pré-aprovado do backlog 11/07).
   O banner abria com o snapshot da composition (load do editor) — ai-suggest (0,5/consulta) e
   render/reset mudam o valor no servidor e o custo exibido mentia. Fix: `/status` agora expõe
   `pending_credits` (o Job já estava carregado — 1 linha) e o modal consome no mount + em cada
   poll, com fallback pro snapshot. Bônus: após o render terminar, o banner zera sozinho.
   `app/api/routes.py` (job_status) + `frontend/src/components/editor/ExportPanel.tsx`.

4. **Código morto deletado**: `ScriptEditor.tsx` (exportado, zero imports; renderizava
   `keywords_en` internos que a UI esconde de propósito) + comentário stale em `editor-api.ts`.

## 🚫 Gate: rejeitados / adiados COM MOTIVO

- **CONFIRMED #2 "refine cobrado com variations>1 sem usar o draft"** → **decisão de produto,
  não aplicado**. O refino (0,5) é serviço JÁ PRESTADO (LLM rodou); a UI documenta "somado ao
  custo do próximo vídeo" e o aviso de draft ignorado existe (GenerateForm:627). Cobrar é
  defensável; auto-descartar draft num clique de toggle é destrutivo. Recomendação ao Gui:
  ou (a) aplicar o draft como 1ª variação do lote, ou (b) aviso passa a mencionar o custo do
  refino acumulado. Aguardando decisão.
- **CONFIRMED #4 "EditorContext re-renderiza tudo a cada 100ms"** → **real, mas adiado p/ R2**.
  Confirmei o mecanismo (value sem memoização + polling do playerFrame); a nuance é que o storm
  só ocorre DURANTE playback (setState com valor igual faz bail-out pausado). Fix correto =
  split de contexto (PlayerFrameContext separado); consumidores de playerFrame: EditorTimeline,
  VideoPlayer, SubtitleTimeline, PretextSubtitlePreview, SceneTimeline, useKeyboardShortcuts
  (6 arquivos). useMemo no value NÃO resolve (playerFrame está nas deps). Esforço M — topo da R2.
- **PLAUSIBLE "refine pending sobrevive à troca de tópico"** → design deliberado (carry
  documentado na UI; teste test_script_preview.py:110 prova floor). Já está no backlog 11/07
  como decisão de produto (TTL 24h). Sem ação.
- **PLAUSIBLE "reset_job sem try/except no commit"** → refutação do 2º cético convence: débito +
  reset na MESMA transação com rollback automático (teste de integridade cobre). Design correto.
- **PLAUSIBLE "EditorTimeline ticks sem useMemo"** → impacto refutado por benchmark (~0,001ms).
  Vira irrelevante com o split da R2.
- **REFUTED "_refund_credits sem rowcount"** → soft-delete + débito imediatamente antes provam
  User vivo. Céticos 2×refuted.

## 🟡 Leves (9) — para triagem futura

- Aviso de variações não menciona o custo do refino acumulado (S, casa com a decisão pendente).
- Sem endpoint p/ limpar refine pending (decisão de produto — mesmo tema do carry).
- max_scenes sem validação no frontend (422 opaco ao editar preview com muitas cenas) (S).
- Ações pagas não retornam `cost` na resposta (design/clone) — "custo sempre visível" (S).
- Refine pending só em Redis (wipe = perda silenciosa de 0,5-1cr) (M, produto decide).
- ai-suggest sem cap de acumulação de pending_credits (abuse teórico) (S).
- VideoCard mobile: metadados comprimidos ~133px úteis (P2 aberto de 11/07) (S).
- SceneGrid: reduce+offsets recalculados por render (cai junto com o split da R2).
- ~~ScriptEditor morto~~ → aplicado nesta rodada.

## 🔎 Pesquisa (delta de concorrentes, 5 recs com fonte)

1. **Submagic (mar/26): social publishing** com título/hashtag por plataforma (M, impacto alto).
2. **AutoShorts/Revid: API pública + MCP/CLI** (L) — mercado de automação aberto.
3. **Fliki (jan/26): playground grátis** sem queimar créditos (M) — lever de conversão.
4. **⚠️ Faceless.so + Google Veo 3.1**: claim de custo 85% menor que Seedance — VALIDAR; se real,
   ameaça o custo do template ai_video (L p/ reagir, S p/ validar o claim).
5. **Revid: templates "brainrot"** (PDF/Text-to-Brainrot) (S!) — candidato a template novo barato.

## Verify (fechado)

- pytest completo: **435 verdes** (incl. teste de regressão novo do refund-safe)
- npx next typegen + tsc --noEmit: **exit 0**
- Deploy: frontend build+restart (49 chunks 200, build consistente) + backend via schtask
  (PID antigo 59272 morto, novo /health 200). GOTCHA aprendido: deletar a schtask enquanto
  roda MATA a árvore do processo (1ª tentativa morreu com ^C antes do kill) — esperar o log
  do script concluir antes do /delete; e /health NÃO é sinal de restart (o velho também
  responde) — validar por PID/campo novo.
- Smoke em produção: home 200 console limpo · editor logado carrega com console limpo
  (EditorContext novo vivo, painel de transições visível) · `/status` vivo retorna
  `pending_credits` (SMOKE OK, era AUSENTE antes do restart de verdade).
- PR #7 mergeado na main (`d75972b`); site servindo o código novo.

## Custo da rodada

22 agentes (6 find + 16 verify) · ~1,53M tokens de subagente · 22 min wall-clock · 0 erros.
Orquestração: Workflow `clipia-agency-r1` (run wf_2ff50e9d-ea4).
