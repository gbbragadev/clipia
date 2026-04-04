# ClipIA Rebranding — Phase 1: Branding & Identidade

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar a identidade visual do ClipIA — web manifest, OG image, apple-touch-icon, metadata completa, backend renomeado, e brand guidelines documentado.

**Architecture:** O branding principal (nome ClipIA, logo SVG, favicon.ico, cores, tipografia) já está aplicado no frontend. Este plano cobre os gaps restantes: meta tags de ícone no layout, web manifest para PWA/bookmark, OG image para compartilhamento social, renomear referências "Auto Shorts" no backend Python, e documentar as brand guidelines.

**Tech Stack:** Next.js 16 (App Router), FastAPI, SVG, sharp (para gerar PNG do ícone), Tailwind v4

---

## Estado Atual (Auditoria)

| Item | Status | Localização |
|------|--------|-------------|
| Nome "ClipIA" | ✅ Feito | Navbar, Footer, Hero, Waitlist, Demo, VideoShowcase |
| Logo SVG dark | ✅ Feito | `frontend/public/logo.svg` |
| Logo SVG light | ✅ Feito | `frontend/public/logo-light.svg` |
| Favicon icon SVG | ✅ Feito | `frontend/public/favicon-icon.svg` |
| Favicon .ico (16+32px) | ✅ Feito | `frontend/src/app/favicon.ico` |
| Cores purple→blue gradient | ✅ Feito | `globals.css`, todos os componentes |
| Tipografia Inter | ✅ Feito | `layout.tsx` |
| Web manifest | ❌ Falta | — |
| Apple-touch-icon (180px PNG) | ❌ Falta | — |
| OG image (1200x630) | ❌ Falta | — |
| Meta tags de ícone no `<head>` | ❌ Falta | `layout.tsx` não tem `<link rel="icon">` explícitos |
| Backend title "Auto Shorts" | ❌ Renomear | `app/main.py:6` |
| Celery app name "auto_shorts" | ❌ Renomear | `app/worker/celery_app.py:5` |
| package.json name genérico | ❌ Renomear | `frontend/package.json` → name: "frontend" |
| Brand guidelines doc | ❌ Falta | — |

---

## File Structure

| Ação | Arquivo | Responsabilidade |
|------|---------|------------------|
| Create | `frontend/public/apple-touch-icon.png` | Ícone 180x180 para iOS bookmark |
| Create | `frontend/public/icon-192.png` | Ícone 192x192 para web manifest |
| Create | `frontend/public/icon-512.png` | Ícone 512x512 para web manifest |
| Create | `frontend/src/app/manifest.ts` | Web manifest dinâmico via Next.js |
| Create | `frontend/public/og-image.png` | Imagem 1200x630 para social sharing |
| Create | `frontend/scripts/generate-icons.mjs` | Script para gerar PNGs dos ícones a partir do SVG |
| Modify | `frontend/src/app/layout.tsx` | Adicionar metadata completa (icons, OG, manifest) |
| Modify | `app/main.py:6` | Renomear título para "ClipIA API" |
| Modify | `app/worker/celery_app.py:5` | Renomear app name para "clipia" |
| Modify | `frontend/package.json` | Renomear name para "clipia-frontend" |
| Create | `docs/brand-guidelines.md` | Documentação da identidade visual |

---

### Task 1: Gerar ícones PNG a partir do SVG

**Files:**
- Create: `frontend/scripts/generate-icons.mjs`
- Create: `frontend/public/apple-touch-icon.png`
- Create: `frontend/public/icon-192.png`
- Create: `frontend/public/icon-512.png`

O favicon-icon.svg já existe com o design correto (quadrado arredondado + play, gradiente purple→blue). Precisamos de PNGs em 3 tamanhos para web manifest e apple-touch-icon.

- [ ] **Step 1: Instalar sharp como dev dependency**

```bash
cd /home/gui/projects/auto-shorts/frontend
npm install --save-dev sharp
```

- [ ] **Step 2: Criar script de geração de ícones**

Criar `frontend/scripts/generate-icons.mjs`:

```js
import sharp from "sharp";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const svgPath = resolve(__dirname, "../public/favicon-icon.svg");
const outDir = resolve(__dirname, "../public");

const svg = readFileSync(svgPath);

const sizes = [
  { name: "apple-touch-icon.png", size: 180 },
  { name: "icon-192.png", size: 192 },
  { name: "icon-512.png", size: 512 },
];

for (const { name, size } of sizes) {
  await sharp(svg, { density: 300 })
    .resize(size, size)
    .png()
    .toFile(resolve(outDir, name));

  console.log(`✓ ${name} (${size}x${size})`);
}
```

- [ ] **Step 3: Executar o script e verificar os PNGs**

```bash
cd /home/gui/projects/auto-shorts/frontend
node scripts/generate-icons.mjs
```

Expected output:
```
✓ apple-touch-icon.png (180x180)
✓ icon-192.png (192x192)
✓ icon-512.png (512x512)
```

Verificar que os arquivos existem:
```bash
ls -la public/apple-touch-icon.png public/icon-192.png public/icon-512.png
```

- [ ] **Step 4: Commit**

```bash
git add frontend/scripts/generate-icons.mjs frontend/public/apple-touch-icon.png frontend/public/icon-192.png frontend/public/icon-512.png frontend/package.json frontend/package-lock.json
git commit -m "feat(brand): generate PNG icons from SVG for manifest and apple-touch"
```

---

### Task 2: Web Manifest

**Files:**
- Create: `frontend/src/app/manifest.ts`

Next.js App Router suporta web manifest gerado via `manifest.ts` na raiz do app directory. Isso é servido automaticamente em `/manifest.webmanifest`.

- [ ] **Step 1: Criar manifest.ts**

Criar `frontend/src/app/manifest.ts`:

```ts
import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ClipIA",
    short_name: "ClipIA",
    description:
      "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
    start_url: "/",
    display: "standalone",
    background_color: "#050509",
    theme_color: "#7c3aed",
    icons: [
      {
        src: "/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
```

- [ ] **Step 2: Verificar que o manifest é servido**

```bash
cd /home/gui/projects/auto-shorts/frontend
npx next build 2>&1 | tail -5
```

Se o build passa, o manifest será servido em `/manifest.webmanifest` automaticamente pelo Next.js.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/manifest.ts
git commit -m "feat(brand): add web manifest for PWA and bookmark support"
```

---

### Task 3: OG Image para social sharing

**Files:**
- Create: `frontend/public/og-image.png`

A OG image aparece quando alguém compartilha o link no Twitter, LinkedIn, WhatsApp, etc. Tamanho ideal: 1200x630px.

- [ ] **Step 1: Criar script de geração da OG image**

Criar `frontend/scripts/generate-og-image.mjs`:

```js
import sharp from "sharp";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outPath = resolve(__dirname, "../public/og-image.png");

// SVG com layout da OG image: fundo escuro, logo, headline
const svg = `
<svg width="1200" height="630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#050509"/>
      <stop offset="50%" stop-color="#0a0a1a"/>
      <stop offset="100%" stop-color="#050509"/>
    </linearGradient>
    <linearGradient id="brand" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7c3aed"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="glow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#7c3aed" stop-opacity="0.15"/>
      <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.05"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Ambient glow -->
  <ellipse cx="600" cy="315" rx="500" ry="300" fill="url(#glow)"/>

  <!-- Logo icon (scaled up) -->
  <g transform="translate(490, 140) scale(3)">
    <rect x="2" y="2" width="28" height="28" rx="6" fill="none" stroke="url(#brand)" stroke-width="2.5"/>
    <polygon points="12,8 12,24 24,16" fill="url(#brand)"/>
  </g>

  <!-- Brand name -->
  <text x="600" y="380" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="72" font-weight="700" fill="#f1f5f9">
    Clip<tspan fill="url(#brand)">IA</tspan>
  </text>

  <!-- Tagline -->
  <text x="600" y="440" text-anchor="middle" font-family="Inter, system-ui, sans-serif" font-size="28" font-weight="400" fill="#94a3b8">
    Crie videos curtos com IA
  </text>

  <!-- Subtle border -->
  <rect x="0" y="0" width="1200" height="630" fill="none" stroke="#7c3aed" stroke-opacity="0.2" stroke-width="1"/>
</svg>`;

await sharp(Buffer.from(svg))
  .resize(1200, 630)
  .png({ quality: 90 })
  .toFile(outPath);

console.log("✓ og-image.png (1200x630)");
```

- [ ] **Step 2: Executar o script**

```bash
cd /home/gui/projects/auto-shorts/frontend
node scripts/generate-og-image.mjs
```

Expected: `✓ og-image.png (1200x630)`

Verificar:
```bash
file public/og-image.png
```
Expected: `PNG image data, 1200 x 630`

- [ ] **Step 3: Commit**

```bash
git add frontend/scripts/generate-og-image.mjs frontend/public/og-image.png
git commit -m "feat(brand): add OG image for social sharing"
```

---

### Task 4: Metadata completa no layout.tsx

**Files:**
- Modify: `frontend/src/app/layout.tsx`

Adicionar icons, OG tags, Twitter card, e theme-color na metadata do Next.js.

- [ ] **Step 1: Atualizar layout.tsx com metadata completa**

Substituir o bloco `metadata` atual em `frontend/src/app/layout.tsx`:

```ts
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import FilmGrain from "@/components/FilmGrain";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ClipIA - Crie videos curtos com IA",
  description:
    "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
  icons: {
    icon: [
      { url: "/favicon-icon.svg", type: "image/svg+xml" },
    ],
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    title: "ClipIA - Crie videos curtos com IA",
    description:
      "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
    url: "https://clipia.com.br",
    siteName: "ClipIA",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "ClipIA — Crie videos curtos com IA",
      },
    ],
    locale: "pt_BR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ClipIA - Crie videos curtos com IA",
    description:
      "Transforme qualquer tema em video pronto para publicar com IA.",
    images: ["/og-image.png"],
  },
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "https://clipia.com.br"
  ),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <FilmGrain />
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Verificar que o build passa**

```bash
cd /home/gui/projects/auto-shorts/frontend
npx next build 2>&1 | tail -10
```

Expected: build completa sem erros.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat(brand): add complete metadata — OG, Twitter card, icons, manifest"
```

---

### Task 5: Renomear referências "Auto Shorts" no backend

**Files:**
- Modify: `app/main.py:6`
- Modify: `app/worker/celery_app.py:5`

- [ ] **Step 1: Atualizar título do FastAPI**

Em `app/main.py`, linha 6, alterar:

```python
# antes:
app = FastAPI(title="Auto Shorts Generator", version="0.1.0")

# depois:
app = FastAPI(title="ClipIA API", version="0.1.0")
```

- [ ] **Step 2: Atualizar nome do Celery app**

Em `app/worker/celery_app.py`, linha 5, alterar:

```python
# antes:
celery_app = Celery("auto_shorts", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

# depois:
celery_app = Celery("clipia", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
```

**⚠️ Nota:** Renomear o Celery app name pode causar incompatibilidade com tasks em fila no Redis. Se houver jobs pendentes, eles serão perdidos. Como estamos em dev, isso é aceitável. Em produção, fazer drain da fila antes.

- [ ] **Step 3: Verificar que o backend inicia**

```bash
cd /home/gui/projects/auto-shorts
python -c "from app.main import app; print(app.title)"
```

Expected: `ClipIA API`

- [ ] **Step 4: Commit**

```bash
git add app/main.py app/worker/celery_app.py
git commit -m "feat(brand): rename backend from Auto Shorts to ClipIA"
```

---

### Task 6: Renomear package.json

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Atualizar name no package.json**

Em `frontend/package.json`, alterar o campo `name`:

```json
{
  "name": "clipia-frontend",
  ...
}
```

Apenas o campo `name` muda. Não alterar nenhuma outra coisa.

- [ ] **Step 2: Commit**

```bash
git add frontend/package.json
git commit -m "chore: rename frontend package to clipia-frontend"
```

---

### Task 7: Brand Guidelines

**Files:**
- Create: `docs/brand-guidelines.md`

Documentar a identidade visual para referência futura em integrações, marketing, e novos contribuidores.

- [ ] **Step 1: Criar documento de brand guidelines**

Criar `docs/brand-guidelines.md`:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/brand-guidelines.md
git commit -m "docs: add ClipIA brand guidelines"
```

---

### Task 8: Verificação final

- [ ] **Step 1: Grep por referências restantes a "Auto Shorts"**

```bash
cd /home/gui/projects/auto-shorts
grep -ri "auto.shorts\|autoshorts\|auto_shorts" --include="*.py" --include="*.ts" --include="*.tsx" --include="*.json" --include="*.md" -l
```

Expected: Apenas `CLAUDE.md`, `docs/superpowers/plans/`, e talvez `README.md` devem aparecer. Nenhum arquivo de código fonte.

- [ ] **Step 2: Verificar que o frontend builda limpo**

```bash
cd /home/gui/projects/auto-shorts/frontend
npx next build 2>&1 | tail -5
```

Expected: `✓ Compiled successfully`

- [ ] **Step 3: Verificar que o backend inicia**

```bash
cd /home/gui/projects/auto-shorts
python -c "from app.main import app; print(f'{app.title} v{app.version}')"
```

Expected: `ClipIA API v0.1.0`

- [ ] **Step 4: Commit final (se houve ajustes)**

Se a verificação encontrou referências restantes, corrigi-las e commitar:

```bash
git add -A
git commit -m "fix(brand): remove remaining Auto Shorts references"
```

---

## Resumo de Entregas

Ao final desta fase, o projeto terá:

1. **Ícones PNG** gerados do SVG (180, 192, 512px)
2. **Web manifest** para PWA/bookmark com ícones e theme color
3. **OG image** 1200x630 para compartilhamento social
4. **Metadata completa** no `<head>`: OG, Twitter Card, icons, manifest
5. **Backend renomeado** de "Auto Shorts" para "ClipIA"
6. **package.json** com nome correto
7. **Brand guidelines** documentado

Próxima fase: **Fase 2 — Autenticação & Banco de Dados**
