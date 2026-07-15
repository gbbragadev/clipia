# Clypra-Inspired Editor Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer a timeline do editor ClipIA com zoom, filmstrips, waveform e reordenação acessível, preservando o fluxo simples e a fidelidade Remotion.

**Architecture:** O frontend continua usando `CompositionData` e `EditorContext`; um helper puro controla spans, zoom e permutações. O cliente salva somente `sceneOrder`, e o backend valida essa permutação antes de aplicá-la aos arquivos autoritativos do job. Componentes isolados cuidam de thumbnail e waveform sem introduzir dependências do Clypra.

**Tech Stack:** Next.js 16, React 19, TypeScript, Remotion 4, Web Audio API, Playwright, FastAPI/Pydantic, pytest.

## Global Constraints

- Manter `EditorContext`, Remotion Player e o renderer Remotion existentes.
- Não adicionar Tauri, Rust, FFmpeg local, Capacitor, Zustand ou pacotes do Clypra.
- Não aceitar URLs ou paths de mídia enviados pelo cliente no renderer.
- Nenhuma migration, variável de ambiente, preço ou API pública nova.
- Desktop recebe a timeline rica inline; mobile mantém a gaveta fechada por padrão.
- O documento não pode ter overflow em 320, 390 ou 393 px.
- Preservar todos os artefatos untracked existentes.
- Antes de alterar componentes Next, ler a documentação local relevante em `frontend/node_modules/next/dist/docs/`.

---

## Mapa de arquivos

- Criar `app/services/scene_order.py`: validação e aplicação segura de permutações.
- Modificar `app/models.py`: validação estrutural de `sceneOrder` no autosave.
- Modificar `app/api/routes.py`: validação contextual e ordenação no composition endpoint.
- Modificar `app/services/remotion.py`: ordenar URLs autoritativas antes do render.
- Modificar `app/worker/tasks.py`: ordenar paths autoritativos no fallback FFmpeg.
- Criar `tests/test_scene_order.py`: contrato puro e segurança.
- Modificar `tests/test_remotion.py` e `tests/test_asset_security.py`: fidelidade e payload hostil.
- Criar `frontend/src/lib/editor-timeline.ts`: spans, zoom, identidade e reorder imutável.
- Criar `frontend/src/lib/editor-timeline.test.ts`: testes Node nativos do helper.
- Modificar `frontend/src/remotion/types.ts`: `sceneOrder` interno.
- Modificar `frontend/src/lib/editor-api.ts`: hidratação compatível e aplicação da ordem à mídia.
- Modificar `frontend/src/contexts/EditorContext.tsx`: ação de reorder e stale/undo.
- Criar `frontend/src/components/editor/SceneThumbnail.tsx`: thumbnail com cache e fallback.
- Criar `frontend/src/components/editor/NarrationWaveform.tsx`: waveform RMS com cache.
- Modificar `frontend/src/components/editor/SceneGrid.tsx`: reutilizar thumbnail.
- Modificar `frontend/src/components/editor/EditorTimeline.tsx`: UI rica e interações.
- Modificar `frontend/src/components/editor/editor.css`: layout, zoom, touch e overflow local.
- Criar `frontend/tests/editor-advanced-timeline.spec.js`: desktop/mobile/autosave.

---

### Task 1: Contrato seguro de ordem de cenas no backend

**Files:**
- Create: `app/services/scene_order.py`
- Modify: `app/models.py:183-211`
- Modify: `app/api/routes.py:1532-1606,1620-1662`
- Modify: `app/services/remotion.py:45-155`
- Modify: `app/worker/tasks.py:2390-2479`
- Create: `tests/test_scene_order.py`
- Modify: `tests/test_remotion.py`
- Modify: `tests/test_asset_security.py`

**Interfaces:**
- Produces: `identity_scene_order(scene_count: int) -> list[int]`
- Produces: `validate_scene_order(value: object, scene_count: int, *, strict: bool) -> list[int]`
- Produces: `apply_scene_order(items: Sequence[T], order: Sequence[int]) -> list[T]`
- Consumes: `composition.sceneOrder` somente como índices; nunca consome `mediaUrls` do cliente.

- [ ] **Step 1: Escrever os testes backend falhando**

```python
# tests/test_scene_order.py
import pytest

from app.services.scene_order import apply_scene_order, validate_scene_order


def test_valid_scene_order_reorders_authoritative_items():
    order = validate_scene_order([2, 0, 1], 3, strict=True)
    assert apply_scene_order(["scene_0.mp4", "scene_1.mp4", "scene_2.mp4"], order) == [
        "scene_2.mp4", "scene_0.mp4", "scene_1.mp4"
    ]


@pytest.mark.parametrize("value", [[0, 0], [-1, 0], [0], [0, 2], [True, 0]])
def test_invalid_scene_order_is_rejected_in_strict_mode(value):
    with pytest.raises(ValueError):
        validate_scene_order(value, 2, strict=True)


def test_invalid_legacy_scene_order_falls_back_to_identity():
    assert validate_scene_order([1, 1], 2, strict=False) == [0, 1]


def test_order_is_not_applied_when_asset_count_differs():
    assert apply_scene_order(["background.mp4"], [1, 0]) == ["background.mp4"]
```

Adicionar em `tests/test_remotion.py` um job de três cenas com `sceneOrder=[2,0,1]`, `mediaUrls`
malicioso no JSON e a asserção de que o resultado usa apenas `scene_2`, `scene_0`, `scene_1` do
storage. Adicionar em `tests/test_asset_security.py` casos duplicados, negativos e booleanos.

- [ ] **Step 2: Executar os testes e confirmar RED**

Run:

```powershell
pytest -q tests/test_scene_order.py tests/test_remotion.py tests/test_asset_security.py
```

Expected: FAIL com `ModuleNotFoundError: app.services.scene_order` ou ausência de ordenação.

- [ ] **Step 3: Implementar o helper mínimo**

```python
# app/services/scene_order.py
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def identity_scene_order(scene_count: int) -> list[int]:
    return list(range(max(0, scene_count)))


def validate_scene_order(value: object, scene_count: int, *, strict: bool) -> list[int]:
    identity = identity_scene_order(scene_count)
    valid = (
        isinstance(value, list)
        and len(value) == scene_count
        and all(type(index) is int for index in value)
        and sorted(value) == identity
    )
    if valid:
        return list(value)
    if value is not None and strict:
        raise ValueError("invalid scene order")
    return identity


def apply_scene_order(items: Sequence[T], order: Sequence[int]) -> list[T]:
    if len(items) != len(order):
        return list(items)
    return [items[index] for index in order]
```

No validator de `EditRequest`, rejeitar listas maiores que 100, valores não inteiros, negativos ou
duplicados. Na rota de autosave, após obter o job e antes do update, chamar
`validate_scene_order(order, len(comp.get("scenes", [])), strict=True)` e converter erro em 422.

No composition endpoint, em `build_composition_props` e no fallback FFmpeg, chamar o helper somente
sobre `media_urls`/`media_paths` enumerados no storage. O script já é sincronizado pelo autosave e
não deve ser reordenado uma segunda vez.

- [ ] **Step 4: Rodar testes backend e confirmar GREEN**

```powershell
pytest -q tests/test_scene_order.py tests/test_remotion.py tests/test_asset_security.py tests/test_data_consistency.py
```

Expected: todos PASS; payload hostil não altera URLs/paths renderizados.

- [ ] **Step 5: Commit**

```powershell
git add -- app/services/scene_order.py app/models.py app/api/routes.py app/services/remotion.py app/worker/tasks.py tests/test_scene_order.py tests/test_remotion.py tests/test_asset_security.py
git commit -m 'feat: secure editor scene ordering'
```

---

### Task 2: Modelo de timeline e ação de reordenação no frontend

**Files:**
- Create: `frontend/src/lib/editor-timeline.ts`
- Create: `frontend/src/lib/editor-timeline.test.ts`
- Modify: `frontend/src/remotion/types.ts`
- Modify: `frontend/src/lib/editor-api.ts`
- Modify: `frontend/src/contexts/EditorContext.tsx`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: `sceneOrder` validado pelo backend ou identidade.
- Produces: `clampTimelineZoom(value: number): number`
- Produces: `getSceneSpans(scenes: Scene[]): Array<{start: number; end: number; duration: number}>`
- Produces: `reorderComposition(composition: CompositionData, from: number, to: number): CompositionData`
- Produces: `EditorContext.reorderScenes(fromIndex: number, toIndex: number): void`

- [ ] **Step 1: Ler a documentação Next local relevante**

```powershell
rg --files frontend/node_modules/next/dist/docs | rg 'client-components|lazy-loading|testing'
```

Ler integralmente o guia de Client Components encontrado. Não mudar App Router nem adicionar API
obsoleta.

- [ ] **Step 2: Escrever o teste unitário falhando**

```ts
// frontend/src/lib/editor-timeline.test.ts
import assert from 'node:assert/strict'
import test from 'node:test'
import { clampTimelineZoom, getSceneSpans, reorderComposition } from './editor-timeline.ts'

const composition = {
  scenes: [
    { text: 'A', keywords_en: [], duration_hint: 2 },
    { text: 'B', keywords_en: [], duration_hint: 3 },
    { text: 'C', keywords_en: [], duration_hint: 5 },
  ],
  mediaUrls: ['m0', 'm1', 'm2'],
  sceneOrder: [0, 1, 2],
} as any

test('reorder keeps scenes media and physical order aligned', () => {
  const next = reorderComposition(composition, 2, 0)
  assert.deepEqual(next.scenes.map((scene: any) => scene.text), ['C', 'A', 'B'])
  assert.deepEqual(next.mediaUrls, ['m2', 'm0', 'm1'])
  assert.deepEqual(next.sceneOrder, [2, 0, 1])
  assert.equal(next.narrationStale, true)
  assert.deepEqual(composition.sceneOrder, [0, 1, 2])
})

test('invalid and no-op reorder return the original object', () => {
  assert.equal(reorderComposition(composition, -1, 0), composition)
  assert.equal(reorderComposition(composition, 1, 1), composition)
})

test('zoom and spans are bounded and proportional', () => {
  assert.equal(clampTimelineZoom(0.1), 1)
  assert.equal(clampTimelineZoom(9), 3)
  assert.deepEqual(getSceneSpans(composition.scenes), [
    { start: 0, end: 0.2, duration: 2 },
    { start: 0.2, end: 0.5, duration: 3 },
    { start: 0.5, end: 1, duration: 5 },
  ])
})
```

Adicionar `"test:editor-unit": "node --test src/lib/editor-timeline.test.ts"` aos scripts.

- [ ] **Step 3: Executar e confirmar RED**

```powershell
cd frontend
npm.cmd run test:editor-unit
```

Expected: FAIL porque `editor-timeline.ts` ainda não existe.

- [ ] **Step 4: Implementar helper, tipo e hidratação mínimos**

```ts
// frontend/src/lib/editor-timeline.ts
import type { CompositionData, Scene } from '@/remotion/types'

export const MIN_TIMELINE_ZOOM = 1
export const MAX_TIMELINE_ZOOM = 3

export function clampTimelineZoom(value: number) {
  return Math.min(MAX_TIMELINE_ZOOM, Math.max(MIN_TIMELINE_ZOOM, value))
}

export function identitySceneOrder(count: number) {
  return Array.from({ length: count }, (_, index) => index)
}

export function normalizeSceneOrder(value: unknown, count: number) {
  const identity = identitySceneOrder(count)
  return Array.isArray(value) && value.length === count &&
    value.every((item) => Number.isInteger(item)) &&
    [...value].sort((a, b) => a - b).every((item, index) => item === identity[index])
    ? [...value] as number[]
    : identity
}

export function getSceneSpans(scenes: Scene[]) {
  const total = scenes.reduce((sum, scene) => sum + Math.max(0, scene.duration_hint), 0) || 1
  let cursor = 0
  return scenes.map((scene) => {
    const duration = Math.max(0, scene.duration_hint)
    const start = cursor / total
    cursor += duration
    return { start, end: cursor / total, duration }
  })
}

function move<T>(items: T[], from: number, to: number) {
  const copy = [...items]
  const [item] = copy.splice(from, 1)
  copy.splice(to, 0, item)
  return copy
}

export function reorderComposition(composition: CompositionData, from: number, to: number) {
  if (from === to || from < 0 || to < 0 || from >= composition.scenes.length || to >= composition.scenes.length) {
    return composition
  }
  const sceneOrder = normalizeSceneOrder(composition.sceneOrder, composition.scenes.length)
  return {
    ...composition,
    scenes: move(composition.scenes, from, to),
    mediaUrls: composition.mediaUrls.length === composition.scenes.length
      ? move(composition.mediaUrls, from, to)
      : composition.mediaUrls,
    sceneOrder: move(sceneOrder, from, to),
    narrationStale: true,
  }
}
```

Adicionar `sceneOrder: number[]` e `narrationStale?: boolean` a `CompositionData`. Em
`fetchComposition`, normalizar `saved?.sceneOrder`, aplicar a ordem somente a `data.media_urls` e
hidratar `narrationStale` do estado salvo. Em `EditorContext`, tornar stale derivado/salvo na
composition, expor `reorderScenes`, pausar playback, criar uma entrada de histórico e selecionar a
posição final. `updateAudio` deve gravar `narrationStale: false`.

- [ ] **Step 5: Rodar unit test e typecheck**

```powershell
cd frontend
npm.cmd run test:editor-unit
npx.cmd tsc --noEmit
```

Expected: PASS e zero erros TypeScript.

- [ ] **Step 6: Commit**

```powershell
git add -- frontend/package.json frontend/src/lib/editor-timeline.ts frontend/src/lib/editor-timeline.test.ts frontend/src/remotion/types.ts frontend/src/lib/editor-api.ts frontend/src/contexts/EditorContext.tsx
git commit -m 'feat: add immutable editor timeline model'
```

---

### Task 3: Filmstrip compartilhado e waveform real

**Files:**
- Create: `frontend/src/components/editor/SceneThumbnail.tsx`
- Create: `frontend/src/components/editor/NarrationWaveform.tsx`
- Modify: `frontend/src/components/editor/SceneGrid.tsx`
- Modify: `frontend/tests/editor-advanced-timeline.spec.js`

**Interfaces:**
- Produces: `<SceneThumbnail mediaUrl size="grid" | "timeline" />`
- Produces: `<NarrationWaveform audioUrl label="Narração" />`
- Waveform informa `role="img"` e `aria-label`; falha usa `data-waveform-state="unavailable"`.

- [ ] **Step 1: Criar o primeiro teste Playwright falhando**

Criar um harness no spec que intercepta `/api/v1/jobs/job-editor/composition`, `/auth/me` e
`/jobs/job-editor/edit`, devolvendo três cenas e URLs data/same-origin. O teste desktop deve exigir:

```js
await page.goto('/editor/job-editor')
await expect(page.getByRole('img', { name: /filmstrip da cena 1/i })).toBeVisible()
await expect(page.getByRole('img', { name: /waveform da narração/i })).toBeVisible()
await expect(page.locator('[data-waveform-state]')).toHaveAttribute('data-waveform-state', /ready|unavailable/)
```

- [ ] **Step 2: Executar e confirmar RED**

```powershell
cd frontend
npx.cmd playwright test tests/editor-advanced-timeline.spec.js --config=playwright.config.mjs --project=chromium
```

Expected: FAIL porque os elementos ainda não existem.

- [ ] **Step 3: Implementar thumbnail reutilizável**

Usar cache `Map<string,string>` no módulo. Para imagens, renderizar `<img>` diretamente. Para vídeo,
criar `<video crossOrigin="anonymous" muted preload="metadata">`, buscar `currentTime=0.5`, desenhar
canvas limitado a 120x68/120x213 conforme variante e armazenar JPEG 0.65. Limpar listeners e src ao
desmontar. O fallback mantém o `role="img"` e a mesma `aria-label`.

Substituir o componente local de `SceneGrid` pelo novo componente.

- [ ] **Step 4: Implementar waveform RMS**

Buscar `audioUrl` com `AbortController`, chamar `AudioContext.decodeAudioData`, reduzir todos os canais
para no máximo 180 barras e desenhar em canvas responsivo. Usar `ResizeObserver`; fechar o
`AudioContext`; cachear os picos por URL. Falha não lança erro de render e mostra uma linha neutra
com `data-waveform-state="unavailable"`.

- [ ] **Step 5: Rodar Playwright focado e typecheck**

```powershell
cd frontend
npx.cmd playwright test tests/editor-advanced-timeline.spec.js --config=playwright.config.mjs --project=chromium
npx.cmd tsc --noEmit
```

Expected: teste de filmstrip/waveform PASS; sem erros no console da página.

- [ ] **Step 6: Commit**

```powershell
git add -- frontend/src/components/editor/SceneThumbnail.tsx frontend/src/components/editor/NarrationWaveform.tsx frontend/src/components/editor/SceneGrid.tsx frontend/tests/editor-advanced-timeline.spec.js
git commit -m 'feat: add cached filmstrips and narration waveform'
```

---

### Task 4: UI rica da timeline, zoom e reordenação acessível

**Files:**
- Modify: `frontend/src/components/editor/EditorTimeline.tsx`
- Modify: `frontend/src/components/editor/editor.css`
- Modify: `frontend/tests/editor-advanced-timeline.spec.js`

**Interfaces:**
- Consumes: `getSceneSpans`, `clampTimelineZoom`, `reorderScenes`, `SceneThumbnail`, `NarrationWaveform`.
- Produces: controles nomeados `Diminuir zoom`, `Ajustar timeline`, `Aumentar zoom`, `Mover cena N para trás/frente`.

- [ ] **Step 1: Ampliar Playwright e confirmar RED**

Desktop:

```js
await expect(page.getByRole('button', { name: 'Aumentar zoom' })).toBeVisible()
await page.getByRole('button', { name: 'Aumentar zoom' }).click()
await expect(page.locator('[data-timeline-zoom]')).toHaveAttribute('data-timeline-zoom', '1.5')
await page.getByRole('button', { name: 'Mover cena 3 para trás' }).click()
await expect.poll(() => savedComposition.sceneOrder).toEqual([0, 2, 1])
await expect(page.getByText(/narração.*desatualizada/i)).toBeVisible()
await page.getByRole('button', { name: 'Desfazer' }).click()
await expect.poll(() => savedComposition.sceneOrder).toEqual([0, 1, 2])
```

Mobile 320/390/393:

```js
await page.getByRole('button', { name: 'Abrir linha do tempo' }).click()
await expect(page.getByRole('dialog', { name: 'Linha do tempo' })).toBeVisible()
expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(viewport.width)
await expect(page.getByRole('button', { name: 'Mover cena 2 para frente' })).toHaveCSS('min-height', '44px')
```

Executar e confirmar que falha por controles ausentes.

- [ ] **Step 2: Implementar timeline visual**

No `EditorTimeline`:

- estado local `zoom` com passos `1, 1.5, 2, 2.5, 3`;
- wrapper overflow local e faixa interna `minWidth: ${zoom * 100}%`;
- ticks calculados em segundos a partir do total real;
- cards com thumbnail, número, duração, drag handle e dois botões de reorder;
- HTML5 drag/drop apenas quando `matchMedia('(pointer:fine)')` for verdadeiro;
- pointer/click de seek baseado na largura interna, não no viewport;
- waveform e `SubtitleTimeline` dentro da mesma faixa escalada;
- playhead calculado sobre a faixa interna;
- usar ícones Lucide, não caracteres mojibake.

No CSS, manter scroll horizontal somente em `.editor-timeline__viewport`, esconder ações impossíveis,
garantir cards com mínimo legível e 44 px no mobile. A altura desktop pode crescer, mas não deve
reduzir o player abaixo do layout atual.

- [ ] **Step 3: Rodar Playwright focado em todos os viewports**

```powershell
cd frontend
npx.cmd playwright test tests/editor-advanced-timeline.spec.js --config=playwright.config.mjs --project=chromium
```

Expected: desktop, 320, 390 e 393 PASS; autosave contém `sceneOrder`; documento sem overflow.

- [ ] **Step 4: Rodar unidade, typecheck e backend focado**

```powershell
cd frontend
npm.cmd run test:editor-unit
npx.cmd tsc --noEmit
cd ..
pytest -q tests/test_scene_order.py tests/test_remotion.py tests/test_asset_security.py tests/test_data_consistency.py
```

Expected: tudo PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- frontend/src/components/editor/EditorTimeline.tsx frontend/src/components/editor/editor.css frontend/tests/editor-advanced-timeline.spec.js
git commit -m 'feat: enrich editor timeline interactions'
```

---

### Task 5: Regressão, smoke real e relatório deep

**Files:**
- Create (artifact): `outputs/startup-user-simulation-clipia-editor-clypra-incorporation-deep.analysis.json`
- Create (artifact): `outputs/startup-user-simulation-clipia-editor-clypra-incorporation-deep.html`
- Modify only if a regression is reproduced: files covered by Tasks 1-4, always after a new failing test.

**Interfaces:**
- Consumes: candidate local da branch e backend real quando disponível.
- Produces: relatório HTML deep com cinco personas e limitações explícitas.

- [ ] **Step 1: Executar a suíte de release**

```powershell
cd frontend
npm.cmd run test:editor-unit
npx.cmd tsc --noEmit
$env:NEXT_DIST_DIR='.next-clypra-verify'; npm.cmd run build
npm.cmd run test:release-b
cd ..
pytest -q
```

Expected: todos os gates verdes. Não reutilizar `.next` de produção.

- [ ] **Step 2: Subir candidate local sem reiniciar serviços existentes**

Usar porta livre e `NEXT_DIST_DIR` isolado. Se o backend local saudável representar produção, usar
`LOCAL_API_URL=http://127.0.0.1:8005`; caso contrário, usar proxy HTTPS para o backend público. Não
reiniciar Docker, worker ou API sem necessidade comprovada.

- [ ] **Step 3: Executar smoke autenticado do editor**

Com conta QA descartável e créditos, validar:

- login e job editável;
- playback/seek;
- zoom 1→1.5→1;
- reorder por botão e drag;
- autosave e reload preservando ordem;
- undo/redo;
- regeneração da narração;
- Neon + Lo-Fi;
- rerender, saldo e download;
- `ffprobe` do MP4;
- 1280x720 e 390x844, mais overflow automatizado em 320/393.

Anonimizar a conta e remover artefatos sintéticos conforme os scripts operacionais existentes. Se o
candidate usar mocks ou o render real não estiver disponível, registrar exatamente essa limitação.

- [ ] **Step 4: Ler as referências da startup-user-simulator**

Ler integralmente:

```text
C:\Users\guibr\.codex\skills\startup-user-simulator\references\evaluation-framework.md
C:\Users\guibr\.codex\skills\startup-user-simulator\references\report-artifact.md
```

- [ ] **Step 5: Produzir análise deep e HTML**

Criar JSON conforme o schema, com modo `deep + desktop + mobile + editor`, cinco personas distintas,
evidências observadas, top cinco fixes e limites. Gerar:

```powershell
python C:\Users\guibr\.codex\skills\startup-user-simulator\scripts\generate_report.py outputs\startup-user-simulation-clipia-editor-clypra-incorporation-deep.analysis.json outputs\startup-user-simulation-clipia-editor-clypra-incorporation-deep.html
```

Expected: HTML contém verdict, leak, cinco cards, cinco fixes, experimento e limites.

- [ ] **Step 6: Validar artefato e working tree**

```powershell
Select-String -LiteralPath outputs\startup-user-simulation-clipia-editor-clypra-incorporation-deep.html -Pattern 'Verdict|Persona|Simulated decision score|Limits'
git status --short --branch
```

Não adicionar os artefatos untracked preexistentes ao commit. Entregar link absoluto para o HTML e
separar nota simulada de conversão real.
