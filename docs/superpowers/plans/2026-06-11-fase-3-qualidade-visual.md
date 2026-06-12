# Fase 3 — Qualidade Visual & Sincronização Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevar a qualidade visual da saída (transições default, Ken Burns no Remotion, mídia de imagens IA no editor) e fechar o gap de sincronização texto-de-cena → narração.

**Architecture:** O export editado já renderiza via Remotion (Fase 2, híbrido). Esta fase porta o Ken Burns para o Remotion (paridade com o FFmpeg da geração inicial), expõe as imagens IA (`images/scene_N.png`) no editor/export, aplica transição default `fade` nos roteiros novos, e adiciona um guard no editor: texto de cena alterado sem regenerar TTS gera aviso antes do export.

**Tech Stack:** Python 3.12 + FastAPI (backend), Remotion 4 + React 19 + Next.js 16 (frontend). Testes: pytest (backend), `npx tsc --noEmit` + validação manual (frontend — projeto não tem unit tests de front).

**Pré-requisitos de ambiente:** stack rodando (`scripts/start-production.ps1` ou manual), `.venv312` ativável, `cd frontend; npx next typegen` antes de `tsc`.

---

### Task 1: Imagens IA (`images/scene_N.png`) como mídia no editor e no export Remotion

Jobs do template `novelinha_historica` guardam as cenas como `storage/jobs/{id}/images/scene_1.png … scene_N.png` (1-based, ver `app/worker/tasks.py:226`). O endpoint `GET /jobs/{id}/composition` (`app/api/routes.py:558-568`) e o `build_composition_props` (`app/services/remotion.py`) só listam `media/scene_*.mp4` → editor abre sem mídia e o export Remotion não inclui as imagens.

**Files:**
- Modify: `app/services/remotion.py` (função `build_composition_props`, bloco de descoberta de mídia)
- Modify: `app/api/routes.py` (em `get_composition`, bloco que monta `media_urls`, ~linhas 558-568)
- Test: `tests/test_remotion.py`

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/test_remotion.py`:

```python
def test_build_props_falls_back_to_ai_images(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = tmp_path / "jobs" / "job4"
    (job_dir / "images").mkdir(parents=True)
    (job_dir / "media").mkdir()
    (job_dir / "script.json").write_text(
        json.dumps({"title": "T", "scenes": [{"text": "a", "duration_hint": 5}, {"text": "b", "duration_hint": 5}]}),
        encoding="utf-8",
    )
    (job_dir / "words.json").write_text(json.dumps([]), encoding="utf-8")
    # imagens 1-based como o worker grava (tasks.py: scene_{i+1}.png)
    (job_dir / "images" / "scene_1.png").write_bytes(b"x")
    (job_dir / "images" / "scene_2.png").write_bytes(b"x")

    props = build_composition_props("job4", backend_url="http://x:8005")

    assert props["mediaUrls"] == [
        "http://x:8005/storage/jobs/job4/images/scene_1.png",
        "http://x:8005/storage/jobs/job4/images/scene_2.png",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_remotion.py::test_build_props_falls_back_to_ai_images -v`
Expected: FAIL — `props["mediaUrls"] == []`

- [ ] **Step 3: Implement in `app/services/remotion.py`**

No `build_composition_props`, substituir o bloco de descoberta de mídia:

```python
    media_dir = job_dir / "media"
    images_dir = job_dir / "images"
    bg = media_dir / "background.mp4"
    if bg.exists():
        media_files = [bg]
    else:
        media_files = sorted(media_dir.glob("scene_*.mp4"), key=lambda p: int(p.stem.split("_")[1]))
        if not media_files and images_dir.exists():
            # Jobs ai_image (novelinha): cenas sao PNGs 1-based gerados pelo worker
            media_files = sorted(images_dir.glob("scene_*.png"), key=lambda p: int(p.stem.split("_")[1]))
```

E a função `url()` já cobre (o caminho relativo inclui `images/` ou `media/`): ajustar a montagem para usar o diretório-pai real:

```python
    props["mediaUrls"] = [url(f"{p.parent.name}/{p.name}") for p in media_files]
```

(no dict `props`, trocar a linha `"mediaUrls": [url(f"media/{p.name}") for p in media_files],` por `"mediaUrls": [url(f"{p.parent.name}/{p.name}") for p in media_files],`)

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_remotion.py -v`
Expected: todos PASS (incluindo os 3 antigos — o caminho `media/` continua coberto por `p.parent.name`)

- [ ] **Step 5: Mesmo fallback no endpoint `/composition`**

Em `app/api/routes.py`, função `get_composition`, depois do loop que monta `media_urls` com `media/scene_{i}.mp4`, adicionar fallback:

```python
    if not media_urls:
        images_dir = job_dir / "images"
        if images_dir.exists():
            for p in sorted(images_dir.glob("scene_*.png"), key=lambda x: int(x.stem.split("_")[1])):
                media_urls.append(f"/storage/jobs/{job_id}/images/{p.name}")
```

- [ ] **Step 6: Run full backend suite**

Run: `.\.venv312\Scripts\python.exe -m pytest -q`
Expected: 234+ passed (nenhuma regressão)

- [ ] **Step 7: Commit**

```bash
git add app/services/remotion.py app/api/routes.py tests/test_remotion.py
git commit -m "feat(editor): jobs ai_image expoem images/scene_N.png no /composition e no export Remotion"
```

---

### Task 2: Ken Burns no Remotion (SceneClip) para cenas de imagem

Hoje `SceneClip` (`frontend/src/remotion/compositions/SceneClip.tsx`) só usa `OffthreadVideo` — uma URL de PNG renderiza estático (ou quebra). O FFmpeg da geração inicial aplica zoompan alternado (`compositor.py::_prepare_static_image`); portar o efeito para o preview+export Remotion.

**Files:**
- Modify: `frontend/src/remotion/compositions/SceneClip.tsx` (arquivo inteiro, hoje 20 linhas)
- Modify: `frontend/src/remotion/compositions/ShortVideoComposition.tsx` (call sites de `<SceneClip>`: linhas ~54, ~66 e ~122)

- [ ] **Step 1: Reescrever `SceneClip.tsx`**

```tsx
import { AbsoluteFill, Img, OffthreadVideo, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'

const IMAGE_RE = /\.(png|jpe?g|webp)(\?|$)/i

export const SceneClip: React.FC<{
  mediaUrl: string
  sceneIndex?: number
  durationInFrames?: number
}> = ({ mediaUrl, sceneIndex = 0, durationInFrames }) => {
  const { width, height } = useVideoConfig()
  const frame = useCurrentFrame()

  if (IMAGE_RE.test(mediaUrl)) {
    // Ken Burns: zoom-in nas cenas pares, zoom-out nas impares (paridade com o FFmpeg)
    const dur = Math.max(1, durationInFrames ?? 150)
    const zoomIn = sceneIndex % 2 === 0
    const scale = interpolate(frame, [0, dur], zoomIn ? [1.0, 1.12] : [1.12, 1.0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    })
    return (
      <AbsoluteFill style={{ overflow: 'hidden' }}>
        <Img
          src={mediaUrl}
          style={{ width, height, objectFit: 'cover', transform: `scale(${scale})` }}
        />
      </AbsoluteFill>
    )
  }

  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={mediaUrl}
        style={{ width, height, objectFit: 'cover' }}
      />
    </AbsoluteFill>
  )
}
```

- [ ] **Step 2: Passar `sceneIndex`/`durationInFrames` nos call sites**

Em `ShortVideoComposition.tsx`:
- Linha ~122 (layout fullscreen, dentro do `TransitionSeries.Sequence`):
  `{i < mediaUrls.length && <SceneClip mediaUrl={mediaUrls[i]} sceneIndex={i} durationInFrames={sf.duration} />}`
- Linhas ~54 e ~66 (split_horizontal e character_overlay usam 1 vídeo só): manter `<SceneClip mediaUrl={mediaUrls[0]} />` (sem Ken Burns — são vídeos de gameplay).

- [ ] **Step 3: Typecheck**

Run: `cd frontend; npx next typegen; npx tsc --noEmit`
Expected: exit 0

- [ ] **Step 4: Validar com export real (smoke manual)**

Com a stack rodando e um job `novelinha_historica` existente (ou gerar um), abrir o editor — as imagens devem aparecer com zoom lento no preview — e exportar:

```powershell
# render via Remotion (usa o job ai_image; ver job ids em storage/jobs/)
.\.venv312\Scripts\python.exe -m scripts.build_remotion_props <JOB_ID> storage\remotion-spike\props-novelinha.json
cd frontend
node scripts\render-composition.mjs --props ..\storage\remotion-spike\props-novelinha.json --out ..\storage\remotion-spike\novelinha.mp4
```

Expected: MP4 válido com as imagens animadas (zoom alternado). Conferir 2 frames: `ffmpeg -ss 1 -i ...novelinha.mp4 -frames:v 1 f1.png` e `-ss 4` — o enquadramento deve mudar.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/remotion/compositions/SceneClip.tsx frontend/src/remotion/compositions/ShortVideoComposition.tsx
git commit -m "feat(remotion): Ken Burns em cenas de imagem no preview e export"
```

---

### Task 3: Transição default `fade` nos roteiros novos

O Remotion suporta `scene.transition` (fade/slide/wipe) e o SceneGrid já tem picker — mas o roteirista nunca seta, então vídeos novos saem com corte seco (`none`). Default: `fade` para cena 1+ (a transição é de ENTRADA da cena i, i>0; a cena 0 não tem).

**Files:**
- Modify: `app/services/scriptwriter.py` (após `_fix_durations` no `generate_script`)
- Test: `tests/test_scriptwriter.py`

- [ ] **Step 1: Write the failing test**

Adicionar em `tests/test_scriptwriter.py`:

```python
def test_generate_script_applies_default_fade_transitions():
    fake = json.dumps({
        "title": "T",
        "narration": "abc",
        "scenes": [
            {"text": "a", "keywords_en": [], "duration_hint": 10},
            {"text": "b", "keywords_en": [], "duration_hint": 10},
            {"text": "c", "keywords_en": [], "duration_hint": 10},
        ],
        "hashtags": [],
    })
    with patch("app.services.scriptwriter.complete_text", return_value=fake):
        result = generate_script("tema", "educational", 30)

    scenes = result["scenes"]
    assert "transition" not in scenes[0] or scenes[0].get("transition") in (None, "none")
    assert scenes[1]["transition"] == "fade"
    assert scenes[2]["transition"] == "fade"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_scriptwriter.py -v`
Expected: FAIL — `KeyError: 'transition'`

- [ ] **Step 3: Implement**

Em `app/services/scriptwriter.py`, adicionar após a definição de `_fix_durations`:

```python
def _apply_default_transitions(script: dict) -> dict:
    """Cenas novas entram com fade por default (cena 0 nao tem transicao de entrada)."""
    for i, scene in enumerate(script.get("scenes", [])):
        if i > 0 and not scene.get("transition"):
            scene["transition"] = "fade"
    return script
```

E no `generate_script`, logo após `script = _fix_durations(script, duration_target)`:

```python
    script = _apply_default_transitions(script)
```

- [ ] **Step 4: Run tests**

Run: `.\.venv312\Scripts\python.exe -m pytest tests/test_scriptwriter.py tests/test_scriptwriter_visual_hint.py -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/scriptwriter.py tests/test_scriptwriter.py
git commit -m "feat(scriptwriter): transicao fade default entre cenas"
```

---

### Task 4: Guard texto→TTS no editor (aviso antes do export)

Editar o texto de uma cena no SceneGrid não regenera a narração — o MP4 exportado mantém áudio/legendas antigos. Adicionar flag `narrationStale` no `EditorContext` e, no `ExportPanel`, NÃO auto-disparar o render quando stale: mostrar aviso com escolha.

**Files:**
- Modify: `frontend/src/contexts/EditorContext.tsx`
- Modify: `frontend/src/components/editor/ExportPanel.tsx`

- [ ] **Step 1: Flag no EditorContext**

Em `frontend/src/contexts/EditorContext.tsx`:

1. Na interface `EditorContextValue`, adicionar (junto dos demais campos de estado):
```ts
  narrationStale: boolean
```

2. No `EditorProvider`, adicionar estado + baseline (após `const playerRef = ...`):
```ts
  const [narrationStale, setNarrationStale] = useState(false)
  const baselineTextsRef = useRef<string[]>([])
```

3. No `useEffect` de load (`fetchComposition(jobId).then((data) => { ... })`), após `setComposition(data)`:
```ts
        baselineTextsRef.current = data.scenes.map((s: Scene) => s.text)
```

4. No `updateScene`, antes do `updateComposition(...)`:
```ts
    if (updates.text !== undefined && updates.text !== baselineTextsRef.current[index]) {
      setNarrationStale(true)
    }
```

5. No `updateAudio` (chamado após regenerar TTS), dentro do updater — a narração nova passa a ser a baseline:
```ts
  const updateAudio = useCallback((words: Array<Record<string, unknown>>, audioUrl: string) => {
    updateComposition((prev) => {
      baselineTextsRef.current = prev.scenes.map((s) => s.text)
      return {
        ...prev,
        words: words as unknown as CompositionData['words'],
        audioUrl,
      }
    })
    setNarrationStale(false)
  }, [updateComposition])
```

6. Adicionar `narrationStale` ao objeto `value`.

- [ ] **Step 2: Aviso no ExportPanel (sem auto-render quando stale)**

Em `frontend/src/components/editor/ExportPanel.tsx`:

1. Pegar do contexto: `const { composition, jobId, narrationStale, setActivePanel } = useEditor()`
2. Adicionar estado: `const [staleAccepted, setStaleAccepted] = useState(false)`
3. Trocar o `useEffect` de auto-render (linhas ~103-106) por:
```ts
  useEffect(() => {
    if (!narrationStale) handleRender()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
```
4. Logo após o `<h2>Exportar Vídeo</h2>`, renderizar o aviso quando `narrationStale && !staleAccepted`:
```tsx
        {narrationStale && !staleAccepted && (
          <div style={{
            background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)',
            borderRadius: 8, padding: 12, marginBottom: 12, fontSize: 13, color: '#fbbf24',
          }}>
            O texto das cenas mudou desde a última narração. Se exportar agora, o áudio e as
            legendas NÃO vão refletir o novo texto.
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button
                onClick={() => { setActivePanel('voice'); onClose() }}
                style={{ background: '#6C5CE7', color: '#fff', border: 'none', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}
              >
                Regenerar narração primeiro
              </button>
              <button
                onClick={() => { setStaleAccepted(true); handleRender() }}
                style={{ background: 'rgba(255,255,255,0.08)', color: '#ccc', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6, padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}
              >
                Exportar mesmo assim
              </button>
            </div>
          </div>
        )}
```
5. Atualizar a mensagem de progresso (linha ~180): trocar `Atualizando com suas edições... (~15s)` por `Atualizando com suas edições... (~2 min)` — o export agora é Remotion (~105s).

- [ ] **Step 3: Typecheck**

Run: `cd frontend; npx next typegen; npx tsc --noEmit`
Expected: exit 0

- [ ] **Step 4: Validação manual (fluxo completo)**

1. Abrir um job no editor, editar o texto de uma cena no SceneGrid.
2. Clicar "Exportar Vídeo" → deve aparecer o aviso âmbar (sem render automático).
3. "Regenerar narração primeiro" → vai para a aba Voz; clicar "Regerar narração"; reabrir export → sem aviso, render dispara.
4. Repetir 1-2 e escolher "Exportar mesmo assim" → render dispara.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/EditorContext.tsx frontend/src/components/editor/ExportPanel.tsx
git commit -m "feat(editor): aviso de narracao desatualizada antes do export + mensagem ~2min"
```

---

### Task 5: Verificação end-to-end da fase

- [ ] **Step 1: Suíte completa backend**

Run: `.\.venv312\Scripts\python.exe -m pytest -q`
Expected: 236+ passed

- [ ] **Step 2: Build de produção do frontend**

Run: `cd frontend; npm run build`
Expected: exit 0. Depois reciclar a stack: `powershell -ExecutionPolicy Bypass -File scripts\start-production.ps1`

- [ ] **Step 3: Smoke no produto real**

Gerar 1 vídeo `stock_narration` novo (deve sair com transições fade entre cenas), abrir no editor, mudar texto de uma cena, conferir o aviso, regenerar, exportar, baixar e assistir.

- [ ] **Step 4: Commit final (se sobrou algo) e atualizar CLAUDE.md**

Atualizar a linha do gotcha "Export nao re-renderiza" no `CLAUDE.md` (raiz) — está obsoleta desde a Fase 2; descrever o híbrido (FFmpeg inicial + Remotion no export).
