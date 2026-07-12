# Planos de melhoria de animações — ClipIA

Gerados por `/improve-animations` em 2026-07-12 (auditoria completa: 4 auditores paralelos + vetting adversarial das citações). Commit de referência: `6428262`. Cada plano é autocontido — executável por qualquer agente, inclusive modelos mais baratos, sem contexto da auditoria.

**Regra de ouro para o executor**: os planos citam linhas do commit `6428262`. Se o código encontrado divergir do trecho citado, PARE e reporte — não improvise. Executar UM plano por vez (alguns tocam os mesmos arquivos; números de linha mudam após cada plano aplicado).

## Planos

| # | Título | Severidade | Status |
|---|--------|------------|--------|
| [001](001-modais-fisica-entrada-saida.md) | Modais com física de entrada/saída (Modal, ExportPanel, VideoPlayerModal) | HIGH | DONE |
| [002](002-toasts-entrada-saida-restack.md) | Toasts com entrada, saída e restack suave | HIGH | DONE |
| [003](003-playhead-transform-nao-layout.md) | Playhead das timelines: transform, não `left` | HIGH | DONE |
| [004](004-progress-bars-scalex.md) | Barras de progresso: `scaleX` em vez de `width` | MEDIUM | DONE |
| [005](005-tokens-css-e-fim-do-transition-all.md) | Tokens CSS de motion + fim do `transition: all` | MEDIUM | DONE |
| [006](006-press-feedback-ctas.md) | Press feedback nos CTAs (cobertura completa) | MEDIUM | DONE |
| [007](007-generateform-transicoes-de-estado.md) | GenerateForm: transições nas mudanças de estado | MEDIUM | DONE |
| [008](008-reduced-motion-gentil-e-status.md) | Reduced-motion gentil + polish dos indicadores de status | LOW-MED | TODO |
| [009](009-delight-video-pronto-e-creditos.md) | Delight: celebração "vídeo pronto" + tick de créditos | LOW | TODO |

## Ordem de execução recomendada

1. **005** — fundação: cria os tokens `--ease-out`/`--ease-gentle` que 004/006 referenciam (ambos têm fallback, mas rodar 005 primeiro evita duplicação).
2. **003** — maior ganho de performance por linha editada (hot path do playback).
3. **004** — mecânico, mesmo padrão em 4 lugares.
4. **001** — maior ganho de percepção de qualidade (modais de ações pagas).
5. **002** — toasts.
6. **006** — press feedback (depende das listas de `transition` que o 005 ajusta; tem fallback embutido).
7. **007** — GenerateForm.
8. **008** — reduced-motion + status.
9. **009** — delight (rodar por último; usa o comportamento de reduced-motion do 008).

## Dependências e conflitos de arquivo

- `006` ← `005` (listas de transition dos `.btn-*`; o 006 traz instrução de fallback se 005 não tiver rodado).
- `004` e `005` criam `--ease-out` condicionalmente ("criar se ausente") — qualquer ordem funciona, sem duplicar.
- Arquivos compartilhados (executar em série, nunca em paralelo): `globals.css` (004, 005, 006, 008, 009) · `editor.css` (003, 004, 005, 006) · `GenerateForm.tsx` (005, 006, 007) · `VideoCard.tsx` (001, 004, 005, 009) · `Navbar.tsx` (005, 006, 009).

## Verificação global (após o conjunto)

- `cd frontend; npx next typegen; npx tsc --noEmit` e `npm run build` verdes.
- `rg "transition: all" frontend/src` → zero.
- Smoke visual: dashboard (gerar vídeo → progresso → pronto), editor (playback, export, reset), landing (scroll), tudo com DevTools → Rendering → `prefers-reduced-motion: reduce` ligado e desligado.

## Aceitos sem plano (decisões documentadas na auditoria)

- Colapso do painel do editor anima `flex-basis` (layout): o efeito exige redimensionar o player junto — tradeoff inerente, interação rara (005 adiciona comentário no CSS).
- Menu mobile do Navbar anima `height: auto`: aceitável para painel de altura desconhecida em interação ocasional.
- `OpticalBalancePreview` 600ms/curva própria: debounced e com propósito (evitar pulo de largura); baixo impacto.
- `GlowCard` re-renderiza no mousemove: `children` tem referência estável (sem re-render do subtree); custo real baixo.
- Keyframes decorativos da landing (marquee, float, shimmer, equalize): corretos para marketing, mortos sob reduced-motion.
- Dead code notado (fora do escopo de motion): `ui/AnimatedCounter.tsx` e o variant `fadeIn` de `lib/motion.ts` não têm call sites.
