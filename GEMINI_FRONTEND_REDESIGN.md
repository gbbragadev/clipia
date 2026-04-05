# ClipIA — Frontend Redesign: De Generico para Memoravel

## Missao

O ClipIA tem um frontend funcional 8/10, mas **generico**. Parece todo SaaS de IA: gradiente roxo, cards arredondados, "Crie X com IA". O objetivo e transformar numa experiencia visual que faz alguem pausar e pensar "isso e diferente".

O diferencial tecnico ja existe: **Pretext** (`@chenglou/pretext`) — uma engine de tipografia em Canvas que faz animacoes de texto em tempo real (karaoke sweep, typewriter, blur-to-focus, scale pop). 9 componentes ja usam. O problema e que o design ao redor nao esta a altura da tecnologia.

**Nao quero um redesign de SaaS generico. Quero algo que pareca um produto de video — cinematico, com movimento, que respira.**

---

## Stack

- Next.js 16 + React 19 (App Router, "use client" para interatividade)
- Tailwind CSS 4 (utility-first, dark theme por padrao)
- @chenglou/pretext (tipografia Canvas — `prepareWithSegments`, `layoutWithLines`, `layoutNextLine`)
- Fonts: Inter (body), Space Grotesk (display, weight 500/700)
- Cores atuais: purple-600 (#7c3aed) primaria, slate para neutros, dark bg (#0f0b1a)
- Nenhuma lib de animacao (tudo custom CSS/Canvas — manter assim, nao adicionar framer-motion ou GSAP)

## Estrutura atual

```
Landing (/)
├── HeroSection — titulo + PretextCanvas (legendas ao vivo) + VideoShowcase (phone mockup)
├── SocialProofBar — numeros/metricas
├── ShowcaseSection — 3 cards de video com ShowcasePretextOverlay
├── DemoSection — demo interativa de geracao
├── HowItWorks — 3 steps com HowItWorksStepCanvas
├── WaitlistForm — formulario (deveria ser CTA de registro)
└── Footer

Dashboard (/dashboard)
├── DashboardNavbar — logo, CreditsBadge, UserDropdown
├── GenerateForm — form de geracao com TemplateSelector, StyleSelector, WpmSlider, previews tipograficos
├── VideoGrid — grid de videos gerados (VideoCard)
└── Banner de verificacao (se email nao verificado)

Editor (/editor/[jobId])
├── EditorLayout — 5 abas (Cenas, Voz, Legendas, Elementos, IA)
├── RemotionPreview — player 9:16
├── ScriptEditor, SubtitleEditor, VoiceSelector, etc
└── ExportPanel
```

## Componentes Pretext existentes (9)
- `PretextCanvas` — 4 modos animados (karaoke, typewriter, blur, pop) no hero
- `HeroTitleCanvas` — efeito visual no titulo h1
- `ReelSubtitleCanvas` — preview de legendas estilo reel
- `SocialProofCanvas` — numeros animados
- `HowItWorksStepCanvas` — numeros dos steps animados
- `ShowcasePretextOverlay` — legendas animadas sobre videos de showcase
- `PretextSubtitlePreview` — preview de legendas no editor
- `SubtitleTimeline` — timeline com posicao de legendas
- `useTextLayout` hook — reutilizavel para qualquer componente

## APIs Pretext — COMPLETA (usar ao maximo)

A lib Pretext de Cheng Lou nao e "animacao de texto". E um **motor de layout tipografico** que pre-calcula largura/altura de cada palavra, permitindo posicionamento absoluto, flow entre containers, text wrapping ao redor de obstaculos, e fit-text sem jitter DOM.

Video de referencia: https://www.youtube.com/watch?v=CUAuy5SWJcw

### API TypeScript completa
```typescript
import {
  prepare,              // Prepara texto para layout (sem segmentos)
  prepareWithSegments,  // Prepara texto com segmentos Unicode (acesso ao texto)
  layout,               // Layout rapido — retorna apenas lineCount + height
  layoutWithLines,      // Layout completo — retorna array de LayoutLine {text, width, start, end}
  layoutNextLine,       // Layout ITERATIVO — processa uma linha por vez (cursor resume de onde parou)
  walkLineRanges,       // Itera sobre ranges dentro de linhas (para hit testing)
  clearCache,           // Limpa cache interno de medidas
  setLocale,            // Define locale para line-breaking rules
  type PreparedText,
  type PreparedTextWithSegments,
  type LayoutCursor,       // {segmentIndex, graphemeIndex} — cursor para resume de layout
  type LayoutLine,         // {text, width, start: LayoutCursor, end: LayoutCursor}
  type LayoutLinesResult,  // {lineCount, height, lines: LayoutLine[]}
  type LayoutResult,       // {lineCount, height}
} from '@chenglou/pretext'
```

### Capacidades avancadas (das demos oficiais, USAR no redesign)

1. **Fit Text sem jitter** — Repetir `layout()` com font-sizes diferentes para encontrar o tamanho que preenche exatamente o espaco. Como `layout()` retorna apenas lineCount/height (sem DOM), e instantaneo. Ideal para titulos hero que preenchem a viewport.

2. **Text flow entre containers** — `layoutNextLine()` retorna um `LayoutCursor` no `end`. Passar esse cursor como `start` do proximo `layoutNextLine()` faz o texto CONTINUAR de onde parou — pode fluir entre colunas, ao redor de obstaculos, entre secoes.

3. **Text wrapping ao redor de obstaculos** — A demo `dynamic-layout.ts` mostra texto que desvia de logos/formas. Para cada faixa Y (band), calcula os intervalos livres e usa `layoutNextLine()` com largura reduzida. O texto reflui em tempo real quando o obstaculo muda.

4. **Layout editorial multi-coluna** — A demo `editorial-engine.ts` faz layout estilo jornal/revista com headline, drop cap, pullquote, e corpo em 2 colunas. Tudo via Canvas, sem DOM.

5. **Medida exata de texto** — `prepareWithSegments()` retorna `widths[]` por segmento. Sabe exatamente quantos pixels cada palavra ocupa. Permite posicionar qualquer elemento ao lado de texto com precisao sub-pixel.

6. **Accordion com pre-calculo** — A demo `accordion.ts` usa `layout()` para saber a altura EXATA do conteudo ANTES de abrir, permitindo animacao CSS suave sem reflow.

### Demos incluidas na lib (em node_modules/@chenglou/pretext/pages/demos/)
- `dynamic-layout.ts` — Layout editorial com logos como obstaculos, texto reflui ao redor
- `editorial-engine.ts` — Revista digital: headline fit, drop cap, pullquote, 2 colunas
- `bubbles.ts` — Chat bubbles com largura otimizada (menos espaco desperdicado)
- `accordion.ts` — Accordion com altura pre-calculada para animacao sem jitter
- `variable-typographic-ascii.ts` — Tipografia variavel ASCII art
- `justification-comparison.ts` — Comparacao de justificacao de texto
- `masonry/` — Layout masonry com texto

### Pattern de uso em Canvas (o mais poderoso)
```typescript
// 1. Preparar texto (fazer UMA vez, cachear)
const prepared = prepareWithSegments(text, '600 48px Inter')

// 2. Layout com largura do canvas
const result = layoutWithLines(prepared, canvasWidth - padding * 2, lineHeight)

// 3. Renderizar cada linha com controle total
const ctx = canvas.getContext('2d')
for (const line of result.lines) {
  // Posicao, cor, opacidade, escala, blur — TUDO controlavel por palavra
  ctx.fillText(line.text, x, y)
  y += lineHeight
}

// 4. Para animacao: renderizar palavra por palavra com timing
for (const line of result.lines) {
  const words = line.text.split(' ')
  let xOffset = x
  for (const word of words) {
    // Cada palavra pode ter sua propria animacao, cor, escala, glow...
    ctx.fillText(word, xOffset, y)
    xOffset += ctx.measureText(word + ' ').width
  }
}
```

### Pattern de Fit Text (titulo que preenche viewport)
```typescript
function fitText(text: string, fontFamily: string, maxWidth: number, targetLines: number): number {
  let lo = 10, hi = 200
  while (hi - lo > 0.5) {
    const mid = (lo + hi) / 2
    const prepared = prepareWithSegments(text, `900 ${mid}px ${fontFamily}`)
    const result = layout(prepared, maxWidth, mid * 1.1)
    if (result.lineCount <= targetLines) lo = mid
    else hi = mid
  }
  return lo
}
// Resultado: fontSize exata para o texto caber em N linhas no espaco dado
// SEM DOM, SEM jitter, SEM reflow — calculo puro
```

---

## O QUE ESTA GENERICO (diagnostico)

1. **Hero**: layout 2-colunas padrao SaaS, titulo "Crie videos curtos com IA" e o mais previsivel possivel
2. **Cards**: todos iguais — bg escuro, border sutil, border-radius. Zero personalidade.
3. **Espacamento**: tudo max-w-5xl com padding uniforme. Sem ritmo visual.
4. **Cor**: monocromatico roxo. Sem contraste, sem hierarquia dramatica.
5. **Tipografia**: Inter e Space Grotesk sao boas mas usadas sem ousadia. Tudo 16-18px normal.
6. **Movimento**: os Canvas Pretext sao lindos mas estao "presos" em caixinhas pequenas. O resto da pagina e estatico.
7. **ShowcaseSection**: 3 cards identicos lado a lado. Layout de template Bootstrap.
8. **HowItWorks**: 3 steps com icones SVG genericos. Todo SaaS tem isso.
9. **Footer**: 3 textos num flex. Sem personalidade.
10. **Dashboard**: funcional mas parece admin panel, nao produto criativo.

---

## DIRETRIZES DE DESIGN (seguir rigidamente)

### Identidade visual
- **ClipIA e um produto de VIDEO, nao de texto.** O design deve evocar cinema, movimento, frames.
- Pensar em: timelines de edicao, film strips, viewfinders, aspect ratios 9:16
- Gradientes devem ser cinematicos (nao o gradiente SaaS padrao roxo→azul)
- Background nao e flat #0f0b1a — usar texturas sutis: grain, noise, linhas de scan

### Tipografia como arte
- O Pretext JA EXISTE. Usar mais. Titulos de secao podem ser Canvas animados.
- Hierarchy dramatica: titulo hero pode ser 6rem+, subtitulos podem ser enormes
- Misturar pesos: 900 para impacto, 300 para contraste
- Letter-spacing negativo nos titulos grandes (-0.04em ou mais)

### Layout que respira
- Quebrar a monotonia de max-w centralizado. Algumas secoes podem ser full-bleed.
- Assimetria intencional: hero nao precisa ser 50/50
- Whitespace generoso entre secoes (120px+, nao 48px)
- Elementos que "sangram" fora do container

### Movimento com proposito
- Scroll-triggered reveals (CSS `animation-timeline: view()` ou IntersectionObserver — sem lib)
- Parallax sutil em backgrounds
- Pretext canvas pode reagir ao scroll (mudar frase conforme secao visivel)
- Transicoes de hover que surpreendem (nao apenas opacity/transform)

### Dark theme cinematico
- Background principal: quase preto com tom levemente azulado/roxo
- Elementos de destaque: brilho real (box-shadow com spread, nao border sutil)
- Glassmorphism SUTIL onde faz sentido (navbar, cards flutuantes)
- Neon glow nos elementos interativos (nao em tudo — so nos pontos focais)

### O que NAO fazer
- Nao adicionar framer-motion, GSAP, ou qualquer lib de animacao. CSS puro + Canvas Pretext.
- Nao fazer o site "pesado". Manter performance. Canvas e leve.
- Nao perder funcionalidade. Tudo que funciona hoje continua funcionando.
- Nao mudar a paleta de cores drasticamente (roxo e a marca). Mas EXPANDIR com acentos.
- Nao colocar animacao em TUDO. Cada animacao deve ter motivo.

---

## SECAO POR SECAO: O QUE MUDAR

### 1. HeroSection — A primeira impressao

**Atual**: Grid 2-col, titulo a direita, phone mockup a esquerda. Generico.

**Visao**: Full-viewport hero onde a TIPOGRAFIA e a estrela. O titulo usa Pretext `fitText` para preencher toda a largura disponivel — nao e "font-size: clamp(...)", e calculo exato via `layout()` que encontra o fontSize perfeito para o texto ocupar 2 linhas na viewport. Cada palavra do titulo aparece com animacao staggered (blur→focus ou scale pop). O phone mockup fica menor, subordinado a tipografia.

Ideias concretas usando Pretext avancado:
- **Fit Title Canvas**: titulo hero renderizado via Canvas com `fitText()` — preenche 100% da largura. Em resize, recalcula instantaneamente sem jitter (a magia do Pretext: nao usa DOM pra medir)
- **Staggered word reveal**: cada palavra aparece com delay progressivo. Primeiro "Crie" (pop), depois "videos" (pop), depois "que" (pop), "ninguem" (pop), "pula" (pop). Timing: 80ms entre palavras.
- **PretextCanvas expandido**: as legendas ao vivo nao ficam numa caixinha — ocupam toda a largura abaixo do titulo como elemento hero. Fonte maior (24px+). Modos animados em loop.
- **Subtitle preview reage ao mouse**: ao mover o cursor, a animacao de legenda muda sutilmente (velocidade, cor do highlight). Feedback interativo que convida a explorar.
- Phone mockup menor, a direita, com glow cinematico sutil. O titulo e as legendas sao os protagonistas, nao o mockup.
- CTA com micro-interacao no hover: texto do botao faz um sutil "typewriter rewrite" via Canvas (ex: "Experimentar" → apaga → "Criar meu video")

**Referencia tecnica**: A demo `dynamic-layout.ts` do Pretext faz fit text com `layout()` repetido — usar o mesmo pattern para o titulo hero.

### 2. SocialProofBar — Numeros que impressionam

**Atual**: Bar horizontal com numeros. Generico.

**Visao**: Full-bleed section com numeros GIGANTES renderizados via Canvas Pretext com `fitText`. Cada numero ocupa exatamente a largura do seu container. Animacao: os digitos "contam" de 0 ao valor final usando Canvas (nao DOM), com easing elastic. O tamanho da fonte e recalculado a cada frame conforme o numero muda (de "0" para "500+" os digitos mudam de largura — Pretext recalcula instantaneamente).

**Tecnica Pretext**: Para cada metrica, usar `layout()` com fontes crescentes para encontrar o font-size maximo que cabe no container. Conforme o numero anima (0→500), o font-size pode mudar sutilmente porque "500" e mais largo que "0" — Pretext recalcula sem flicker.

### 3. ShowcaseSection — Videos como portfolio

**Atual**: 3 cards identicos lado a lado. Layout Bootstrap.

**Visao**: Layout editorial/magazine. Um video grande a esquerda (featured), dois menores a direita. Ou carousel horizontal que "escorrega" com scroll. Cada video tem o Pretext overlay animando legendas em tempo real. O hover revela mais info com transicao cinematica.

Layout alternativo: grid assimetrico — 1 card ocupa 60% da largura, os outros 2 ocupam 40% empilhados. Nao precisam ser uniformes.

### 4. DemoSection — O momento "uau"

**Atual**: Form de demo. Funcional mas nao gera "uau".

**Visao**: Secao split. Esquerda: input onde o usuario digita um tema. Direita: Canvas Pretext que simula o pipeline em tempo real:
1. Usuario digita "5 curiosidades sobre o oceano" → o texto aparece via typewriter no Canvas
2. Apos 1s, o Canvas transiciona: o texto se reorganiza como ROTEIRO (multi-coluna estilo editorial-engine), com "Cena 1", "Cena 2" fluindo em layout de script
3. Depois, ondas de audio aparecem sobre o texto (o texto continua legivel mas com waveform overlay)
4. Finalmente, o canvas faz zoom out e o roteiro "encolhe" para dentro de um frame 9:16

Isso usa as capacidades avancadas do Pretext: text flow entre containers (script fluindo pelas cenas), fit text (titulo do roteiro preenchendo o espaco), e layout iterativo com `layoutNextLine()` para o texto continuar entre cenas.

**Referencia**: A demo `editorial-engine.ts` faz exatamente layout multi-coluna com headline fit + body flow. Adaptar para um "script de video" em vez de artigo.

### 5. HowItWorks — Menos steps, mais cinema

**Atual**: 3 cards com icone + texto. Todo SaaS tem.

**Visao**: Timeline vertical com UM Canvas grande que cobre os 3 steps. Conforme o usuario scrolla, o texto de cada step flui para o proximo usando `layoutNextLine()` com cursor continuous — literalmente o texto de um step CONTINUA no seguinte, como se fosse um so documento fluindo. O numero do step e fit-text gigante no background (opacidade 5%) usando `fitText()`.

**Tecnica Pretext**: Usar `walkLineRanges()` para saber exatamente onde cada step comeca e termina no canvas. Highlight do step ativo conforme scroll position.

Alternativa mais simples: cada step e um Canvas individual que renderiza o numero gigante via `fitText` e a descricao aparece com animacao de typewriter ao entrar em view.

### 6. Footer — Personalidade ate o fim

**Atual**: 3 textos num flex row. Sem alma.

**Visao**: Footer dark com grid organizado, links uteis (Produto, Legal, Contato), tagline com Pretext animado sutil, filmstrip decorativo.

### 7. Dashboard — De admin panel para studio criativo

**Atual**: Form + grid de videos. Funcional mas sem personalidade.

**Visao**:
- Saudacao personalizada: "Ola, Gui. Pronto para criar?" com hora do dia
- GenerateForm com visual de "estudio": fundo com textura, input que parece prompt de terminal
- VideoGrid com cards que mostram thumbnail 9:16 real (ou placeholder cinematico)
- Progress de geracao com barra estilo timeline de edicao (nao barra simples)
- Stats do usuario (videos criados, creditos usados) com mini graficos

### 8. Paginas de Auth — Primeira experiencia

**Atual**: Cards centralizados, funcional. Generico.

**Visao**: Background com animacao Pretext sutil (frases sobre video aparecendo e sumindo). Logo grande. Forms limpos mas com personalidade (inputs com borda que brilha ao focar). OTP inputs ja sao bons — manter.

---

## COMPONENTES NOVOS A CRIAR

### 1. `CinematicSection` wrapper
```tsx
// Wrapper para secoes com reveal on scroll, spacing generoso, fundo customizavel
<CinematicSection
  background="grain" // "grain" | "gradient" | "mesh" | "none"
  reveal="fade-up"   // "fade-up" | "slide-left" | "blur-in" | "none"
  spacing="xl"       // "md" | "lg" | "xl"
>
```

### 2. `PretextHeading` — Titulos animados
```tsx
// Titulo que anima via Canvas Pretext ao entrar em view
<PretextHeading
  text="Showcase"
  animation="blur-focus" // "blur-focus" | "pop" | "typewriter" | "karaoke"
  fontSize={72}
  color="#ffffff"
  triggerOnView
/>
```

### 3. `GlowCard` — Cards com personalidade
```tsx
// Card com glow border que segue o mouse (efeito spotlight)
<GlowCard glowColor="#7c3aed" intensity={0.3}>
  {children}
</GlowCard>
```

### 4. `FilmstripBackground` — Background decorativo
```tsx
// Background com filmstrip frames sutis passando
<FilmstripBackground speed={20} opacity={0.03} />
```

### 5. `AnimatedCounter` — Numeros que contam
```tsx
// Numero que anima de 0 ao valor final usando Pretext Canvas
<AnimatedCounter value={500} suffix="+" label="videos criados" />
```

---

## IMPLEMENTACAO

### Ordem de execucao
1. Criar componentes base (CinematicSection, PretextHeading, GlowCard)
2. Redesenhar HeroSection (maior impacto visual)
3. Redesenhar ShowcaseSection (layout editorial)
4. Redesenhar HowItWorks (timeline cinematica)
5. Melhorar SocialProofBar (numeros gigantes)
6. Redesenhar Footer
7. Melhorar Dashboard (saudacao, visual de estudio)
8. Melhorar paginas Auth (background animado)

### Regras tecnicas
- CSS puro para animacoes (keyframes, animation-timeline, transitions). ZERO libs externas.
- Canvas Pretext para tipografia animada. Ja existe e funciona.
- IntersectionObserver para triggers de scroll (sem lib).
- Manter responsive (mobile-first). Testar em 375px e 1440px.
- Manter Server Components onde possivel. "use client" so quando precisa de Canvas/interatividade.
- NAO quebrar rotas, auth, ou funcionalidade existente.
- Manter o hook `useTextLayout` para reutilizacao de Pretext.

### Verificacao
```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
# Testar visual em http://localhost:3003 nos viewports 375px, 768px, 1440px
```

---

## CONTEXTO CRITICO

### O que torna o ClipIA diferente (usar como inspiracao visual)
1. Gera videos com legendas sincronizadas — o PRETEXT mostra isso ao vivo
2. Narracao com vozes naturais pt-BR — o audio e protagonista
3. Pipeline automatico: tema → video pronto em 2min — VELOCIDADE e o valor
4. Editor visual com Remotion — o usuario tem controle

### Competidores visuais (estudar o nivel de design)
- opus.pro — editor de clips, design cinematico
- descript.com — editor de video/audio, tipografia forte
- runway.ml — IA generativa, visual futurista
- captions.ai — legendas automaticas, UI limpa e impactante

O ClipIA nao precisa copiar nenhum deles. Mas precisa estar no MESMO NIVEL de polimento visual. O produto funciona — agora o visual precisa comunicar "isso e serio".

### Demos do Pretext (INCLUIDAS na lib — estudar antes de implementar)
Os arquivos estao em `node_modules/@chenglou/pretext/pages/demos/`. LEIA ESTES ARQUIVOS antes de comecar:

- **`dynamic-layout.ts`** — O MAIS IMPORTANTE. Layout editorial com logos como obstaculos, titulo com fit-text, texto que reflui ao redor de formas em tempo real. Este e o nivel de ambicao que queremos.
- **`editorial-engine.ts`** — Layout de revista: headline fit, drop cap, pullquote, 2 colunas, orbs como obstaculos. Inspiracao para a DemoSection.
- **`accordion.ts`** — Accordion com altura pre-calculada via `layout()`. Mostra como usar Pretext para medir ANTES de animar.
- **`bubbles.ts`** — Chat bubbles otimizados. Mostra comparacao visual de largura CSS vs Pretext.

Video de referencia do criador: https://www.youtube.com/watch?v=CUAuy5SWJcw

### O principio fundamental
O CSS trata texto como conteudo que flui num box model rigido. O Pretext trata texto como **grafismo** — voce sabe exatamente quantos pixels cada palavra ocupa e pode posicionar com precisao sub-pixel. Isso permite:
- Texto que preenche exatamente o espaco (fit text)
- Texto que desvia de obstaculos (obstacle routing)
- Texto que flui entre containers (continuous cursor)
- Texto que anima sem DOM reflow (tudo em Canvas)
- Texto que se adapta ao resize sem jitter (recalculo instantaneo)

O ClipIA DEVE usar essas capacidades de forma visivel — e o que nenhum outro SaaS tem.
