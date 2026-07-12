# 009 — Delight: celebração "vídeo pronto" + tick de créditos

- **Status**: DONE (executado por GPT-5.6 Sol via cgpt em 2026-07-12; gate Opus: APROVADO 100% verbatim; tsc verde)
- **Commit**: 6428262
- **Severity**: LOW (aditivo — momento raro, delight permitido)
- **Category**: Missed opportunities (AUDIT seção 8)
- **Estimated scope**: 3 arquivos (`globals.css`, `VideoCard.tsx`, `Navbar.tsx`)

## Problema (oportunidades, não bugs)

**1. O momento de maior emoção do produto passa em branco** — o usuário espera ~2 minutos pela geração; quando o polling detecta a conclusão, o card apenas troca o badge para "Pronto" num frame. Eventos raros e de alta emoção são exatamente onde o playbook PERMITE gastar orçamento de delight. Hoje (`frontend/src/components/dashboard/VideoCard.tsx`): a transição `status ativo → completed/editable` não tem nenhuma marcação visual além do badge.

**2. Créditos mudam seco no Navbar** — após qualquer ação paga, o número simplesmente vira outro; não há feedback de que o débito/crédito aconteceu:

```tsx
{/* frontend/src/components/Navbar.tsx:59 — atual (desktop; o mobile na :116 é análogo) */}
<span className="text-coral font-semibold text-xs">{user.credits}</span>
```

## Alvo

- **Card recém-concluído**: um anel coral que acende e apaga UMA vez (~900ms) no card cujo status transicionou de ativo para pronto durante a sessão (nunca em cards que já montaram prontos). Sem loop, sem confete — crisp, uma respiração de destaque.
- **Créditos**: quando `user.credits` muda, o número conta do valor antigo para o novo (~0.6s) e dá um pop sutil de escala (1 → 1.06 → 1). Com reduced-motion: troca direta, sem tween.

## Convenções do repo a seguir

- Keyframes utilitários vivem em `frontend/src/app/globals.css` na seção "Landing keyframes & motion utilities" (linhas 188+), padrão `.anim-*`.
- Tokens JS: `EASE`, `DURATIONS` e `prefersReducedMotion()`/`useReducedMotionState` de `frontend/src/lib/motion.ts`.
- Lib motion v12 (`motion/react`): para o contador usar `animate()` imperativo (import `animate` de `motion/react`).
- `ACTIVE_JOB_STATUSES` vem de `@/lib/editor-api` (o VideoCard já importa, linha 6).

## Passos

1. **`frontend/src/app/globals.css`** — adicionar na seção de keyframes (após `.anim-scene-fade`, ~linha 221):
   ```css
   /* One-shot: anel coral no card cujo job acabou de ficar pronto (delight raro). */
   @keyframes ready-ring {
     0% { box-shadow: 0 0 0 0 rgba(255, 86, 56, 0); }
     25% { box-shadow: 0 0 0 3px rgba(255, 86, 56, 0.55), 0 0 24px rgba(255, 86, 56, 0.25); }
     100% { box-shadow: 0 0 0 0 rgba(255, 86, 56, 0); }
   }
   .anim-ready-ring { animation: ready-ring 900ms var(--ease-out, ease-out) 1 both; border-radius: 16px; }
   ```
   (Com a rede de reduced-motion — nuclear atual ou a gentil do plano 008 — `animation-duration: 0.01ms` mata este one-shot automaticamente. Nada a fazer.)
2. **`frontend/src/components/dashboard/VideoCard.tsx`** — detectar a transição ativo→pronto e aplicar a classe uma vez:
   - Adicionar aos imports existentes de react: `useState, useRef, useEffect` (já importados na linha 3) — nada a acrescentar.
   - Dentro do componente, após `const canEdit = ...` (linha ~47), adicionar:
     ```tsx
     // Delight one-shot: acende um anel coral quando ESTE card transiciona de "gerando"
     // para "pronto" durante a sessão (nunca em cards que já montaram prontos).
     const prevStatusRef = useRef(job.status)
     const [justCompleted, setJustCompleted] = useState(false)
     useEffect(() => {
       const prev = prevStatusRef.current
       prevStatusRef.current = job.status
       if (
         ACTIVE_JOB_STATUSES.includes(prev) &&
         ['completed', 'editable'].includes(job.status)
       ) {
         setJustCompleted(true)
         const t = setTimeout(() => setJustCompleted(false), 1000)
         return () => clearTimeout(t)
       }
     }, [job.status])
     ```
   - No wrapper interno do card (linha ~140, o div `flex flex-col h-full bg-[var(--bg-raised)] ...`), acrescentar a classe condicional:
     ```tsx
     className={`flex flex-col h-full bg-[var(--bg-raised)] hover:bg-[var(--bg-surface)] transition-colors rounded-xl overflow-hidden relative ${justCompleted ? 'anim-ready-ring' : ''}`}
     ```
3. **`frontend/src/components/Navbar.tsx`** — criar um componente de número animado no próprio arquivo (usado 2×) e usar nos dois pontos:
   - Adicionar `animate` ao import de motion da linha 5: `import { AnimatePresence, motion, animate } from 'motion/react'`.
   - Antes do `export default function Navbar()`, adicionar:
     ```tsx
     /** Número de créditos com tick animado: conta do valor antigo pro novo e dá um
      *  pop sutil quando muda. Reduced-motion: troca direta. */
     function CreditsValue({ value, className }: { value: number; className: string }) {
       const reduceMotion = useReducedMotionState()
       const ref = useRef<HTMLSpanElement>(null)
       const prevRef = useRef(value)
       useEffect(() => {
         const prev = prevRef.current
         prevRef.current = value
         const el = ref.current
         if (!el || prev === value) return
         if (reduceMotion) {
           el.textContent = String(value)
           return
         }
         const controls = animate(prev, value, {
           duration: 0.6,
           ease: EASE,
           onUpdate: (v) => { el.textContent = String(Math.round(v)) },
         })
         const pop = animate(el, { scale: [1, 1.06, 1] }, { duration: 0.35, ease: EASE })
         return () => { controls.stop(); pop.stop() }
       }, [value, reduceMotion])
       return <span ref={ref} className={`inline-block ${className}`}>{value}</span>
     }
     ```
     (Imports extras necessários no topo do arquivo: `useRef` já vem de react? A linha 4 importa `useEffect, useState` — acrescentar `useRef`. `EASE` e `useReducedMotionState` já são importados na linha 8.)
   - Linha 59 (desktop): trocar
     ```tsx
     <span className="text-coral font-semibold text-xs">{user.credits}</span>
     ```
     por
     ```tsx
     <CreditsValue value={user.credits} className="text-coral font-semibold text-xs" />
     ```
   - Linha ~116 (menu mobile): trocar o span análogo por `<CreditsValue value={user.credits} className="text-coral font-semibold text-sm" />`.

## Limites

- NÃO adicionar confete, som, nem animação em loop — o anel é one-shot e o tick dura <1s.
- NÃO mexer no polling/estado de jobs nem no AuthContext.
- NÃO celebrar cards que já montam prontos (a guarda do prevStatusRef cuida disso — preservar).
- NÃO adicionar dependências.
- Se o código divergir do citado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Gerar um vídeo e deixar o dashboard aberto: no tick de polling em que vira "Pronto", o card acende o anel coral uma única vez (~0.9s) e volta ao normal. Recarregar a página: o card pronto NÃO acende de novo.
  - Executar uma ação paga (ex.: gerar vídeo): o número de créditos no Navbar conta para baixo suavemente com um pop sutil.
  - Comprar/ganhar créditos (ou simular alterando o estado): conta para cima.
  - DevTools → Rendering → `prefers-reduced-motion: reduce`: número troca seco; anel não aparece.
- **Done when**: os dois momentos têm feedback visível, one-shot, sem loops; reduced-motion os desliga; tsc/build verdes.
