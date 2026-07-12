# 003 — Playhead das timelines: animar transform, não `left`

- **Status**: DONE (executado por GPT-5.6 Sol via cgpt em 2026-07-12; gate Opus: APROVADO sem findings; tsc verde)
- **Commit**: 6428262
- **Severity**: HIGH
- **Category**: Performance (AUDIT seção 5)
- **Estimated scope**: 3 arquivos (`editor.css`, `EditorTimeline.tsx`, `SceneTimeline.tsx`)

## Problema

Os dois playheads do editor são posicionados com `left: N%` e têm `transition: left` — `left` é propriedade de **layout**: cada atualização dispara layout + paint. Durante o playback, o `playerFrame` atualiza por polling a cada 100ms, ou seja, o container da timeline sofre layout thrash ~10×/segundo **durante todo o playback** — a superfície mais quente do produto. A regra: animar apenas `transform` e `opacity`.

**1. `frontend/src/components/editor/editor.css:176-181`**:

```css
/* atual */
.editor-timeline__playhead {
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: var(--color-azure); box-shadow: 0 0 6px rgba(62,155,255,0.5);
  border-radius: 1px; pointer-events: none; z-index: 5;
  transition: left 0.08s linear;
}
```

**2. `frontend/src/components/editor/EditorTimeline.tsx:79-83`**:

```tsx
{/* atual */}
{/* Playhead */}
<div
  className="editor-timeline__playhead"
  style={{ left: `${playheadPercent}%` }}
/>
```

**3. `frontend/src/components/editor/SceneTimeline.tsx:56-67`**:

```tsx
{/* atual */}
{/* Playhead indicator */}
<div style={{
  position: 'absolute', top: 0, bottom: 0,
  left: `${playheadPercent}%`,
  width: 2,
  background: 'white',
  boxShadow: '0 0 6px rgba(255,255,255,0.5)',
  borderRadius: 1,
  pointerEvents: 'none',
  transition: 'left 0.05s linear',
  opacity: playheadPercent > 0 ? 0.8 : 0,
}} />
```

## Alvo

Técnica do **trilho** (track): um wrapper absoluto cobrindo o container inteiro (`inset: 0`), transladado com `transform: translateX(N%)` — em `%`, `translateX` é relativo à largura do PRÓPRIO elemento, e como o trilho tem 100% da largura do container, `translateX(37%)` = 37% do container, mesmo resultado visual do `left: 37%` atual. O risquinho de 2px fica como filho na borda esquerda do trilho. `transition: transform ... linear` (linear é a curva correta para motion constante de playback). Resultado: só composite, zero layout.

## Convenções do repo a seguir

- CSS do editor em `frontend/src/components/editor/editor.css`, classes BEM-like `editor-timeline__*`.
- O container `.editor-timeline__scenes` já é `position: relative` (editor.css:161-165) — o trilho ancora nele. No `SceneTimeline.tsx` o container do playhead também é `position: relative` (verificar o wrapper imediato no arquivo).

## Passos

1. **`frontend/src/components/editor/editor.css:176-181`** — substituir o bloco `.editor-timeline__playhead` por:
   ```css
   /* Trilho do playhead: cobre o container e translada em % da própria largura
      (= % do container). transform em vez de left: só composite, zero layout. */
   .editor-timeline__playhead-track {
     position: absolute; inset: 0;
     pointer-events: none; z-index: 5;
     transition: transform 0.1s linear;
     will-change: transform;
   }
   .editor-timeline__playhead {
     position: absolute; top: 0; bottom: 0; left: -1px; width: 2px;
     background: var(--color-azure); box-shadow: 0 0 6px rgba(62,155,255,0.5);
     border-radius: 1px; pointer-events: none;
   }
   ```
   (O bloco `.editor-timeline__playhead::before` das linhas 182-187 — a bolinha — permanece exatamente como está: continua ancorado no risco.)
2. **`frontend/src/components/editor/EditorTimeline.tsx:79-83`** — trocar por:
   ```tsx
   {/* Playhead */}
   <div
     className="editor-timeline__playhead-track"
     style={{ transform: `translateX(${playheadPercent}%)` }}
   >
     <div className="editor-timeline__playhead" />
   </div>
   ```
3. **`frontend/src/components/editor/SceneTimeline.tsx:56-67`** — trocar por (inline styles, seguindo o estilo do arquivo):
   ```tsx
   {/* Playhead indicator */}
   <div style={{
     position: 'absolute', inset: 0,
     pointerEvents: 'none',
     transform: `translateX(${playheadPercent}%)`,
     transition: 'transform 0.05s linear',
     opacity: playheadPercent > 0 ? 0.8 : 0,
   }}>
     <div style={{
       position: 'absolute', top: 0, bottom: 0, left: -1, width: 2,
       background: 'white',
       boxShadow: '0 0 6px rgba(255,255,255,0.5)',
       borderRadius: 1,
     }} />
   </div>
   ```

## Limites

- NÃO mexer no polling do `playerFrame`, no `EditorContext` nem na lógica de seek/click — só o posicionamento visual do playhead.
- NÃO mudar os blocos de cena, ruler, transport nem o `::before` (bolinha).
- NÃO adicionar dependências.
- Se o código encontrado divergir do citado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Abrir um job no editor, dar play: o playhead desliza suave pela timeline, na MESMA posição visual de antes (comparar com um vídeo de referência se necessário: início, meio, fim — em 100% deve encostar na borda direita do trilho útil).
  - Clicar em pontos da área de cenas (seek): o playhead vai ao ponto clicado.
  - DevTools → Performance: gravar 5s de playback; no track principal NÃO deve haver eventos "Layout" recorrentes a cada ~100ms vindos da timeline (antes havia). Alternativa: Rendering → Paint flashing — a área da timeline não deve piscar inteira a cada tick.
  - Repetir na aba Cenas (SceneTimeline) com o preview tocando.
- **Done when**: playhead visualmente idêntico ao anterior em início/meio/fim, sem layout recorrente no Performance durante playback; tsc/build verdes.
