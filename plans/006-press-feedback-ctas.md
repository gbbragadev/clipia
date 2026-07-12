# 006 — Press feedback nos CTAs (cobertura completa)

- **Status**: TODO
- **Commit**: 6428262
- **Severity**: MEDIUM
- **Category**: Physicality & origin (AUDIT seção 3)
- **Estimated scope**: 4 arquivos (`globals.css`, `editor.css`, `Navbar.tsx`, `GenerateForm.tsx`)

## Problema

Press feedback (`:active { scale(0.97) }`) existe em ALGUNS botões — `VideoCard.tsx:261/272/292` e `VideoPlayerModal.tsx` têm `active:scale-[0.97]` — mas os CTAs mais importantes do produto não afundam ao toque: o botão **Gerar vídeo** (ação principal), **Exportar** no editor, os botões de download/render do ExportPanel, os CTAs do Navbar e os botões compartilhados `.btn-primary`/`.btn-outline`. A regra do playbook: elementos pressáveis recebem `transform: scale(0.95–0.98)` no `:active` com `transition: transform ~160ms ease-out`. Cobertura inconsistente = produto que responde ao dedo em uma tela e ignora na outra.

Locais SEM press feedback (código atual):

```css
/* frontend/src/app/globals.css:84-97 — .btn-primary (hover tem translateY(-1px), sem :active) */
.btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
/* globals.css:99-108 — .btn-outline (sem :active) */
```

```css
/* frontend/src/components/editor/editor.css:47-52 — botão Exportar do header */
.editor-header__export { ... transition: opacity 0.15s; }
.editor-header__export:hover { opacity: 0.9; }
/* editor.css:250-256 — .editor-btn-sm (sem :active) */
/* editor.css:315-323 — .export-download (transition já inclui transform, sem :active) */
/* editor.css:299-303 — .export-status__retry (sem transition nem :active) */
/* editor.css:333-337 — .export-stale__btn (sem transition nem :active) */
```

```tsx
{/* frontend/src/components/Navbar.tsx:63-69 e 72-75 — CTAs Dashboard/Login (classe `transition` já cobre transform) */}
className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-coral to-azure text-white text-sm font-medium hover:opacity-90 transition"
{/* Navbar.tsx:119-126 — CTAs do menu mobile (sem transition) */}
```

```tsx
{/* frontend/src/components/dashboard/GenerateForm.tsx:682-689 — CTA principal "Gerar" */}
<button
  onClick={handleGenerate}
  disabled={generating || !canSubmit}
  className={`w-full py-3.5 rounded-xl border-none text-base font-semibold transition cursor-pointer ${
    generating || !canSubmit
      ? 'bg-[var(--bg-surface-hover)] text-[var(--text-tertiary)] cursor-not-allowed'
      : 'bg-gradient-to-r from-coral to-azure text-white hover:opacity-90'
  }`}
```

## Alvo

Todo botão de ação afunda para `scale(0.97)` quando pressionado (0.95 nos ícones pequenos do transport), com `transition: transform 160ms` na curva da marca. Botões `disabled` NÃO afundam. Sutil — nunca abaixo de 0.95.

## Convenções do repo a seguir

- **Exemplar do repo**: `frontend/src/components/dashboard/VideoCard.tsx:261` — `... active:scale-[0.97] transition` (Tailwind). Imitar esse padrão em TSX.
- Em CSS vanilla (globals/editor.css), usar `var(--ease-out)`. Se o token não existir ainda no `@theme` de `globals.css` (criado pelos planos 004/005), adicionar: `--ease-out: cubic-bezier(0.22, 1, 0.36, 1);`.
- Tailwind: a classe `transition` (sem sufixo) já transiciona `transform`; onde só houver `transition-colors`, usar `transition-[color,background-color,transform]` ou adicionar `transition` genérica.

## Passos

1. **`frontend/src/app/globals.css`** — adicionar após a regra `.btn-primary:hover` (linha 97):
   ```css
   .btn-primary:active { transform: translateY(0) scale(0.97); }
   ```
   e após `.btn-outline:hover` (linha 108):
   ```css
   .btn-outline:active { transform: scale(0.97); }
   ```
   Pré-requisito: as listas de `transition` desses dois botões precisam incluir `transform 0.16s var(--ease-out)` — o plano 005 já faz isso; se 005 ainda não rodou, trocar aqui `transition: all 0.2s;` por `transition: opacity 0.2s var(--ease-out), transform 0.16s var(--ease-out);` (btn-primary) e `transition: border-color 0.2s var(--ease-out), color 0.2s var(--ease-out), transform 0.16s var(--ease-out);` (btn-outline).
2. **`frontend/src/components/editor/editor.css`**:
   - `.editor-header__export` (linha ~50): trocar `transition: opacity 0.15s;` por `transition: opacity 0.15s var(--ease-out), transform 0.16s var(--ease-out);` e adicionar após o `:hover`:
     ```css
     .editor-header__export:active { transform: scale(0.97); }
     ```
   - `.editor-btn-sm`: acrescentar `transform 0.16s var(--ease-out)` à lista de transition e:
     ```css
     .editor-btn-sm:active { transform: scale(0.97); }
     ```
   - `.export-download` (transition de transform já existe): adicionar:
     ```css
     .export-download:active:not(:disabled) { transform: scale(0.97); }
     ```
   - `.export-status__retry` e `.export-stale__btn`: adicionar `transition: transform 0.16s var(--ease-out);` na regra base e:
     ```css
     .export-status__retry:active, .export-stale__btn:active { transform: scale(0.97); }
     ```
   - `.editor-timeline__transport-btn`: acrescentar `transform 0.12s var(--ease-out)` à transition e:
     ```css
     .editor-timeline__transport-btn:active { transform: scale(0.95); }
     ```
   - `.editor-header__icon-btn` (undo/redo mobile): acrescentar `transform 0.16s var(--ease-out)` à transition e:
     ```css
     .editor-header__icon-btn:active:not(:disabled) { transform: scale(0.95); }
     ```
3. **`frontend/src/components/Navbar.tsx`** — adicionar `active:scale-[0.97]` à className dos 4 CTAs (linhas 63-69, 72-75, 119-121, 124-126). Nos dois do menu mobile (119/124), que não têm `transition`, adicionar também a classe `transition`.
4. **`frontend/src/components/dashboard/GenerateForm.tsx:682-689`** — no CTA principal, adicionar `enabled:active:scale-[0.98]` à className base (fora do ternário — `enabled:` garante que desabilitado não afunda). No botão "Gerar rascunho do roteiro (grátis)" (linha ~526-533), adicionar `active:scale-[0.98]`.

## Limites

- NÃO adicionar press feedback a: tabs do editor (largura total — scale fica estranho), links de navegação puros, itens de lista.
- NÃO mexer em `whileTap`/motion — este plano é 100% CSS/classes.
- NÃO passar de scale(0.95) em nenhum caso.
- Se uma regra citada não bater com o código (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde.
- **Feel check**:
  - Segurar o clique no CTA "Gerar" (habilitado): afunda a 0.98 e volta ao soltar, com resposta imediata (~160ms).
  - CTA desabilitado (sem tema): NÃO afunda.
  - "Exportar" no editor, play/pause do transport, undo/redo mobile: todos afundam sutilmente.
  - DevTools → Animations a 10%: o afundar usa a curva da marca (desacelera no final), não linear.
  - Comparar com os botões do VideoCard (referência pré-existente): mesma sensação.
- **Done when**: todo CTA de ação do app afunda ao pressionar (disabled não), uniforme com o exemplar do VideoCard; tsc/build verdes.
