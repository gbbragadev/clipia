# 008 — Reduced-motion gentil (não nuclear) + polish dos indicadores de status

- **Status**: TODO
- **Commit**: 6428262
- **Severity**: LOW-MEDIUM
- **Category**: Accessibility (AUDIT seção 6) + Purpose & frequency (seção 1)
- **Estimated scope**: 3 arquivos (`globals.css`, `StatusBadge.tsx`, sem mudanças em `JobStepper.tsx`)

## Problema

**1. Rede de reduced-motion "nuclear" (`frontend/src/app/globals.css:130-138`)** — zera TODAS as transições para 0.01ms:

```css
/* atual */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
  .reveal { opacity: 1 !important; transform: none !important; }
}
```

Reduced motion significa **menos e mais gentil, não zero**: fades de opacity/cor ajudam compreensão e não disparam desconforto vestibular (o problema é MOVIMENTO). Efeitos colaterais do nuclear hoje: modais/backdrops piscam seco, trocas de cor de hover piscam, e os **spinners de loading congelam** (`animation-iteration-count: 1` + 0.01ms) — um spinner parado comunica "travou", perdendo a indicação essencial de estado.

**2. Card em geração tem DOIS pulses dessincronizados** — StatusBadge "Gerando" pulsa E o círculo ativo do JobStepper pulsa, no mesmo card, ×N cards visíveis no grid (polling). Dois metrônomos fora de fase viram ruído; um indicador de atividade basta:

```tsx
// frontend/src/components/ui/StatusBadge.tsx:14 — atual
processing: 'bg-coral/15 text-coral border-coral/30 animate-pulse',
```
```tsx
// frontend/src/components/dashboard/JobStepper.tsx:48 — atual (este FICA — é o "mapa da viagem")
? 'bg-coral text-white animate-pulse'
```

**3. StatusBadge troca de cor seco** — o polling muda `variant` (neutral → processing → success) sem transição; um `transition-colors` curto suaviza a troca sem custo.

## Alvo

- Transições preservadas em 150ms no modo reduzido (fades curtos, sem movimento — os transforms já são cobertos pelos `initial={reduceMotion ? false : ...}` dos componentes motion e pelo `.reveal` forçado).
- Keyframes decorativos continuam mortos (0.01ms), MAS spinners de loading continuam girando (exceção explícita — motion essencial de estado).
- Um único pulse por card (o do JobStepper); badge ganha `transition-colors`.

## Convenções do repo a seguir

- A rede vive em `frontend/src/app/globals.css:129-138` com o comentário "Fase 0" — editar no lugar, manter o comentário-âncora.
- Spinners conhecidos do repo: `.editor-loading__spinner` (editor.css:18-22, spin 0.7s), `.export-status__spinner` (editor.css:298, spin 0.9s), e a classe Tailwind `animate-spin` (usada com `<Loader2>` em VideoCard, VideoPlayerModal etc.).
- StatusBadge: classes em `frontend/src/components/ui/StatusBadge.tsx:8-15` (mapa `VARIANT_CLASSES`) e base na linha 29.

## Passos

1. **`frontend/src/app/globals.css:130-138`** — substituir o bloco por:
   ```css
   /* ── Fase 0: Respeita usuarios com motion reduzido ──
      Gentil, nao nuclear: transicoes curtas de opacity/cor FICAM (ajudam compreensao,
      nao disparam desconforto vestibular — movimento e que dispara); keyframes
      decorativos morrem; spinners de loading sao excecao (indicacao essencial de
      estado — parados comunicam "travou"). */
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
       transition-duration: 150ms !important;
       scroll-behavior: auto !important;
     }
     .editor-loading__spinner,
     .export-status__spinner,
     .animate-spin {
       animation-duration: 1s !important;
       animation-iteration-count: infinite !important;
     }
     .reveal { opacity: 1 !important; transform: none !important; }
   }
   ```
2. **`frontend/src/components/ui/StatusBadge.tsx:14`** — remover o `animate-pulse` do variant processing:
   ```tsx
   processing: 'bg-coral/15 text-coral border-coral/30',
   ```
3. **`frontend/src/components/ui/StatusBadge.tsx:29`** — adicionar `transition-colors duration-200` à className base:
   ```tsx
   'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition-colors duration-200',
   ```
4. **`frontend/src/components/dashboard/JobStepper.tsx`** — NENHUMA mudança (o pulse do círculo ativo vira o único indicador pulsante do card, de propósito).

## Limites

- NÃO remover a regra `.reveal` forçada nem o `scroll-behavior: auto`.
- NÃO adicionar novas animações neste plano.
- NÃO mexer nos componentes motion (eles já tratam reduced-motion via `useReducedMotionState`).
- Se o código divergir do citado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check** (DevTools → Rendering → `prefers-reduced-motion: reduce` LIGADO):
  - Hover num card do dashboard: a cor ainda faz um fade curto (150ms), não pisca seco.
  - Gerar um vídeo / abrir tela de loading do editor: o spinner CONTINUA girando.
  - Landing: marquee, float e shimmer continuam mortos; conteúdo `.reveal` visível sem movimento.
  - (Reduced-motion DESLIGADO) Card em geração no dashboard: só o círculo do stepper pulsa; o badge "Gerando" fica estável e, quando o status muda para "Pronto", a troca de cor é um fade de 200ms.
- **Done when**: modo reduzido preserva fades e spinners e mata movimento/decoração; card em geração tem um único pulse; badge transiciona cor; tsc/build verdes.
