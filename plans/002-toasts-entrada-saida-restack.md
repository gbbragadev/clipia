# 002 — Toasts com entrada, saída e restack suave

- **Status**: DONE (executado por GPT-5.6 Sol via cgpt em 2026-07-12; gate Opus: APROVADO sem findings; tsc verde)
- **Commit**: 6428262
- **Severity**: HIGH
- **Category**: Interruptibility (AUDIT seção 4) + Physicality (seção 3)
- **Estimated scope**: 1 arquivo (`frontend/src/components/ui/feedback.tsx`)

## Problema

Os toasts (sucesso/erro/info — disparados em downloads, falhas de rede, ações do editor) aparecem e somem **sem nenhuma animação**. Pior: um toast novo entra no TOPO da pilha (`[item, ...current]`), empurrando os existentes para baixo num salto seco; quando um expira (timeout 5s), os de baixo PULAM para cima. Toasts empilham rápido (vários downloads/erros em sequência) — exatamente o caso em que a animação precisa ser retargetável/interruptível.

```tsx
// frontend/src/components/ui/feedback.tsx:105-120 — atual
export function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed right-4 top-4 z-[80] w-[min(24rem,calc(100vw-2rem))] space-y-3">
      {toasts.map((toast) => {
        const palette = TOAST_PALETTE[toast.tone]
        return (
          <div
            key={toast.id}
            className="card overflow-hidden shadow-2xl"
```

O `OfflineBanner` no mesmo arquivo (linhas 196-213) tem o mesmo problema (pop seco), em menor grau (raro).

## Alvo

- Toast novo desliza de cima com fade (`opacity: 0, y: -16, scale: 0.98` → `opacity: 1, y: 0, scale: 1`).
- Toast que sai encolhe com fade (`opacity: 0, scale: 0.96`), rápido (0.15s).
- Os toasts restantes **deslizam** suavemente para as novas posições (layout animation), nunca pulam.
- Transições via spring do repo (retargetável — spam de toasts nunca reinicia animação do zero).
- Reduced-motion: entradas/saídas viram fade puro, sem layout animation.

## Convenções do repo a seguir

- Tokens JS: `frontend/src/lib/motion.ts` — importar `EASE`, `DURATIONS`, `SPRING`, `useReducedMotionState`. `SPRING` é `{ type: "spring", stiffness: 380, damping: 30, mass: 0.8 }` (responsivo, não-bouncy — a personalidade do app).
- Lib: `motion/react` (`AnimatePresence`, `motion.div`).
- Exemplar de AnimatePresence com reduced-motion: `frontend/src/components/editor/EditorLayout.tsx:173-203`.

## Passos

1. Em `frontend/src/components/ui/feedback.tsx`, adicionar no topo:
   ```tsx
   import { AnimatePresence, motion } from 'motion/react'
   import { EASE, DURATIONS, SPRING, useReducedMotionState } from '@/lib/motion'
   ```
2. Reescrever o `ToastViewport` assim (atenção: o early-return `if (toasts.length === 0) return null` é REMOVIDO — o container precisa ficar montado para a animação de saída do último toast rodar; por isso o container ganha `pointer-events-none` e cada toast `pointer-events-auto`, senão o container vazio bloquearia cliques na área):
   ```tsx
   export function ToastViewport({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: string) => void }) {
     const reduceMotion = useReducedMotionState()

     return (
       <div className="pointer-events-none fixed right-4 top-4 z-[80] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-3">
         <AnimatePresence initial={false} mode="popLayout">
           {toasts.map((toast) => {
             const palette = TOAST_PALETTE[toast.tone]
             return (
               <motion.div
                 key={toast.id}
                 layout={!reduceMotion}
                 initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -16, scale: 0.98 }}
                 animate={{ opacity: 1, y: 0, scale: 1 }}
                 exit={
                   reduceMotion
                     ? { opacity: 0, transition: { duration: 0.15 } }
                     : { opacity: 0, scale: 0.96, transition: { duration: 0.15, ease: EASE } }
                 }
                 transition={SPRING}
                 className="card pointer-events-auto overflow-hidden shadow-2xl"
                 style={{
                   background: palette.bg,
                   borderColor: palette.border,
                 }}
               >
   ```
   O conteúdo interno do toast (linhas 121-167 atuais: dot, título, descrição, botões de ação/fechar) permanece IDÊNTICO; apenas o wrapper `<div key={toast.id}>` vira o `<motion.div>` acima e fecha como `</motion.div>`.
   Nota: `space-y-3` foi trocado por `flex flex-col gap-3` — com `mode="popLayout"` o item que sai é retirado do fluxo, e `space-y-*` (margens em irmãos) causa pulos; `gap` não.
3. No `OfflineBanner` (linhas 196-213), envolver com AnimatePresence e animar o pill:
   ```tsx
   export function OfflineBanner({ online }: { online: boolean }) {
     return (
       <AnimatePresence>
         {!online && (
           <div className="pointer-events-none fixed inset-x-0 top-4 z-[70] flex justify-center px-4">
             <motion.div
               initial={{ opacity: 0, y: -12 }}
               animate={{ opacity: 1, y: 0 }}
               exit={{ opacity: 0, y: -12 }}
               transition={{ duration: DURATIONS.fast, ease: EASE }}
               className="pointer-events-auto rounded-full border px-4 py-2 text-sm shadow-lg backdrop-blur-md"
               style={{
                 background: 'rgba(17, 17, 24, 0.9)',
                 borderColor: 'rgba(239, 68, 68, 0.3)',
                 color: '#fecaca',
               }}
             >
               Voce esta offline. Alguns recursos podem falhar ate a conexao voltar.
             </motion.div>
           </div>
         )}
       </AnimatePresence>
     )
   }
   ```

## Limites

- NÃO mudar a lógica do ToastProvider (ids, timeouts, limite de 4, dismiss) — só a camada visual do viewport.
- NÃO mudar o conteúdo/markup interno dos toasts (dot, títulos, botões).
- NÃO adicionar dependências.
- Se um trecho não bater com o código encontrado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Disparar um download no dashboard: o toast de sucesso desliza de cima com fade.
  - Disparar 3+ toasts em sequência rápida (ex.: 3 downloads): cada novo entra por cima e os antigos DESLIZAM para baixo (nunca pulam); nada reinicia do zero.
  - Esperar um toast expirar no meio da pilha: os de baixo sobem deslizando.
  - Clicar "Fechar" imediatamente após o toast aparecer (interrupção no meio da entrada): ele reverte da posição atual, sem salto.
  - DevTools → Rendering → `prefers-reduced-motion: reduce`: toasts viram fade puro e o restack é instantâneo (sem slide).
- **Done when**: pilha de toasts entra/sai/reordena sem nenhum salto seco; spam é interruptível; tsc/build verdes.
