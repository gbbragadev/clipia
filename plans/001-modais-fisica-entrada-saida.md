# 001 — Dar física de entrada/saída aos modais (Modal base, ExportPanel, VideoPlayerModal)

- **Status**: DONE (2026-07-12; passos 1-2 pelo executor GPT-5.6 Sol/cgpt — processo morto 2×, passos 3-5 completados pelo orquestrador Fable conforme fallback do plano de execução; gate Opus: APROVADO em tudo; tsc verde)
- **Commit**: 6428262
- **Severity**: HIGH
- **Category**: Physicality & origin + Interruptibility (AUDIT seções 3–4)
- **Estimated scope**: 4 arquivos (`Modal.tsx`, `ExportPanel.tsx`, `EditorLayout.tsx`, `VideoPlayerModal.tsx` + 1 linha em `VideoCard.tsx`)

## Problema

Os três overlays centrais do produto aparecem e somem **instantaneamente** (montagem/desmontagem seca), sem nenhuma transição. Modais confirmam ações **pagas e destrutivas** — o pop seco parece bug e barateia a percepção de qualidade. Nada no mundo real surge do nada: a entrada correta é `scale 0.96 → 1` + fade (nunca `scale(0)`), e a saída é o reverso.

**1. `frontend/src/components/ui/Modal.tsx:65-90`** — o modal compartilhado (usado por GenerateForm, VoiceSelector, AIAssistant, ResetEditorButton) retorna `null` e monta seco:

```tsx
// frontend/src/components/ui/Modal.tsx:65-90 — atual
if (!open || typeof document === 'undefined') return null

return createPortal(
  <div
    className="fixed inset-0 z-[90] flex items-center justify-center p-4"
    onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose()
    }}
    style={{ background: 'var(--overlay-bg)' }}
  >
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
      tabIndex={-1}
      className={cn(
        'w-full max-w-sm rounded-2xl border border-white/10 bg-[var(--bg-raised)] p-6 shadow-2xl outline-none',
        className
      )}
    >
      {children}
    </div>
  </div>,
  document.body
)
```

Todos os 5 call sites já renderizam `<Modal open={...}>` incondicionalmente (`GenerateForm.tsx:719` e `:758`, `VoiceSelector.tsx:418`, `AIAssistant.tsx:443`, `ResetEditorButton.tsx:54`) — **nenhum call site precisa mudar**; a animação vive inteira dentro do Modal.

**2. `frontend/src/components/editor/ExportPanel.tsx:202-204`** — o modal de export monta seco (o call site `frontend/src/components/editor/EditorLayout.tsx:207` é `{showExport && <ExportPanel onClose={...} />}`):

```tsx
// frontend/src/components/editor/ExportPanel.tsx:202-204 — atual
return (
  <div className="export-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
    <div className="export-panel" role="dialog" aria-modal="true" aria-label="Exportar vídeo">
```

**3. `frontend/src/components/dashboard/VideoPlayerModal.tsx:107-120`** — a entrada está correta (scale 0.96 + fade + reduced-motion ✓), mas não há `exit` nem `AnimatePresence` — fechar pufa; e o backdrop (div comum) nem fade de entrada tem:

```tsx
// frontend/src/components/dashboard/VideoPlayerModal.tsx:107-120 — atual
return createPortal(
  <div
    className="fixed inset-0 z-[90] flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-label={`Assistir: ${job.topic}`}
    onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
  >
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: DURATIONS.fast, ease: EASE }}
```

Call site: `frontend/src/components/dashboard/VideoCard.tsx:329-331`:

```tsx
{showPlayer && (
  <VideoPlayerModal job={job} onClose={() => setShowPlayer(false)} onEdit={onEdit} />
)}
```

## Alvo

Todos os overlays: backdrop com fade (`opacity 0 → 1`), painel com `opacity: 0, scale: 0.96, y: 8 → opacity: 1, scale: 1, y: 0`, exit reverso, duração `DURATIONS.fast` (0.18s) e curva `EASE` (`[0.22, 1, 0.36, 1]`) dos tokens do repo. Com `prefers-reduced-motion`: `initial: false` (sem animação de entrada) e exit só com `{ opacity: 0 }`. Modais são centrados — `transform-origin` center é o correto aqui, não mexer.

## Convenções do repo a seguir

- Tokens JS de motion: `frontend/src/lib/motion.ts` — importar `EASE`, `DURATIONS`, `useReducedMotionState`.
- Lib de animação: `motion` v12, importada como `motion/react` (`AnimatePresence`, `motion.div`).
- **Exemplar de entrada correta**: `frontend/src/components/dashboard/VideoPlayerModal.tsx:115-118`.
- **Exemplar de AnimatePresence com reduced-motion**: `frontend/src/components/editor/EditorLayout.tsx:173-203` (gaveta da timeline).

## Passos

1. **`frontend/src/components/ui/Modal.tsx`** — adicionar imports:
   ```tsx
   import { AnimatePresence, motion } from 'motion/react'
   import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
   ```
   Dentro do componente, adicionar `const reduceMotion = useReducedMotionState()`. Trocar o early-return e o retorno por (mantendo o `useEffect` de foco/Esc/scroll-lock EXATAMENTE como está — ele já depende de `open`):
   ```tsx
   if (typeof document === 'undefined') return null

   return createPortal(
     <AnimatePresence>
       {open && (
         <motion.div
           key="modal-overlay"
           className="fixed inset-0 z-[90] flex items-center justify-center p-4"
           initial={reduceMotion ? false : { opacity: 0 }}
           animate={{ opacity: 1 }}
           exit={{ opacity: 0 }}
           transition={{ duration: DURATIONS.fast, ease: EASE }}
           onMouseDown={(e) => {
             if (e.target === e.currentTarget) onClose()
           }}
           style={{ background: 'var(--overlay-bg)' }}
         >
           <motion.div
             ref={panelRef}
             role="dialog"
             aria-modal="true"
             aria-labelledby={labelledBy}
             tabIndex={-1}
             initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
             animate={{ opacity: 1, scale: 1, y: 0 }}
             exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
             transition={{ duration: DURATIONS.fast, ease: EASE }}
             className={cn(
               'w-full max-w-sm rounded-2xl border border-white/10 bg-[var(--bg-raised)] p-6 shadow-2xl outline-none',
               className
             )}
           >
             {children}
           </motion.div>
         </motion.div>
       )}
     </AnimatePresence>,
     document.body
   )
   ```
2. **`frontend/src/components/editor/EditorLayout.tsx:207`** — envolver o ExportPanel com AnimatePresence (o import de `AnimatePresence` já existe na linha 4):
   ```tsx
   <AnimatePresence>
     {showExport && <ExportPanel onClose={() => setShowExport(false)} />}
   </AnimatePresence>
   ```
3. **`frontend/src/components/editor/ExportPanel.tsx`** — adicionar imports `motion` (de `motion/react`) e `EASE, DURATIONS, useReducedMotionState` (de `@/lib/motion`); adicionar `const reduceMotion = useReducedMotionState()` no topo do componente; trocar o return (linhas 202-204) para:
   ```tsx
   return (
     <motion.div
       className="export-overlay"
       initial={reduceMotion ? false : { opacity: 0 }}
       animate={{ opacity: 1 }}
       exit={{ opacity: 0 }}
       transition={{ duration: DURATIONS.fast, ease: EASE }}
       onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
     >
       <motion.div
         className="export-panel"
         role="dialog"
         aria-modal="true"
         aria-label="Exportar vídeo"
         initial={reduceMotion ? false : { opacity: 0, scale: 0.96, y: 8 }}
         animate={{ opacity: 1, scale: 1, y: 0 }}
         exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
         transition={{ duration: DURATIONS.fast, ease: EASE }}
       >
   ```
   (fechar com `</motion.div></motion.div>` no lugar dos `</div></div>` correspondentes do final do return).
4. **`frontend/src/components/dashboard/VideoCard.tsx:329-331`** — envolver com AnimatePresence (adicionar `import { AnimatePresence } from 'motion/react'`):
   ```tsx
   <AnimatePresence>
     {showPlayer && (
       <VideoPlayerModal job={job} onClose={() => setShowPlayer(false)} onEdit={onEdit} />
     )}
   </AnimatePresence>
   ```
5. **`frontend/src/components/dashboard/VideoPlayerModal.tsx:107-120`** — transformar o div do backdrop em `motion.div` com fade (`initial={reduceMotion ? false : { opacity: 0 }}`, `animate={{ opacity: 1 }}`, `exit={{ opacity: 0 }}`, `transition={{ duration: DURATIONS.fast, ease: EASE }}`) e adicionar ao `motion.div` do painel a prop:
   ```tsx
   exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
   ```

## Limites

- NÃO tocar no focus trap, no scroll-lock nem na lógica de Esc/clique-fora do Modal — só a camada visual.
- NÃO animar o conteúdo interno dos modais (children ficam como estão).
- NÃO adicionar dependências novas (motion já está instalado).
- NÃO mudar os 5 call sites do `<Modal>` — a animação é interna.
- Se algum trecho não bater com o código encontrado (drift desde o commit 6428262), PARE e reporte em vez de improvisar.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` sem erros novos; `npm run build` verde.
- **Feel check** (rodar o app e olhar):
  - Abrir a confirmação de reset no editor: o painel cresce de 0.96 para 1 com fade (~180ms); fechar reverte — nada pufa.
  - Abrir/fechar o modal em sequência rápida (spam de clique): nunca "pisca" nem reinicia visivelmente do zero.
  - Player do dashboard: fechar agora tem fade+scale de saída; o backdrop escurece/clareia junto.
  - DevTools → Rendering → emular `prefers-reduced-motion: reduce`: modais viram fade puro, sem movimento.
  - Após fechar com Tab preso dentro do modal, o foco volta ao elemento que o abriu (comportamento pré-existente intacto).
- **Done when**: os 3 overlays entram com scale 0.96→1 + fade e saem com o reverso; tsc/build verdes; reduced-motion vira fade puro.
