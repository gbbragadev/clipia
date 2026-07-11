# Audit UX do Editor — 11/07/2026 (sessão de reforma)

Walkthrough persona (criador, primeiro edit) em build isolado `.next-verify` na porta
3103, desktop 1440×900 + mobile 390×844, job real `c70d2315` (stock, 5 cenas) com
todas as edições da matriz E2E aplicadas. Cliques pagos evitados; conta admin.

## Prova de fidelidade (matriz E2E, mesma sessão)

Editar TUDO → exportar → inspecionar frames do MP4:

| Campo | Preview | Export (antes) | Export (depois dos fixes) |
|---|---|---|---|
| Legenda karaoke coral | ✅ embaixo | ❌ caixa sólida no MEIO-DIREITA | ✅ idêntico ao preview |
| Overlays (4 tipos) | ✅ | ✅ (layout padrão) / ❌ layouts especiais | ✅ nos 3 layouts |
| Música + volume | ✅ | ✅ | ✅ (tech-pulse 0.45 medido) |
| Texto de cena/transição | ✅ | ✅ | ✅ |
| Export de jobs de imagens IA | — | ❌ "No media files found" | ✅ (job `5a821c34` completou) |

Causas-raiz: `AbsoluteFill` é `flexDirection: column` (justify/align com papéis
trocados em TODOS os presets) e `background-clip: text` não suportado pelo
compositor de vídeo do Remotion (só no still). Detalhe completo no commit.

## Achados corrigidos nesta sessão

1. **ExportPanel ignorava render em curso ao abrir** — mostrava "Aplicar edições e
   renderizar" ativo durante um render vivo; agora consulta `/status` na montagem e
   retoma o progresso.
2. **Preset de legenda ativo invisível** — carrossel com scroll oculto
   (`scrollbarWidth: none`) escondia o 4º+ preset (inclusive o selecionado); agora
   `flexWrap`.
3. **Botões de transição estouravam o painel** no desktop (Wipe cortado); `flexWrap`.
4. **Aba Voz lenta** — `/voices` chamava a API ElevenLabs a cada request; cache
   10min server-side (stale-if-error).
5. **Keywords internas em inglês** expostas no card da cena; removidas da UI.
6. **Hint de atalhos de teclado no mobile** (sem teclado); oculto < 768px.
7. **Acentuação** varrida no editor: Posição/Animação/Transição/composição/mídias/
   única/VOCÊ SABIA?/Botão/animação/finalização/Início/vídeo.
8. **Rewrite default `localhost` → `127.0.0.1`** — resolver IPv6 desta máquina
   causava 500 intermitente no proxy (visto ao vivo no audit).

## Bom estado confirmado (não mexer)

- Mobile reflow: player topo + cenas + abas inferiores + gaveta de timeline com FAB
  (padding correto); undo/redo no header.
- CostChips presentes nas 4 ações pagas; badge "Minha Voz" corrigida para 2cr.
- Elementos: 4 templates com descrição + lista de ativos com timing e Remover.
- Captions prontas por rede (YT/TikTok/IG) no export.
- Console limpo (0 erros) nos dois viewports após os fixes.

## Pendências (decisão/próxima sessão)

- **P1 — Vozes grátis sem preview de áudio**: cards Edge não têm ▶ (escolha às
  cegas); gerar amostras estáticas por voz seria ~10 linhas + assets. Vale fazer.
- P2 — Fundo de legenda tem preset ROXO (fora da paleta; fase D).
- P2 — Emojis como ícones funcionais nos templates de elementos (anti-padrão
  DESIGN.md; trocar por lucide na fase D).
- P2 — Textarea da cena com min-height 48px (scroll interno cedo demais).
- P2 — Área morta à esquerda do player em 1440px (aproveitar p/ preview de estilo?).
- P2 — Barra de rolagem horizontal aparece na gaveta mobile (overflow-x da página).
