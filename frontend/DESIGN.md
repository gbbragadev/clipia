# DESIGN.md — ClipIA (fonte de verdade visual e de UX)

> Vale para TODA superfície: landing, dashboard, editor, credits, auth, admin.
> Se uma decisão de cor/tipo/componente não está aqui, decida, aplique e REGISTRE aqui.
> Dark-only (decisão 10/07/2026). Norte de referência: Linear/PostHog (dashboard denso e
> preciso), Runway/Framer (editor cinematográfico), nossa landing v2 (conversão honesta).

## Identidade

Estúdio de vídeo brasileiro, direto e confiável. Fala de OUTPUT ("vídeo pronto"), nunca de
tecnologia pela tecnologia. Sem hype, sem promessa de resultado ("viralize" é proibido).
Todo texto de UI em pt-BR com acentuação correta.

## Tokens (Tailwind `@theme` em `src/app/globals.css` — única fonte)

| Token | Valor | Uso |
|---|---|---|
| `ink` / `ink-2` | `#08090f` / `#0b0d15` | fundo de página |
| `panel` / `panel-2` / `panel-3` | `#11141d` / `#161a25` / `#1c2130` | cards, superfícies, hover |
| `coral` / `coral-soft` | `#ff5638` / `#ff7a61` | AÇÃO primária, marca |
| `azure` | `#3e9bff` | acento secundário, info/render |
| `mint` | `#43e0ad` | positivo, bônus |
| `cloud` / `mist` / `mist-2` | `#f2f5fa` / `#a6afc2` / `#8b93a8` | texto 1/2/3 |
| `line` | `rgba(255,255,255,0.08)` | bordas |
| `success` / `warn` / `danger` | mint / `#fbbf24` / `#f87171` | status semântico |

As vars antigas do shell (`--bg-base`, `--bg-raised`, `--text-primary`…) são ESPELHO
desses valores (bloco `:root` no globals.css) — não introduza cor nova fora daqui.
Gradiente da marca: `linear-gradient(135deg, #ff5638, #3e9bff)` (coral→azure). O
gradiente coral→índigo (`#6366f1`) está MORTO — não ressuscite.

**Exceção legítima**: cores escolhidas pelo USUÁRIO para o conteúdo do vídeo dele
(presets de legenda, moods de música) não são paleta de UI — variedade é feature.

## Tipografia

- Display/headings: **Sora** via `font-display` (extrabold, tracking-tight).
- Corpo/UI: **Geist** (é o `--font-inter` — nome legado; NÃO usar Inter de verdade).
- Escala: `h-display`, `.h-1`, `.h-2` (globals.css) para títulos de página/seção;
  UI densa usa text-sm/13px; microcopy 11-12px `text-mist-2`.
- Números tabulares em contadores de crédito e tabelas (`tabular-nums`).

## Diais por superfície (taste)

| Superfície | Densidade | Movimento | Nota |
|---|---|---|---|
| Landing | média | médio (reveal, marquee) | vitrine |
| Dashboard | média-alta | baixo | ferramenta diária; nada de reveal em lista |
| Editor | alta | funcional apenas | precisão > show |
| Credits/Auth | baixa | baixo | zero distração na hora do dinheiro |

`prefers-reduced-motion` SEMPRE respeitado (rede de segurança global no globals.css).

## Guardrails de CONFIANÇA (inegociáveis — princípio do produto)

1. **Custo antes da ação**: toda ação que consome créditos mostra o custo E o saldo
   ANTES do clique (padrão: CostChip/linha "N créditos · você tem M").
2. **Nenhum número prometido hardcoded**: valores de oferta (créditos grátis, bônus,
   preços) vêm do backend (`/api/config`, pacotes) — nunca de string solta.
3. **Status honesto**: estados do sistema visíveis, em pt-BR, via `StatusBadge`
   (`components/ui/StatusBadge.tsx`). Nada de status cru do banco na tela.
4. **Ação destrutiva/paga = confirmação**: `Modal` acessível
   (`components/ui/Modal.tsx`) com consequência + custo explícitos.
   Exceção deliberada (decisão de produto 11/07/2026): o refino de roteiro
   (0,5cr, GenerateForm) executa SEM Modal — é ação iterativa de baixo valor
   e o custo já aparece no botão e no painel; Modal ali só adiciona atrito.
5. **Erro sempre com saída**: mensagem em pt-BR + ação de retry
   (`components/ui/feedback.tsx` InlineError/useToast).

## Componentes canônicos

`components/ui/`: `Button` (re-export do design system), `StatusBadge` (+
`jobStatusBadge`/`purchaseStatusBadge`), `Modal`, `feedback` (toasts/InlineError),
`skeletons`. Antes de criar componente novo, procure aqui e em
`components/landing/ui/`.

## Anti-padrões (impeccable — reprovam PR)

- Texto cinza sobre fundo colorido; contraste < 4.5:1 em texto de leitura.
- Card dentro de card; wrapper redundante.
- Fonte fora de Sora/Geist; roxo/índigo de qualquer espécie na UI.
- Bounce/elastic easing; animação em lista longa; motion sem propósito.
- Emoji como ícone de UI funcional (emoji só em conteúdo/nicho).
- Botão desabilitado sem explicação do porquê.
- Texto de UI em inglês ou sem acento.

## Checklist de entrega por tela (ui-ux-pro-max + F5)

- [ ] Console limpo · [ ] contraste 4.5:1 · [ ] 375px e 1440px sem quebra
- [ ] hover/focus visíveis · [ ] Tab navega, Esc fecha modal · [ ] reduced-motion ok
- [ ] estados: loading (skeleton), vazio (EmptyState com CTA), erro (retry)
- [ ] guardrails de confiança conferidos (custo/status/confirmação)
- [ ] screenshot desktop+mobile arquivado (`LIVE-app-*.png`)
