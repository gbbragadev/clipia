# Handoff de Revisão — Elevação de Frontend ClipIA

> **Para: sessão Opus 4.8 (revisora).** Documento exaustivo do trabalho de elevação de frontend feito pela sessão GLM-5.2-max na branch `feat/frontend-elevacao` (29/06). Use isto para **revisar o que foi feito** e **decidir o que falta**. Se houver sobreposição com seu go-live, coordene via `docs/SESSION-COORD.md`.

## TL;DR
- **Objetivo original**: melhorar (NÃO refazer) todo o frontend — usabilidade, mobile, criatividade, fluidez, impacto visual. Faseado, deps liberadas.
- **4 fases + 2 polishes entregues e commitadas** (build + tsc verdes em cada uma).
- **Dependências adicionadas**: `motion`, `lucide-react`, `geist`. Radix **removido** (registry quebrado).
- **Pendências**: mapeadas exaustivamente na Seção 3 (auth é território seu — não toquei).

---

## 1. Commits (branch `feat/frontend-elevacao`)

| Commit | Fase | Autor | Resumo |
|--------|------|-------|--------|
| `b09e61f` | Fase 0 | GLM (esta) | Fundação: Geist+Sora, tokens de motion, reduced-motion, utilities |
| `c754782` | Fase 1 | **Opus (você)** | Navbar/Hero/Showcase — capturado no seu commit de go-live ("trabalho concomitante") |
| `e184c83` | Fase 2/3 | GLM (esta) | Dashboard, login, editor (ícones abas) |
| `a8c4f13` | Editor | GLM (esta) | Drawer timeline animado (enter+exit motion) |
| `faab896` | Polish | GLM (esta) | VideoGrid stagger, NicheGallery skeleton, ícone Exportar |

> ⚠️ **Atenção**: a Fase 1 (Navbar/Hero/Showcase) foi commitada por VOCÊ dentro de `c754782`. Meu código da Fase 1 está lá, mas mesclado com seu go-live. Ao revisar, saiba que Navbar/Showcase/Hero são de autoria mista.

---

## 2. O que foi feito (detalhado por fase)

### Fase 0 — Fundação (`b09e61f`)
- **Tipografia**: `Geist` (corpo) + `Sora` (display) via `next/font` (`layout.tsx` → vars `--font-geist-sans`/`--font-sora` → `globals.css` reescreve `--font-inter`/`--font-display`). Uma edição muda todo o corpo do site.
- **`lib/motion.ts`** (NOVO): tokens — `EASE` (easeOutExpo `[0.22,1,0.36,1]`), `DURATIONS`, `SPRING`, variants `fadeUp`/`fadeIn`/`scaleIn`/`staggerContainer`, `useReducedMotionState()`.
- **`globals.css`**: utilities semânticas (`.text-2/.text-3/.bg-surface/.bg-raised/.border-subtle`) + escala tipográfica fluida (`.h-display/.h-1/.h-2` com `clamp`).
- **A11y**: `prefers-reduced-motion` — guards JS em `useCountUp`/`CinematicSection` + rede de segurança CSS global (zera transições/animações).

### Fase 1 — Vitrine (`c754782`, autoria mista)
- **Navbar**: menu mobile animado (`AnimatePresence` height+opacity), ESC fecha, backdrop outside-click, scroll-aware (sombra ao rolar), ícones lucide (`LayoutDashboard`/`LogIn`).
- **Showcase**: `preload="none"` + pausa off-screen (perf mobile), skeleton no loading do manifesto, stagger dos cards.
- **Hero**: CTAs com `whileHover`/`whileTap` (SPRING).

### Fase 2/3 — App logada + editor (`e184c83`)
- **Dashboard**: títulos com `font-display` (Sora), ícone `Mail` no banner de verificação de e-mail.
- **Login**: toggle de senha (`Eye`/`EyeOff`), `autoFocus` no e-mail.
- **Editor**: 5 abas com ícones lucide (`Layers`/`Mic`/`Captions`/`Shapes`/`Sparkles`), FAB `Clock`, close `X`.

### Editor drawer (`a8c4f13`)
- Gaveta da timeline mobile: enter (slide-up) + **exit** (slide-down) via `AnimatePresence`+`motion`, backdrop fade, reduced-motion. Removida `@keyframes drawer-up` obsoleta do `editor.css`.
- **Bottom-nav mobile já existia** no `editor.css` (`order:2` + `min-height:52px` + safe-area) — confirmado, sem mudança.

### Polish final (`faab896`)
- `VideoGrid`: stagger de entrada (motion), reduced-motion.
- `NicheGallery`: skeleton no carregamento (era `return null` → flash).
- Editor: botão Exportar com ícone `Download`.

---

## 3. Mapeamento EXAUSTIVO do restante (pendências)

> Priorizado por impacto. Cada item tem arquivo + ação. **Marcar no `docs/SESSION-COORD.md` ao pegar.**

### 🔴 A. Auth — TERRITÓRIO DA SESSÃO OPUS (não toquei)
O working tree tem `M AuthContext.tsx`, `M lib/auth.ts`, `?? components/auth/` (TurnstileWidget) — sua frente. Pendências de UI para quando finalizar o captcha:
- **`/auth/register/page.tsx`**: validação de senha já existe (min 8, maiúscula, número). Faltam: toggle `Eye`/`EyeOff` (como no login), **medidor visual de força** (barrinha de 4 critérios), `autoFocus` no campo nome.
- **`/auth/forgot-password`**, **`/auth/reset-password`**, **`/auth/verify`**: aplicar padrão consistente (toggle senha, autofocus, ícones). Não foram auditados — revisar conteúdo.

### 🟡 B. Landing — seções NÃO tocadas (polish lighter)
Aplicar ícones lucide + tokens de motion consistentes. Auditorar (não refazer):
- `SocialProofBar.tsx` / `SocialProofCanvas.tsx`
- `HowItWorks.tsx` / `HowItWorksStepCanvas.tsx`
- `demo/DemoSection.tsx` / `demo/GenerateForm.tsx` / `demo/ProgressBar.tsx` / `demo/VideoPlayer.tsx`
- `WaitlistForm.tsx` (CTA com spring, ícone)
- `Footer.tsx` (ícones de redes sociais?)
- `ShowcasePretextOverlay.tsx`

### 🟡 C. Dashboard — componentes NÃO tocados
- **`GenerateForm.tsx`** (396L): ícones lucide nos seletores (`TemplateSelector`/`StyleSelector`/`WpmSlider`), tokens de motion. **Cirúrgico** — tem `KineticPreviewPanel`/`ScriptDensityHeatmap`/`OpticalBalancePreview`/`NarrationTimelineRuler` (não refazer).
- **`TrendingPanel.tsx`**: ícone `TrendingUp`.
- **`ReferralCard.tsx`**: ícone `Gift`/`Copy` + feedback de copiar.
- Revisar polish: `FilterBar`, `CreditsBadge`, `CreditPackageCard`, `PurchaseHistory`, `ExportCostBanner`, `UserDropdown`, `DashboardNavbar`, `EmptyState`.

### 🟡 D. Editor — pendências
- **`EditorLayout.tsx`**: panel toggle `◂`/`▸` → `ChevronLeft`/`ChevronRight`; status de save com microanimação.
- **Panels** (`SceneGrid`/`VoiceSelector`/`SubtitleEditor`/`OverlayPicker`/`MusicSelector`/`AIAssistant`): transição entre painéis (`AnimatePresence`), estados vazios/erro consistentes.

### 🟠 E. Cross-cutting / A11y (importante)
- **Canvas + reduced-motion**: a media query CSS NÃO cobre animações via `requestAnimationFrame` em canvas. Pendência real de a11y em: `HeroTitleCanvas`, `PretextCanvas`, `ReelSubtitleCanvas`, `SocialProofCanvas`, `HowItWorksStepCanvas`. Cada um precisa de guard JS (`matchMedia('(prefers-reduced-motion: reduce)')` → parar/pular o loop de animação).
- **View Transitions API** entre rotas (mencionado no plano original): não implementado. Nice-to-have.

### 🔵 F. Verificação NUNCA rodada nesta sessão
- **Smoke visual runtime** (gstack/playwright em 375px e 1280px) nas páginas alteradas: confirmar menu mobile animado, stagger do showcase/videogrid, drawer do editor, toggle de senha login, ícones lucide renderizam. **Só validei compilação (build verde).**
- Playwright specs: `session-expiry.spec.js`, specs de galeria.
- `scripts/validate_readiness.py` (cadastro→OTP→gerar MP4).

---

## 4. Decisões de arquitetura (pra revisar)

- **Fronteira de CSS**: site público = Tailwind v4 + utilities semânticas; editor = `editor.css` (BEM). **Mantida separada** (não unificar).
- **Deps**: `motion` (animação declarativa), `lucide-react` (ícones SVG), `geist` (fonte). **Radix removido** — `@radix-ui/primitive@1.1.4` inexistente no registry (afeta `radix-ui` unificado e os `@radix-ui/react-*`). Overlays fazem com `motion` + hook de outside-click/ESC.
- **Motion no editor**: só no shell (drawer/header), **nunca dentro das composições Remotion** (`remotion/*` intocadas — renderização server-side).
- **Ponytail**: deps só onde custo/benefício claro; máximo reuso (skeletons, GlowCard, ShowcaseCard reaproveitados).

## 5. Riscos / gotchas

- **Sessão concorrente ativa** (Opus 4.8 em go-live + QA mobile). Antes de commitar: `git log --oneline -5` + rebase se houver commit novo. `git add` sempre seletivo.
- **Auth é território da Opus** — não mexer em `AuthContext.tsx`/`lib/auth.ts`/`components/auth/`/`register` sem coordenar.
- **Next 16**: `npx next typegen` antes de `tsc --noEmit`; build roda typecheck interno.
- **cwd do Bash resetou** pra raiz algumas vezes — sempre `cd /c/Dev/clipia/frontend` em comandos npm.
- **`lucide-react@1.18.0`**: confirmar que é o pacote canônico (não fork) — importei ícones padrão (`Layers`/`Mic`/`Captions`/`Shapes`/`Sparkles`/`Clock`/`X`/`Download`/`Mail`/`Eye`/`EyeOff`/`LayoutDashboard`/`LogIn`), todos resolvidos no build.

## 6. Checklist de revisão para o Opus
- [ ] Confirmar que Fase 1 (Navbar/Hero/Showcase em `c754782`) está íntegra e sem regressão do seu go-live.
- [ ] Rodar smoke visual mobile (375px) nas 4 superfícies.
- [ ] Auditar pendências da Seção 3 e priorizar.
- [ ] Decidir: concluir canvas+reduced-motion (E) ou auth (A) primeiro.
- [ ] Após revisão, atualizar `docs/SESSION-COORD.md` e a memória `frontend-elevacao-fases.md`.

— *Sessão GLM-5.2-max, 29/06 ~19h.*
