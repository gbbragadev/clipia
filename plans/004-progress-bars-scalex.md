# 004 — Barras de progresso: `scaleX` em vez de `width`

- **Status**: TODO
- **Commit**: 6428262
- **Severity**: MEDIUM
- **Category**: Performance (AUDIT seção 5)
- **Estimated scope**: 4 arquivos (`ScrollProgress.tsx`, `VideoCard.tsx`, `VideoPlayerModal.tsx`, `ExportPanel.tsx` + `editor.css`)

## Problema

Quatro barras de progresso animam `width` (propriedade de layout — reflow + paint a cada update). A pior é a `ScrollProgress`, que atualiza **a cada evento de scroll** em todas as páginas com Navbar. A do VideoCard ainda usa `transition-all` (anima propriedades não intencionais). A regra: animar só `transform`/`opacity` — para barras de preenchimento, `transform: scaleX(p)` com `transform-origin: left`.

Nota visual: `scaleX` comprime o gradiente do fill, mas `width` também renderiza o gradiente inteiro dentro da largura atual — o resultado visual é o mesmo. Os cantos `rounded-full` distorcem de forma imperceptível em barras de 1-4px de altura.

**1. `frontend/src/components/ScrollProgress.tsx:6-13`** (contínua no scroll — a mais quente):

```tsx
// atual
return (
  <div className="h-[2px] bg-gray-900">
    <div
      className="h-full bg-gradient-to-r from-coral via-coral-soft to-azure transition-[width] duration-100"
      style={{ width: `${progress * 100}%` }}
    />
  </div>
)
```

**2. `frontend/src/components/dashboard/VideoCard.tsx:246-251`** (progresso da geração, atualiza por polling; usuário olha durante ~2min):

```tsx
// atual
<div className="h-1 rounded-full overflow-hidden bg-white/10">
  <div
    className="h-full rounded-full bg-gradient-to-r from-coral to-azure transition-all duration-500 ease-out"
    style={{ width: `${Math.max(4, (job.progress ?? 0) * 100)}%` }}
  />
</div>
```

**3. `frontend/src/components/dashboard/VideoPlayerModal.tsx:167-172`** (progresso de carregamento do vídeo):

```tsx
// atual
<div className="h-1 w-40 overflow-hidden rounded-full bg-white/10">
  <div
    className="h-full rounded-full bg-gradient-to-r from-coral to-azure transition-all duration-300"
    style={{ width: `${Math.max(4, loadProgress * 100)}%` }}
  />
</div>
```

**4. `frontend/src/components/editor/ExportPanel.tsx:258-260` + `frontend/src/components/editor/editor.css:305-313`** (progresso do render de export):

```tsx
// ExportPanel.tsx:259 — atual
<div className="export-progress__fill" style={{ width: `${Math.max(6, renderProgress * 100)}%` }} />
```
```css
/* editor.css:309-313 — atual */
.export-progress__fill {
  height: 100%; border-radius: 999px;
  background: linear-gradient(90deg, var(--color-coral), var(--color-azure, #3e9bff));
  transition: width 0.5s ease-out;
}
```

## Alvo

Todos os fills: largura fixa `100%`, `transform: scaleX(fração)` (0–1), `transform-origin: left`, transition em `transform` com a duração que cada um já tinha (500ms no VideoCard/export é deliberado — interpola os saltos do polling; 100ms linear no scroll; 300ms no load). Os floors `Math.max(4|6, %)` viram frações: `Math.max(0.04, p)` / `Math.max(0.06, p)`.

## Convenções do repo a seguir

- Tailwind CSS 4: usar utilities `origin-left`, `transition-transform`, `duration-*`, `w-full`.
- Token CSS de curva: se `--ease-out` ainda NÃO existir no `@theme` de `frontend/src/app/globals.css`, adicionar lá:
  ```css
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  ```
  (é a mesma curva do `EASE` de `frontend/src/lib/motion.ts` — o plano 005 também a cria; criar apenas se ausente.)

## Passos

1. **`frontend/src/components/ScrollProgress.tsx`** — trocar o fill por:
   ```tsx
   <div
     className="h-full w-full origin-left bg-gradient-to-r from-coral via-coral-soft to-azure transition-transform duration-100 ease-linear"
     style={{ transform: `scaleX(${progress})` }}
   />
   ```
2. **`frontend/src/components/dashboard/VideoCard.tsx:246-251`** — trocar o fill por:
   ```tsx
   <div
     className="h-full w-full origin-left rounded-full bg-gradient-to-r from-coral to-azure transition-transform duration-500 ease-out"
     style={{ transform: `scaleX(${Math.max(0.04, job.progress ?? 0)})` }}
   />
   ```
3. **`frontend/src/components/dashboard/VideoPlayerModal.tsx:167-172`** — trocar o fill por:
   ```tsx
   <div
     className="h-full w-full origin-left rounded-full bg-gradient-to-r from-coral to-azure transition-transform duration-300"
     style={{ transform: `scaleX(${Math.max(0.04, loadProgress)})` }}
   />
   ```
4. **`frontend/src/components/editor/ExportPanel.tsx:259`** — trocar por:
   ```tsx
   <div className="export-progress__fill" style={{ transform: `scaleX(${Math.max(0.06, renderProgress)})` }} />
   ```
5. **`frontend/src/components/editor/editor.css:309-313`** — trocar a regra por:
   ```css
   .export-progress__fill {
     height: 100%; width: 100%; border-radius: 999px;
     background: linear-gradient(90deg, var(--color-coral), var(--color-azure, #3e9bff));
     transform-origin: left;
     transition: transform 0.5s var(--ease-out, ease-out);
   }
   ```

## Limites

- NÃO mudar cores, alturas, gradientes nem os containers das barras.
- NÃO mudar a fonte dos valores de progresso (hooks/polling).
- NÃO adicionar dependências.
- Se o código encontrado divergir do citado (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Rolar a landing: a barra fina do topo acompanha o scroll com a mesma suavidade de antes.
  - Gerar um vídeo: a barra do card avança suave entre os ticks do polling (interpolação de ~500ms preservada) e nunca fica vazia (floor 4%).
  - Exportar no editor: a barra do modal avança; em 100% preenche até a borda direita.
  - DevTools → Rendering → Paint flashing: rolar a página NÃO deve piscar a barra da navbar a cada frame (antes piscava).
- **Done when**: as 4 barras visualmente idênticas às anteriores (floors inclusos), sem reflow por update; tsc/build verdes.
