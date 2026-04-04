# ClipIA — Brand Guidelines

## Nome

- **Nome completo:** ClipIA
- **Grafia:** "Clip" em regular + "IA" em destaque (gradiente ou bold)
- **Pronúncia:** "Clip-I-A" (três sílabas)
- **Uso em texto corrido:** ClipIA (CamelCase, sempre junto)

## Logo

| Variante | Arquivo | Uso |
|----------|---------|-----|
| Logo dark (texto claro) | `public/logo.svg` | Fundo escuro (padrão) |
| Logo light (texto escuro) | `public/logo-light.svg` | Fundo claro |
| Ícone only | `public/favicon-icon.svg` | Favicon, app icon, espaços pequenos |

### Anatomia do Logo
- **Ícone:** Quadrado arredondado (rx=6) com borda gradiente + triângulo play preenchido
- **Texto:** "Clip" em branco/escuro + "IA" em gradiente
- **Fonte:** Inter Bold (700)

### Espaçamento mínimo
Manter pelo menos 50% da altura do ícone como padding ao redor do logo.

## Cores

### Primárias (Gradiente Brand)
| Nome | Hex | Uso |
|------|-----|-----|
| Purple | `#7c3aed` | Início do gradiente (violet-600) |
| Blue | `#3b82f6` | Fim do gradiente (blue-500) |

**CSS do gradiente:**
```css
background: linear-gradient(135deg, #7c3aed, #3b82f6);
```

### Neutras (UI)
| Nome | Hex | Uso |
|------|-----|-----|
| Background | `#050509` | Fundo principal |
| Surface | `#0a0a12` | Cards, sections |
| Text primary | `#f1f5f9` | Texto principal (slate-100) |
| Text secondary | `#94a3b8` | Texto secundário (slate-400) |
| Border | `rgba(124, 58, 237, 0.15)` | Bordas sutis |

## Tipografia

| Elemento | Fonte | Peso | Tamanho |
|----------|-------|------|---------|
| Headings | Inter | 700 (Bold) | 2rem–3.5rem |
| Body | Inter | 400 (Regular) | 1rem |
| Buttons | Inter | 600 (Semibold) | 0.875rem–1rem |
| Captions | Inter | 400 | 0.75rem–0.875rem |

## Ícones e Assets

| Asset | Tamanho | Arquivo |
|-------|---------|---------|
| Favicon .ico | 16x16, 32x32 | `src/app/favicon.ico` |
| Apple Touch Icon | 180x180 | `public/apple-touch-icon.png` |
| Manifest icon small | 192x192 | `public/icon-192.png` |
| Manifest icon large | 512x512 | `public/icon-512.png` |
| OG Image | 1200x630 | `public/og-image.png` |

## Tom de Voz

- **Direto e confiante:** "Crie vídeos curtos com IA" (não "Tente criar...")
- **Português brasileiro:** Toda a UI em pt-BR
- **Sem jargão técnico:** "vídeo pronto para publicar" (não "pipeline de renderização")
- **Verbos de ação:** "Experimentar", "Criar", "Publicar"
