# 007 — GenerateForm: transições nas mudanças de estado (roteiro avançado + modo lote)

- **Status**: TODO
- **Commit**: 6428262
- **Severity**: MEDIUM
- **Category**: Missed opportunities (AUDIT seção 8)
- **Estimated scope**: 1 arquivo (`frontend/src/components/dashboard/GenerateForm.tsx`)

## Problema

Duas mudanças de estado no formulário principal **teletransportam** a UI (jarring change que uma transição breve evitaria):

**1. Disclosure "Roteiro avançado" (`GenerateForm.tsx:504-519`)** — o chevron até gira animado (`transition-transform`), mas o painel que ele controla aparece/some seco, empurrando o formulário inteiro:

```tsx
{/* atual — :512 (chevron, JÁ animado, manter) e :518-519 (painel seco) */}
<span className="transition-transform" style={{ transform: showAdvancedScript ? 'rotate(90deg)' : 'rotate(0deg)' }}>
  ▶
</span>
...
{showAdvancedScript && (
  <div className="mt-3 space-y-4">
```

**2. Troca single ↔ lote (`GenerateForm.tsx:310-344`)** — clicar "Gerar vários de uma vez" troca `<input>` (1 linha) por `<textarea rows={5}>` instantaneamente; o bloco muda de altura num frame:

```tsx
{/* atual — :310-311 e :326-328 */}
{batchMode ? (
  <>
    <textarea
      value={batchTopics}
      ...
  </>
) : (
  <>
    <input
      type="text"
      value={topic}
      ...
  </>
)}
```

## Alvo

- Disclosure: expande/colapsa com `height: 0 ↔ auto` + fade via motion (AnimatePresence). Height é layout, mas disclosure de formulário é interação ocasional e o conteúdo tem altura desconhecida — é o caso aceito; a duração `DURATIONS.normal` (0.32s) com `EASE` cobre o painel alto.
- Troca de modo: o bloco que ENTRA faz fade+rise curto (`opacity: 0, y: 4` → `1, 0` em 0.18s). Sem `mode="wait"` (esperaria a saída e dobraria a latência) — o que sai desmonta direto; o fade de entrada já elimina a sensação de teleporte.
- Reduced-motion: sem animação (comportamento atual).

## Convenções do repo a seguir

- Tokens JS: `frontend/src/lib/motion.ts` — `EASE`, `DURATIONS`, `useReducedMotionState`.
- Lib: `motion/react`. O GenerateForm ainda NÃO importa motion — adicionar imports.
- Exemplar de AnimatePresence com reduced-motion: `frontend/src/components/editor/EditorLayout.tsx:173-203`.

## Passos

1. Adicionar imports no topo do `GenerateForm.tsx`:
   ```tsx
   import { AnimatePresence, motion } from 'motion/react'
   import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
   ```
   e dentro do componente: `const reduceMotion = useReducedMotionState()`.
2. **Disclosure (linhas 518+)** — trocar `{showAdvancedScript && (<div className="mt-3 space-y-4"> ... </div>)}` por:
   ```tsx
   <AnimatePresence initial={false}>
     {showAdvancedScript && (
       <motion.div
         key="advanced-script"
         initial={reduceMotion ? false : { height: 0, opacity: 0 }}
         animate={{ height: 'auto', opacity: 1 }}
         exit={reduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
         transition={{ duration: DURATIONS.normal, ease: EASE }}
         style={{ overflow: 'hidden' }}
       >
         <div className="mt-3 space-y-4">
           {/* conteúdo interno EXATAMENTE como está hoje */}
         </div>
       </motion.div>
     )}
   </AnimatePresence>
   ```
   IMPORTANTE: o `mt-3` fica no div INTERNO (margens fora do clip de height causam pulo no início/fim da animação).
3. **Troca de modo (linhas 310-344)** — envolver o conteúdo de cada ramo num `motion.div` com key própria (sem AnimatePresence — só fade-in de quem entra):
   ```tsx
   {batchMode ? (
     <motion.div
       key="topic-batch"
       initial={reduceMotion ? false : { opacity: 0, y: 4 }}
       animate={{ opacity: 1, y: 0 }}
       transition={{ duration: DURATIONS.fast, ease: EASE }}
     >
       {/* textarea + <p> do contador, exatamente como estão */}
     </motion.div>
   ) : (
     <motion.div
       key="topic-single"
       initial={reduceMotion ? false : { opacity: 0, y: 4 }}
       animate={{ opacity: 1, y: 0 }}
       transition={{ duration: DURATIONS.fast, ease: EASE }}
     >
       {/* input + span do trendContext, exatamente como estão */}
     </motion.div>
   )}
   ```
   (Os fragments `<>...</>` atuais viram esses `motion.div`. `initial` roda porque a key muda a cada troca de modo.)

## Limites

- NÃO mudar nenhuma lógica do form (draft, débito, validação, batchList, handlers).
- NÃO animar o resto do formulário (template selector, toggles etc.).
- NÃO usar `mode="wait"` (latência dobrada em interação frequente).
- NÃO adicionar dependências.
- Se o código divergir do citado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Clicar "Roteiro avançado": o painel desliza aberto em sincronia com o giro do chevron; clicar de novo recolhe. Spam de cliques: a animação reverte do ponto atual, sem restart.
  - Clicar "Gerar vários de uma vez": o textarea surge com fade+rise sutil (~180ms); voltar idem. Nada pisca.
  - Digitar no textarea/input após a troca: foco e valor preservados.
  - DevTools → Rendering → `prefers-reduced-motion: reduce`: trocas viram instantâneas/fade leve, sem movimento.
- **Done when**: as duas mudanças de estado têm continuidade visual, sem alterar comportamento do form; tsc/build verdes.
