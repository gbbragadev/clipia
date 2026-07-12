# 005 — Tokens CSS de motion + fim do `transition: all`

- **Status**: TODO
- **Commit**: 6428262
- **Severity**: MEDIUM (alto retorno — mecânico e amplo)
- **Category**: Cohesion & tokens (AUDIT seção 7) + Performance (seção 5) + Accessibility (seção 6)
- **Estimated scope**: 5 arquivos (`globals.css`, `editor.css`, `Navbar.tsx`, `GenerateForm.tsx`, `VideoCard.tsx`, `GlowCard.tsx`)

## Problema

O repo tem tokens de motion em JS (`lib/motion.ts`) mas **nenhum token CSS** — resultado: 8 curvas distintas espalhadas, a curva da marca `cubic-bezier(0.22, 1, 0.36, 1)` hardcoded 2× no editor.css, e `transition: all` em 11+ regras (anima propriedades não intencionais fora da GPU, inclusive em superfícies quentes como tabs e transport do editor). Há ainda: um toggle animando `left`, o hambúrguer animando `top`, `will-change` permanente, uma transição órfã do light theme morto e um hover com movimento sem gate de ponteiro (dispara em toque no mobile).

Locais (código atual verbatim):

```css
/* frontend/src/app/globals.css:52 — transição órfã (light theme foi aposentado; nada mais troca essas cores em runtime) */
body { ... transition: background 0.3s, color 0.3s; }
/* globals.css:67 — idem no ambient gradient */
body::before { ... transition: background 0.3s; }
/* globals.css:76 */  .card { ... transition: all 0.2s; }
/* globals.css:90 */  .btn-primary { ... transition: all 0.2s; }
/* globals.css:104 */ .btn-outline { ... transition: all 0.2s; }
/* globals.css:170-178 — will-change PERMANENTE (layer de compositor por elemento .reveal, dezenas na landing) */
.reveal { ... will-change: opacity, transform; }
```

```css
/* frontend/src/components/editor/editor.css — transition: all em superfícies quentes */
/* :56  */ .editor-header__icon-btn { ... transition: all 0.15s; }
/* :98  */ .editor-tools-panel { transition: flex-basis 0.25s cubic-bezier(0.4,0,0.2,1), opacity 0.2s ease; }
/* :109 */ .editor-panel-toggle { ... transition: all 0.2s; }
/* :124 */ .editor-tab { ... transition: all 0.15s; }
/* :169 */ .editor-timeline__scene { ... transition: all 0.12s; }
/* :197 */ .editor-timeline__transport-btn { ... transition: all 0.12s; }
/* :217 */ .editor-card { ... transition: all 0.15s ease; }
/* :238 */ .editor-color-swatch { ... transition: all 0.12s; }
/* :240 */ .editor-color-swatch:hover { transform: scale(1.1); }   /* sem gate (hover: hover) — tap no mobile dispara */
/* :254 */ .editor-btn-sm { ... transition: all 0.12s; }
/* :282 */ .export-panel__close { ... transition: background 0.15s cubic-bezier(0.22, 1, 0.36, 1), color 0.15s; }
/* :320 */ .export-download { ... transition: opacity 0.15s, transform 0.15s cubic-bezier(0.22, 1, 0.36, 1); }
```

```tsx
{/* frontend/src/components/Navbar.tsx:88-92 — hambúrguer anima `top` (layout) via transition-all */}
<span className="relative block h-4 w-5">
  <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 0, transform: open ? 'rotate(45deg)' : 'none' }} />
  <span className="absolute left-0 top-[7px] block h-0.5 w-5 bg-current transition-all" style={{ opacity: open ? 0 : 1 }} />
  <span className="absolute left-0 block h-0.5 w-5 bg-current transition-all" style={{ top: open ? 7 : 14, transform: open ? 'rotate(-45deg)' : 'none' }} />
</span>
```

```tsx
{/* frontend/src/components/dashboard/GenerateForm.tsx:490-497 — thumb do toggle anima `left` */}
<span
  className={`relative w-9 h-5 rounded-full transition shrink-0 ${item.on ? 'bg-coral' : 'bg-[var(--bg-surface-hover)]'}`}
>
  <span
    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
    style={{ left: item.on ? '18px' : '2px' }}
  />
</span>
```

```tsx
{/* frontend/src/components/dashboard/VideoCard.tsx:176 — hover decorativo de 500ms em item de lista */}
<span className="text-6xl opacity-30 group-hover:opacity-50 group-hover:scale-110 transition-all duration-500 z-10">{icon}</span>
```

```tsx
{/* frontend/src/components/ui/GlowCard.tsx:33 — transition-all no shell do card */}
className={`relative overflow-hidden rounded-2xl bg-[#16161d]/80 backdrop-blur-sm border border-white/5 transition-all duration-300 hover:border-white/10 ${className}`}
```

## Alvo

1. Tokens CSS no `@theme` do globals.css (espelham a convenção JS existente — `EASE` de `lib/motion.ts`):
   ```css
   --ease-out: cubic-bezier(0.22, 1, 0.36, 1);      /* curva da marca (= EASE do motion.ts); sobrescreve o ease-out default do Tailwind de propósito */
   --ease-gentle: cubic-bezier(0.2, 0.7, 0.2, 1);   /* já usada em .reveal/.anim-scene-fade — vira token */
   ```
2. Todo `transition: all` vira lista explícita das propriedades que realmente mudam.
3. Layout props (left/top) em micro-animações viram `transform`.
4. `will-change` do `.reveal` desligado após a revelação; transições órfãs do body removidas; hover com movimento ganha gate `(hover: hover) and (pointer: fine)`.

## Convenções do repo a seguir

- Curva da marca: `cubic-bezier(0.22, 1, 0.36, 1)` — exatamente a `EASE` de `frontend/src/lib/motion.ts:11`. NÃO inventar outra curva.
- Tokens Tailwind 4 vivem no bloco `@theme { ... }` de `frontend/src/app/globals.css:146-163` (junto com `--color-*`).
- Exemplar de transição bem escrita já no repo: `editor.css:282` (propriedades explícitas + curva forte) — o alvo é esse padrão em todo lugar, com a curva vinda do token.

## Passos

1. **`frontend/src/app/globals.css`** — no bloco `@theme` (linha 146), adicionar após os `--color-*`:
   ```css
   --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
   --ease-gentle: cubic-bezier(0.2, 0.7, 0.2, 1);
   ```
   (Se o plano 004 já tiver criado `--ease-out`, apenas conferir o valor e adicionar `--ease-gentle`.)
2. **globals.css:47-53 (body)** — remover a linha `transition: background 0.3s, color 0.3s;`. **globals.css:56-68 (body::before)** — remover a linha `transition: background 0.3s;`.
3. **globals.css:76 (.card)** — trocar `transition: all 0.2s;` por `transition: background-color 0.2s var(--ease-out), border-color 0.2s var(--ease-out);`.
4. **globals.css:90 (.btn-primary)** — trocar `transition: all 0.2s;` por `transition: opacity 0.2s var(--ease-out), transform 0.16s var(--ease-out);`. **globals.css:104 (.btn-outline)** — trocar por `transition: border-color 0.2s var(--ease-out), color 0.2s var(--ease-out), transform 0.16s var(--ease-out);` (o `transform` prepara o press feedback do plano 006 — inofensivo sozinho).
5. **globals.css:170-179 (.reveal)** — trocar as duas curvas `cubic-bezier(0.2, 0.7, 0.2, 1)` por `var(--ease-gentle)` e, após a regra `.reveal.in`, desligar a layer: 
   ```css
   .reveal.in { opacity: 1; transform: none; will-change: auto; }
   ```
   (editar a regra existente da linha 179 — acrescentar `will-change: auto;`).
6. **globals.css:221 (.anim-scene-fade)** — trocar `cubic-bezier(0.2, 0.7, 0.2, 1)` por `var(--ease-gentle)`.
7. **`frontend/src/components/editor/editor.css`** — substituições 1-para-1 (manter durações atuais; usar `var(--ease-out)` como curva):
   - `:56` `.editor-header__icon-btn` → `transition: color 0.15s var(--ease-out), background-color 0.15s var(--ease-out), opacity 0.15s var(--ease-out);`
   - `:98` `.editor-tools-panel` → trocar apenas `opacity 0.2s ease` por `opacity 0.2s var(--ease-out)` (o `flex-basis 0.25s` FICA — o colapso precisa redimensionar o player, tradeoff aceito; adicionar comentário acima da regra: `/* flex-basis é layout, mas o efeito exige redimensionar o player junto — deliberado, uso raro */`).
   - `:109` `.editor-panel-toggle` → `transition: color 0.2s var(--ease-out), background-color 0.2s var(--ease-out);`
   - `:124` `.editor-tab` → `transition: color 0.15s var(--ease-out), background-color 0.15s var(--ease-out), border-color 0.15s var(--ease-out);`
   - `:169` `.editor-timeline__scene` → `transition: filter 0.12s var(--ease-out), box-shadow 0.12s var(--ease-out);`
   - `:197` `.editor-timeline__transport-btn` → `transition: color 0.12s var(--ease-out), background-color 0.12s var(--ease-out);`
   - `:217` `.editor-card` → `transition: background-color 0.15s var(--ease-out), border-color 0.15s var(--ease-out);`
   - `:238` `.editor-color-swatch` → `transition: transform 0.12s var(--ease-out), border-color 0.12s var(--ease-out), box-shadow 0.12s var(--ease-out);`
   - `:240` — envolver o hover com gate de ponteiro:
     ```css
     @media (hover: hover) and (pointer: fine) {
       .editor-color-swatch:hover { transform: scale(1.1); }
     }
     ```
   - `:254` `.editor-btn-sm` → `transition: background-color 0.12s var(--ease-out), color 0.12s var(--ease-out), border-color 0.12s var(--ease-out);`
   - `:282` `.export-panel__close` → trocar `cubic-bezier(0.22, 1, 0.36, 1)` por `var(--ease-out)`.
   - `:320` `.export-download` → trocar `cubic-bezier(0.22, 1, 0.36, 1)` por `var(--ease-out)` e `opacity 0.15s` por `opacity 0.15s var(--ease-out)`.
8. **`frontend/src/components/Navbar.tsx:88-92`** — hambúrguer transform-only (top fixo por span, movimento via translateY; `transition-transform` e `transition-opacity` no lugar de `transition-all`):
   ```tsx
   <span className="relative block h-4 w-5">
     <span className="absolute left-0 top-0 block h-0.5 w-5 bg-current transition-transform duration-200" style={{ transform: open ? 'translateY(7px) rotate(45deg)' : 'none' }} />
     <span className="absolute left-0 top-[7px] block h-0.5 w-5 bg-current transition-opacity duration-200" style={{ opacity: open ? 0 : 1 }} />
     <span className="absolute left-0 top-[14px] block h-0.5 w-5 bg-current transition-transform duration-200" style={{ transform: open ? 'translateY(-7px) rotate(-45deg)' : 'none' }} />
   </span>
   ```
9. **`frontend/src/components/dashboard/GenerateForm.tsx:493-496`** — thumb do toggle via transform:
   ```tsx
   <span
     className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform duration-200"
     style={{ transform: item.on ? 'translateX(16px)' : 'translateX(0)' }}
   />
   ```
   (base `left-0.5` = 2px; ligado = 2px + 16px = 18px — posições finais idênticas às atuais.)
10. **`frontend/src/components/dashboard/VideoCard.tsx:176`** — trocar `transition-all duration-500` por `transition-[transform,opacity] duration-200` (hover de item de lista: rápido, propriedades explícitas).
11. **`frontend/src/components/ui/GlowCard.tsx:33`** — trocar `transition-all duration-300` por `transition-colors duration-300`.

## Limites

- NÃO alterar durações além das indicadas (o objetivo é curva/propriedade, não re-temporizar o app).
- NÃO mexer em `.anim-*` keyframes da landing (marquee, float, shimmer etc. estão corretos).
- NÃO tocar no `editor-tools-panel` além do especificado (o `flex-basis` fica).
- NÃO adicionar dependências.
- Se uma regra citada não bater com o código (drift desde 6428262), PARE e reporte.

## Verificação

- **Mecânica**: `cd frontend; npx next typegen; npx tsc --noEmit` limpo; `npm run build` verde. Grep de controle: `rg "transition: all" frontend/src` deve retornar ZERO resultados; `rg "transition-all" frontend/src` deve retornar apenas ocorrências que este plano não listou (se sobrar alguma inesperada em superfície quente, reportar).
- **Feel check**:
  - Hovers de cards/botões do dashboard e do editor continuam suaves (agora com a curva da marca — desaceleração perceptível no final em câmera lenta: DevTools → Animations → 10%).
  - Toggle SFX/Música do formulário desliza igual (2px ↔ 18px).
  - Hambúrguer mobile abre/fecha formando o X, sem pulo.
  - Num device touch (ou emulação), tocar num swatch de cor do editor NÃO deixa ele preso em scale(1.1).
- **Done when**: zero `transition: all` no src; tokens `--ease-out`/`--ease-gentle` no `@theme` e referenciados; visuais inalterados salvo curvas mais firmes; tsc/build verdes.
