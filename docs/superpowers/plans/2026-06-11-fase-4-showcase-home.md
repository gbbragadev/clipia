# Fase 4 — Showcase da Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconstruir os exemplos da landing a partir de vídeos reais e curados do pipeline novo, com manifesto versionado, filtro por nicho, melhor UX mobile e social proof honesto.

**Architecture:** Abordagem curada (decisão registrada — sem puxar jobs de usuários dinamicamente, por controle de qualidade/moderação). Um manifesto `frontend/public/showcase/showcase.json` descreve os vídeos (gerados pelo produto, exportados pelo editor com estilo, copiados para `public/showcase/`); `ShowcaseSection`, `VideoShowcase` (hero) e `SocialProofBar` leem do manifesto. Um validador Node garante manifesto↔arquivos em sincronia.

**Tech Stack:** Next.js 16 + React 19 + Tailwind 4. Geração dos vídeos: API do próprio produto (script batch Python). Validação: `node scripts/check-showcase.mjs` + `npx tsc --noEmit`.

**Dependência:** Fase 3 concluída (transições default + Ken Burns) para os vídeos saírem "showcase-worthy".

---

### Task 1: Manifesto + tipos + loader + validador

**Files:**
- Create: `frontend/public/showcase/showcase.json`
- Create: `frontend/src/lib/showcase.ts`
- Create: `frontend/scripts/check-showcase.mjs`

- [ ] **Step 1: Criar o manifesto inicial** (com os 3 vídeos atuais — os novos substituem nas Tasks 2/6)

`frontend/public/showcase/showcase.json`:
```json
{
  "niches": [
    { "id": "educational", "label": "Educativo", "icon": "🧠" },
    { "id": "entertainment", "label": "Entretenimento", "icon": "🎬" },
    { "id": "tips", "label": "Dicas", "icon": "💡" },
    { "id": "story", "label": "Histórias", "icon": "📖" }
  ],
  "videos": [
    {
      "id": "ocean",
      "title": "5 curiosidades sobre o oceano profundo",
      "template": "Narração + Stock",
      "niche": "educational",
      "video": "/showcase/ocean-curiosidades.mp4",
      "phrase": "O oceano cobre mais de 70% da superficie da Terra",
      "captionStyle": "tiktok",
      "captionAccent": "#22d3ee",
      "gradient": "from-blue-900/60 to-cyan-900/60",
      "icon": "🌊",
      "hero": true,
      "beforeScript": "Você sabia que conhecemos menos de 5% dos oceanos?"
    },
    {
      "id": "ia",
      "title": "Como a IA está mudando o mundo",
      "template": "Narração + Stock",
      "niche": "educational",
      "video": "/showcase/ia-revolucao.mp4",
      "phrase": "Inteligencia artificial ja supera humanos em tarefas complexas",
      "captionStyle": "impact",
      "captionAccent": "#c084fc",
      "gradient": "from-purple-900/60 to-indigo-900/60",
      "icon": "🤖",
      "hero": true,
      "beforeScript": "A IA não vai te substituir. Mas quem usa IA, vai."
    },
    {
      "id": "cerebro",
      "title": "Fatos surpreendentes sobre o cérebro",
      "template": "Narração + Stock",
      "niche": "educational",
      "video": "/showcase/cerebro-fatos.mp4",
      "phrase": "Seu cerebro processa 60 mil pensamentos por dia",
      "captionStyle": "karaoke",
      "captionAccent": "#fb923c",
      "gradient": "from-amber-900/60 to-orange-900/60",
      "icon": "🧠",
      "hero": true,
      "beforeScript": "Seu cérebro mente para você o dia inteiro."
    }
  ]
}
```

- [ ] **Step 2: Criar `frontend/src/lib/showcase.ts`**

```typescript
export interface ShowcaseNiche {
  id: string
  label: string
  icon: string
}

export interface ShowcaseVideo {
  id: string
  title: string
  template: string
  niche: string
  video: string
  phrase: string
  captionStyle: 'tiktok' | 'impact' | 'karaoke' | 'minimal' | 'boxed'
  captionAccent: string
  gradient: string
  icon: string
  hero?: boolean
  beforeScript?: string
}

export interface ShowcaseManifest {
  niches: ShowcaseNiche[]
  videos: ShowcaseVideo[]
}

export async function loadShowcase(): Promise<ShowcaseManifest> {
  const res = await fetch('/showcase/showcase.json')
  if (!res.ok) throw new Error(`showcase.json: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 3: Criar `frontend/scripts/check-showcase.mjs`** (validador manifesto↔arquivos)

```javascript
// Valida que todo video do manifesto existe em public/ e nao ha mp4 orfao sem entrada.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const showcaseDir = path.join(root, 'public', 'showcase')
const manifest = JSON.parse(fs.readFileSync(path.join(showcaseDir, 'showcase.json'), 'utf8'))

let errors = 0
const nicheIds = new Set(manifest.niches.map((n) => n.id))

for (const v of manifest.videos) {
  const file = path.join(root, 'public', v.video.replace(/^\//, ''))
  if (!fs.existsSync(file)) { console.error(`MISSING FILE: ${v.video} (id=${v.id})`); errors++ }
  if (!nicheIds.has(v.niche)) { console.error(`UNKNOWN NICHE: ${v.niche} (id=${v.id})`); errors++ }
}

const referenced = new Set(manifest.videos.map((v) => path.basename(v.video)))
for (const f of fs.readdirSync(showcaseDir).filter((f) => f.endsWith('.mp4'))) {
  if (!referenced.has(f)) { console.error(`ORPHAN MP4 (sem entrada no manifesto): ${f}`); errors++ }
}

if (errors) { console.error(`\n${errors} problema(s).`); process.exit(1) }
console.log(`OK: ${manifest.videos.length} videos, ${manifest.niches.length} nichos, tudo em sincronia.`)
```

- [ ] **Step 4: Rodar o validador**

Run: `cd frontend; node scripts/check-showcase.mjs`
Expected: `OK: 3 videos, 4 nichos, tudo em sincronia.`

- [ ] **Step 5: Typecheck e commit**

Run: `cd frontend; npx next typegen; npx tsc --noEmit` → exit 0

```bash
git add frontend/public/showcase/showcase.json frontend/src/lib/showcase.ts frontend/scripts/check-showcase.mjs
git commit -m "feat(showcase): manifesto showcase.json + loader + validador"
```

---

### Task 2: Script batch de geração de candidatos

Gerar 8+ vídeos candidatos via API do próprio produto (variedade de nichos), para curadoria manual no editor.

**Files:**
- Create: `scripts/generate_showcase_batch.py`

- [ ] **Step 1: Criar o script**

```python
"""Gera videos candidatos ao showcase via API local (batch).

Uso (stack rodando):
    python -m scripts.generate_showcase_batch
Le credenciais de .admin-credentials.local. Gera 1 job por tema e acompanha ate concluir.
"""

import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8005"

# (topic, style, template_id, duration, niche-alvo p/ manifesto)
BATCH = [
    ("5 curiosidades sobre o oceano profundo", "educational", "stock_narration", 35, "educational"),
    ("Por que os gatos ronronam? A ciencia explica", "educational", "stock_narration", 30, "educational"),
    ("3 habitos que destroem sua produtividade", "educational", "stock_narration", 30, "tips"),
    ("Como economizar dinheiro sem perceber", "educational", "stock_narration", 30, "tips"),
    ("A historia do cafe: da Etiopia ao mundo", "storytelling", "stock_narration", 40, "story"),
    ("O misterio do navio que sumiu em 1872", "storytelling", "novelinha_historica", 40, "story"),
    ("Fatos absurdos que parecem mentira", "comedy", "stock_narration", 30, "entertainment"),
    ("O que aconteceria se a internet caisse no mundo todo", "news", "stock_narration", 35, "entertainment"),
]


def main() -> None:
    creds = Path(".admin-credentials.local").read_text(encoding="utf-8").splitlines()
    email = creds[0].split(":", 1)[1].strip()
    password = creds[1].split(":", 1)[1].strip()

    client = httpx.Client(base_url=API, timeout=30)
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    jobs: list[tuple[str, str]] = []
    for topic, style, template, duration, niche in BATCH:
        r = client.post(
            "/api/v1/generate",
            json={"topic": topic, "style": style, "duration_target": duration, "template_id": template},
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        jobs.append((job_id, topic))
        print(f"queued {job_id}  [{niche}] {topic}")
        # worker e --pool=solo: 1 por vez; aguardar concluir antes do proximo
        while True:
            st = client.get(f"/api/v1/jobs/{job_id}/status").json()
            if st["status"] in ("completed", "editable"):
                print(f"  done: {job_id}")
                break
            if st["status"] in ("failed", "error"):
                print(f"  FAILED: {job_id}: {st.get('error')}")
                break
            time.sleep(10)

    print("\nCandidatos prontos:")
    for job_id, topic in jobs:
        print(f"  http://localhost:3003/editor/{job_id}  <- {topic}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rodar o batch** (leva ~30-50 min com DeepSeek + pipeline; deixar rodando)

Run: `.\.venv312\Scripts\python.exe -m scripts.generate_showcase_batch`
Expected: 8 jobs concluídos com URLs do editor listadas.

- [ ] **Step 3: Curadoria manual (dono)** — para cada candidato bom: abrir no editor, ajustar estilo de legenda (variar presets: tiktok/impact/karaoke/boxed), adicionar 1 overlay onde couber, regenerar narração se precisar, **Exportar** (Remotion), baixar.

- [ ] **Step 4: Copiar os escolhidos** (6–8) para `frontend/public/showcase/{id}.mp4`, adicionar cada um ao `showcase.json` (title, niche, captionStyle usado, phrase = gancho do roteiro, beforeScript = primeira linha do roteiro), marcar os 3 melhores com `"hero": true`. Remover entradas/arquivos antigos substituídos.

- [ ] **Step 5: Validar e commitar**

Run: `cd frontend; node scripts/check-showcase.mjs` → OK

```bash
git add scripts/generate_showcase_batch.py frontend/public/showcase/
git commit -m "feat(showcase): batch de geracao + videos curados v1"
```

---

### Task 3: Refactor `ShowcaseSection` — manifesto + filtro por nicho + badge de estilo + mobile

**Files:**
- Modify: `frontend/src/components/ShowcaseSection.tsx`

- [ ] **Step 1: Reescrever o componente**

Manter `ShowcaseCard` (hover-som, IntersectionObserver) e mudar: (a) itens vêm de `loadShowcase()`; (b) tabs de nicho; (c) badge do estilo de legenda no card; (d) mobile usa carrossel horizontal com scroll-snap em vez de cards empilhados full-height.

```tsx
'use client'

import { useRef, useCallback, useEffect, useState } from 'react'
import { CinematicSection } from './ui/CinematicSection'
import { GlowCard } from './ui/GlowCard'
import { PretextHeading } from './ui/PretextHeading'
import Link from 'next/link'
import { loadShowcase, type ShowcaseManifest, type ShowcaseVideo } from '@/lib/showcase'

function ShowcaseCard({ item, featured = false }: { item: ShowcaseVideo; featured?: boolean }) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const card = cardRef.current
    const video = videoRef.current
    if (!card || !video) return
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) video.play().catch(() => {}) },
      { threshold: 0.3 },
    )
    observer.observe(card)
    return () => observer.disconnect()
  }, [])

  const handleEnter = useCallback(() => {
    const v = videoRef.current
    if (v) { v.muted = false; v.volume = 0.6; v.play().catch(() => {}) }
  }, [])
  const handleLeave = useCallback(() => { const v = videoRef.current; if (v) v.muted = true }, [])

  return (
    <GlowCard className={`h-full ${featured ? 'md:col-span-2' : ''}`}>
      <div
        ref={cardRef}
        className="w-full h-full relative cursor-pointer snap-center shrink-0"
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onTouchStart={handleEnter}
        onTouchEnd={handleLeave}
      >
        <div className="relative w-full h-full aspect-[9/16] md:aspect-auto md:min-h-[500px] overflow-hidden">
          <video
            ref={videoRef}
            autoPlay muted loop playsInline preload="metadata"
            className="w-full h-full object-cover"
            src={item.video}
          />
          {/* Badge: estilo de legenda */}
          <div className="absolute top-4 left-4 z-10">
            <span
              className="text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded-md bg-black/50 backdrop-blur-md border border-white/10"
              style={{ color: item.captionAccent }}
            >
              legenda: {item.captionStyle}
            </span>
          </div>
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[#0f0b1a] via-[#0f0b1a]/80 to-transparent p-6 pt-24">
            <h3 className={`font-bold text-white leading-tight ${featured ? 'text-2xl' : 'text-lg'}`}>{item.title}</h3>
            {item.beforeScript && (
              <p className="mt-2 text-xs text-white/50 italic">Prompt: &ldquo;{item.beforeScript}&rdquo;</p>
            )}
            <span className="inline-block mt-3 text-xs px-3 py-1 rounded-full bg-white/10 text-white/80 backdrop-blur-md border border-white/5">
              {item.template}
            </span>
          </div>
        </div>
      </div>
    </GlowCard>
  )
}

export default function ShowcaseSection() {
  const [manifest, setManifest] = useState<ShowcaseManifest | null>(null)
  const [niche, setNiche] = useState<string>('all')

  useEffect(() => { loadShowcase().then(setManifest).catch(() => {}) }, [])

  if (!manifest) return null
  const videos = niche === 'all' ? manifest.videos : manifest.videos.filter((v) => v.niche === niche)

  return (
    <CinematicSection background="none" spacing="xl" reveal="fade-up" className="border-b border-white/5">
      <div className="text-center mb-10 max-w-3xl mx-auto">
        <PretextHeading text="O que a IA cria em minutos" animation="blur-focus" color="#ffffff" className="mb-6" />
        <p className="text-xl text-slate-400">
          Vídeos reais gerados e editados no ClipIA. Passe o mouse para ouvir.
        </p>
      </div>

      {/* Filtro por nicho — scroll horizontal no mobile */}
      <div className="flex gap-2 justify-start md:justify-center mb-10 overflow-x-auto px-4 snap-x [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {[{ id: 'all', label: 'Todos', icon: '✦' }, ...manifest.niches].map((n) => (
          <button
            key={n.id}
            onClick={() => setNiche(n.id)}
            className={`shrink-0 snap-start text-sm px-4 py-2 rounded-full border transition-all ${
              niche === n.id
                ? 'bg-purple-600/30 text-purple-200 border-purple-500/40'
                : 'bg-white/5 text-white/60 border-white/10 hover:bg-white/10'
            }`}
          >
            {n.icon} {n.label}
          </button>
        ))}
      </div>

      {/* Mobile: carrossel snap; Desktop: grid */}
      <div className="flex md:grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto overflow-x-auto md:overflow-visible snap-x snap-mandatory px-4 md:px-0 [&>*]:w-[80vw] md:[&>*]:w-auto">
        {videos.map((item, i) => (
          <ShowcaseCard key={item.id} item={item} featured={i === 0 && niche === 'all'} />
        ))}
      </div>

      {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === 'true' && (
        <div className="text-center mt-16">
          <Link
            href="/auth/register"
            className="inline-block px-8 py-4 rounded-xl bg-purple-600/20 text-purple-300 font-semibold hover:bg-purple-600/30 border border-purple-500/30 transition-all"
          >
            Criar meu primeiro vídeo
          </Link>
        </div>
      )}
    </CinematicSection>
  )
}
```

Nota: `ShowcasePretextOverlay` deixa de ser usado aqui (os vídeos reais já têm legendas embutidas). Não deletar o componente (o hero ainda pode usar canvas overlay).

- [ ] **Step 2: Typecheck + visual**

Run: `cd frontend; npx next typegen; npx tsc --noEmit` → exit 0. Abrir `http://localhost:3003`, testar filtro e, em DevTools viewport 375px, o carrossel horizontal.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ShowcaseSection.tsx
git commit -m "feat(showcase): secao guiada por manifesto com filtro de nicho e carrossel mobile"
```

---

### Task 4: Hero `VideoShowcase` a partir do manifesto

**Files:**
- Modify: `frontend/src/components/hero/VideoShowcase.tsx`

- [ ] **Step 1: Trocar o array hardcoded `REELS`**

No topo do componente (que hoje define `const REELS = [...]` com 3 vídeos em `/videos/*_final.mp4`), substituir por estado carregado do manifesto — os marcados `hero: true` (máx 3), mapeando para o shape que o carrossel já usa:

```tsx
import { loadShowcase, type ShowcaseVideo } from '@/lib/showcase'

// dentro do componente:
const [reels, setReels] = useState<{ title: string; video: string; accent: string }[]>([])
useEffect(() => {
  loadShowcase()
    .then((m) => setReels(
      m.videos.filter((v) => v.hero).slice(0, 3).map((v) => ({
        title: v.title,
        video: v.video,
        accent: v.captionAccent,
      }))
    ))
    .catch(() => {})
}, [])
if (reels.length === 0) return null
```

Adaptar as referências internas: onde o componente usava `REELS[i].video` → `reels[i].video`, `REELS[i].accent` → `reels[i].accent`, `REELS.length` → `reels.length`. Os contadores fake de likes/comments do mockup: **remover** (social proof falso) — manter só os ícones sem números, ou números neutros omitidos.

- [ ] **Step 2: Typecheck + visual**

Run: `cd frontend; npx next typegen; npx tsc --noEmit` → exit 0. Hero deve rotacionar os 3 vídeos `hero` do manifesto.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hero/VideoShowcase.tsx
git commit -m "feat(hero): carrossel do mockup le os videos hero do manifesto (sem metricas fake)"
```

---

### Task 5: `SocialProofBar` honesto

**Files:**
- Modify: `frontend/src/components/SocialProofBar.tsx`

- [ ] **Step 1: Trocar as métricas**

Manter "Vídeos criados" (já vem de `/api/v1/public/stats`). Trocar as 2 hardcoded por fatos verificáveis do produto:

```tsx
      <div className="grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8 divide-y md:divide-y-0 md:divide-x divide-white/10">
        <AnimatedCounter value={totalVideos} suffix="+" label="Vídeos criados" />
        <AnimatedCounter value={5} suffix="" label="Estilos de legenda animada" />
        <AnimatedCounter value={4} suffix="" label="Vozes pt-BR (IA)" />
      </div>
```

(5 presets reais: tiktok/impact/karaoke/minimal/boxed; 4 vozes reais: Antonio/Francisca/Thalita Edge + Fernanda ElevenLabs. Se adicionar vozes, atualizar.)

- [ ] **Step 2: Typecheck + commit**

Run: `cd frontend; npx next typegen; npx tsc --noEmit` → exit 0

```bash
git add frontend/src/components/SocialProofBar.tsx
git commit -m "fix(landing): social proof com numeros verificaveis"
```

---

### Task 6: Verificação end-to-end + deploy

- [ ] **Step 1:** `cd frontend; node scripts/check-showcase.mjs` → OK
- [ ] **Step 2:** `cd frontend; npm run build` → exit 0
- [ ] **Step 3:** Reciclar produção: `powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1`
- [ ] **Step 4:** Abrir **https://clipia.com.br** no celular: showcase com vídeos novos, som no toque, filtro funciona, carrossel desliza, hero rotaciona.
- [ ] **Step 5:** Commit final + (opcional) `git push`.
