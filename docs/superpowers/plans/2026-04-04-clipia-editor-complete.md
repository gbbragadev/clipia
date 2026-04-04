# ClipIA Editor — Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-quality short-form video editor with TikTok-grade overlays, interactive timeline, AI assistant, voice selection, and social sharing.

**Architecture:** React 19 + Next.js 16 frontend with Remotion 4 for video composition preview. FastAPI + Celery backend for TTS/render. CSS Grid 3-zone layout (header/workspace/timeline). PlayerRef shared via context for unified seek/play control. All edits are instant (optimistic updates), auto-saved to backend.

**Tech Stack:** React 19, Next.js 16, Remotion 4.0.443 (@remotion/transitions, captions, shapes, noise, google-fonts), Tailwind CSS 4, FastAPI, Edge TTS, Claude API, FFmpeg+NVENC.

---

## File Structure

### New Files
```
frontend/src/components/editor/overlays/TikTokCaptions.tsx    — TikTok auto-caption style (karaoke word highlighting)
frontend/src/components/editor/overlays/ImpactCaptions.tsx     — CapCut impact style (bold, colored, pop-in)
frontend/src/components/editor/overlays/QuestionBox.tsx         — "Did you know?" / poll overlay
frontend/src/components/editor/overlays/FollowCTA.tsx           — "Follow for more" floating CTA
frontend/src/components/editor/overlays/EndScreen.tsx           — End card with follow + engagement CTAs
frontend/src/components/editor/overlays/ProgressBar.tsx         — Linear progress indicator (top of frame)
frontend/src/components/editor/OverlayPicker.tsx                — UI to pick/configure overlays for the video
frontend/src/components/editor/CaptionStylePicker.tsx           — Horizontal carousel of caption style presets
frontend/src/components/editor/AIAssistant.tsx                  — Chat with Claude for script improvements
frontend/src/components/editor/ExportPanel.tsx                  — Export with quality options + social sharing
frontend/src/hooks/useKeyboardShortcuts.ts                      — ALREADY EXISTS, may need updates
frontend/src/remotion/compositions/TransitionComposition.tsx    — Uses @remotion/transitions between scenes
```

### Files to Rewrite
```
frontend/src/components/editor/editor.css              — Lighter theme, CapCut-inspired 3-level dark
frontend/src/components/editor/EditorLayout.tsx         — Add overlay/export panels, fix seek wiring
frontend/src/components/editor/EditorTimeline.tsx       — Wire seek to playerRef, fix click handler
frontend/src/components/editor/SceneGrid.tsx            — Click thumbnail = seek to scene start
frontend/src/components/editor/SubtitleEditor.tsx       — Add style presets carousel, more options
frontend/src/contexts/EditorContext.tsx                 — Sync playerFrame via timeupdate event
frontend/src/remotion/compositions/SubtitleOverlay.tsx  — Support multiple caption styles
frontend/src/remotion/compositions/ShortVideoComposition.tsx — Add overlay layers, transitions
```

### Backend Files to Add/Modify
```
app/api/routes.py        — Add /regenerate-tts, /regenerate-media, /render, /ai-suggest endpoints
app/services/tts.py      — Accept voice_id + rate + pitch parameters
```

---

## Task 1: Fix Timeline Seek + Player Sync

The #1 user complaint. Timeline clicks and scene selection must control the video player.

**Files:**
- Modify: `frontend/src/contexts/EditorContext.tsx`
- Modify: `frontend/src/components/editor/EditorTimeline.tsx`
- Modify: `frontend/src/components/editor/SceneGrid.tsx`

- [ ] **Step 1: Add timeupdate listener in EditorContext**

In `EditorContext.tsx`, add a `useEffect` that attaches a `timeupdate` event listener to the Remotion Player after it mounts. This syncs `playerFrame` in real-time during playback.

```typescript
// Add after the playerRef definition in EditorProvider
useEffect(() => {
  const interval = setInterval(() => {
    const player = playerRef.current
    if (!player) return
    try {
      const frame = player.getCurrentFrame()
      setPlayerFrame(frame)
      // Sync isPlaying state
      setIsPlaying(!player.isPaused())
    } catch {
      // Player not ready yet
    }
  }, 100) // Poll every 100ms for smooth playhead

  return () => clearInterval(interval)
}, [])
```

- [ ] **Step 2: Fix EditorTimeline click-to-seek**

In `EditorTimeline.tsx`, the `handleSceneAreaClick` function calls `seekToFrame` but the playerRef may not respond because the Player uses `controls={false}` and `clickToPlay`. Verify the `seekToFrame` in context actually calls `playerRef.current?.seekTo(frame)`.

Test: Click different positions on the timeline scene blocks. The player should jump to that frame.

- [ ] **Step 3: Wire SceneGrid thumbnail click to seek**

In `SceneGrid.tsx`, when clicking a scene thumbnail, calculate the start frame for that scene and call `seekToFrame`:

```typescript
const handleSceneClick = (index: number) => {
  selectScene(index)
  // Calculate frame offset for this scene
  if (!composition) return
  const totalHints = composition.scenes.reduce((s, sc) => s + sc.duration_hint, 0)
  let frameOffset = 0
  for (let i = 0; i < index; i++) {
    frameOffset += (composition.scenes[i].duration_hint / totalHints) * totalFrames
  }
  seekToFrame(Math.round(frameOffset))
}
```

- [ ] **Step 4: Test end-to-end seek**

1. Click scene 3 in SceneGrid → player jumps to scene 3 start
2. Click middle of timeline → player jumps to that time
3. Press Space → plays from current position
4. Press 1-5 → jumps to scene N
5. ← → moves frame by frame

- [ ] **Step 5: Commit**

---

## Task 2: Lighter UI Theme (CapCut-Inspired)

**Files:**
- Modify: `frontend/src/components/editor/editor.css`

- [ ] **Step 1: Update color palette**

Replace the current overly dark theme with CapCut's 3-level approach:

```css
/* OLD: background: linear-gradient(160deg, #0f0f1a, #1a1025, #0d1117); */
/* NEW: 3-level dark hierarchy */

.editor {
  background: #1A1A1A;  /* deepest - canvas area */
}
.editor-tools-panel {
  background: #222222;  /* panels */
}
.editor-timeline {
  background: #1E1E1E;  /* timeline */
}
.editor-header {
  background: #222222;  /* header matches panels */
}

/* Text colors - NOT pure white */
color: #E8E8E8;           /* primary text */
/* secondary: */ #999999;
/* tertiary: */ #666666;

/* Accent - purple/violet */
--accent: #6C5CE7;
--accent-hover: rgba(108, 92, 231, 0.15);
--accent-active: rgba(108, 92, 231, 0.25);

/* Playhead/trim: cyan */
--playhead: #00D4FF;

/* Borders: barely visible but creates definition */
border-color: rgba(255,255,255,0.08);
```

- [ ] **Step 2: Update all component colors**

Go through every `.editor-*` class and replace:
- `#0f0f1a` / `#0a0a12` → `#1A1A1A`
- `rgba(255,255,255,0.03)` → `#222222` (for panels)
- `#e2e8f0` text → `#E8E8E8`
- `#7c3aed` accent → `#6C5CE7`
- Remove gradient backgrounds on the editor shell (solid color reads cleaner)
- Keep the subtle glow on the player (it provides a nice "light well" effect)

- [ ] **Step 3: Commit**

---

## Task 3: Caption Style System (TikTok + Impact + Presets)

**Files:**
- Create: `frontend/src/components/editor/overlays/TikTokCaptions.tsx`
- Create: `frontend/src/components/editor/overlays/ImpactCaptions.tsx`
- Create: `frontend/src/components/editor/CaptionStylePicker.tsx`
- Modify: `frontend/src/remotion/compositions/SubtitleOverlay.tsx`
- Modify: `frontend/src/remotion/types.ts`

- [ ] **Step 1: Add captionStyle to types**

In `types.ts`, add to `SubtitleStyle`:

```typescript
export type CaptionStylePreset = 'tiktok' | 'impact' | 'minimal' | 'karaoke' | 'boxed'

export interface SubtitleStyle {
  // ...existing fields...
  preset: CaptionStylePreset
  accentColor: string      // for karaoke highlight or impact alternating color
  strokeWidth: number      // text outline (0 = none, 1-4px)
  animationStyle: 'pop' | 'fade' | 'slideUp' | 'none'
}
```

- [ ] **Step 2: Create TikTokCaptions component**

Remotion component that renders auto-caption style:
- Sentence-case text (not uppercase)
- `rgba(0,0,0,0.65)` pill background with `border-radius: 8px`
- Word-by-word karaoke: active word gets `accentColor` (default `#FFFC00` yellow)
- Positioned at `top: 60%`

```tsx
// TikTokCaptions.tsx
export const TikTokCaptions: React.FC<{ words: Word[]; style: SubtitleStyle }> = ...
```

Uses `useCurrentFrame()` to determine which word is currently active based on timestamps.

- [ ] **Step 3: Create ImpactCaptions component**

Remotion component for CapCut Impact style:
- UPPERCASE, font-weight 900, font-size 72-80px
- `-webkit-text-stroke: 3px #000`
- `text-shadow: 4px 4px 0px rgba(0,0,0,0.8)`
- Alternating word colors from palette (white + accentColor)
- Pop-in animation: `scale(1.3) → scale(1.0)` with bounce easing
- 1-3 words at a time, positioned at `top: 50%`

- [ ] **Step 4: Update SubtitleOverlay to route by preset**

```typescript
export const SubtitleOverlay: React.FC<{words: Word[]; style: SubtitleStyle}> = ({words, style}) => {
  switch (style.preset) {
    case 'tiktok': return <TikTokCaptions words={words} style={style} />
    case 'impact': return <ImpactCaptions words={words} style={style} />
    case 'minimal': return <MinimalCaptions words={words} style={style} />  // current style
    default: return <MinimalCaptions words={words} style={style} />
  }
}
```

- [ ] **Step 5: Create CaptionStylePicker**

Horizontal scrollable row of preset thumbnails (CapCut pattern):
- Each preset is a small preview card (80x60px) showing "Aa" in that style
- Click to select → updates `composition.subtitleStyle.preset`
- Live preview in Remotion Player

- [ ] **Step 6: Update SubtitleEditor to include CaptionStylePicker**

Add the preset carousel at the top of the SubtitleEditor panel. Below it, show style-specific controls (e.g., accent color only shows for karaoke/impact presets).

- [ ] **Step 7: Commit**

---

## Task 4: Video Overlays (Question Box, CTA, End Screen, Progress Bar)

**Files:**
- Create: `frontend/src/components/editor/overlays/QuestionBox.tsx`
- Create: `frontend/src/components/editor/overlays/FollowCTA.tsx`
- Create: `frontend/src/components/editor/overlays/EndScreen.tsx`
- Create: `frontend/src/components/editor/overlays/ProgressBar.tsx`
- Create: `frontend/src/components/editor/OverlayPicker.tsx`
- Modify: `frontend/src/remotion/compositions/ShortVideoComposition.tsx`
- Modify: `frontend/src/remotion/types.ts`

- [ ] **Step 1: Add overlay types**

```typescript
export interface VideoOverlay {
  type: 'questionBox' | 'followCTA' | 'endScreen' | 'progressBar'
  startFrame: number
  endFrame: number
  config: Record<string, unknown>  // type-specific config
}

export interface CompositionData {
  // ...existing...
  overlays: VideoOverlay[]
}
```

- [ ] **Step 2: Create each overlay component**

Each is a Remotion component that renders within a `<Sequence>`:

**QuestionBox**: dark card with "DID YOU KNOW?" label + question text. Slide-in from top.
**FollowCTA**: red pill "FOLLOW FOR MORE" floating at bottom. Subtle bob animation.
**EndScreen**: dark overlay with profile circle + "Follow" button + engagement icons.
**ProgressBar**: thin gradient bar at top, width tracks video progress.

- [ ] **Step 3: Create OverlayPicker**

New tab in the editor (replace or augment the "IA" tab):
- Grid of overlay templates with preview thumbnails
- Click to add overlay to composition
- Configure start/end time, text content
- Toggle on/off

- [ ] **Step 4: Wire overlays into ShortVideoComposition**

```tsx
{composition.overlays.map((overlay, i) => (
  <Sequence key={i} from={overlay.startFrame} durationInFrames={overlay.endFrame - overlay.startFrame}>
    {overlay.type === 'questionBox' && <QuestionBox config={overlay.config} />}
    {overlay.type === 'followCTA' && <FollowCTA config={overlay.config} />}
    {overlay.type === 'endScreen' && <EndScreen config={overlay.config} />}
    {overlay.type === 'progressBar' && <ProgressBar />}
  </Sequence>
))}
```

- [ ] **Step 5: Commit**

---

## Task 5: Narration Regeneration (Backend + Frontend)

**Files:**
- Modify: `app/services/tts.py`
- Modify: `app/api/routes.py`
- Modify: `frontend/src/components/editor/VoiceSelector.tsx`
- Modify: `frontend/src/components/editor/SceneGrid.tsx`

- [ ] **Step 1: Update tts.py to accept voice parameters**

```python
def synthesize_narration(
    text: str, output_path: str,
    speaker_wav: str = "",
    duration_target: float = 0,
    voice_id: str = "pt-BR-AntonioNeural",
    rate: int = -10,
    pitch: int = 5,
) -> str:
```

Update `_generate()` to use the passed voice_id, rate, pitch.

- [ ] **Step 2: Add regenerate-tts endpoint**

```python
@router.post("/jobs/{job_id}/regenerate-tts")
async def regenerate_tts(job_id: str, req: RegenerateTTSRequest, ...):
    # 1. Read current script from job dir
    # 2. Update narration text if provided
    # 3. Run TTS with voice settings
    # 4. Run Whisper to get new word timestamps
    # 5. Return updated composition data
```

This runs synchronously (Edge TTS is fast, ~2-4s). Returns the updated words + audio URL.

- [ ] **Step 3: Wire "Regerar narracao" button**

In `VoiceSelector.tsx`, the button calls the API:

```typescript
const handleRegenerate = async () => {
  setRegenerating(true)
  const result = await fetch(`/api/v1/jobs/${jobId}/regenerate-tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      voice_id: composition.voiceConfig.voiceId,
      rate: composition.voiceConfig.rate,
      pitch: composition.voiceConfig.pitch,
    }),
  })
  const data = await result.json()
  // Update composition with new words + audio URL
  updateComposition(prev => ({ ...prev, words: data.words, audioUrl: data.audio_url + '?t=' + Date.now() }))
  setRegenerating(false)
}
```

- [ ] **Step 4: Commit**

---

## Task 6: AI Assistant (Claude Chat)

**Files:**
- Create: `frontend/src/components/editor/AIAssistant.tsx`
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add /ai-suggest endpoint**

```python
@router.post("/jobs/{job_id}/ai-suggest")
async def ai_suggest(job_id: str, req: AISuggestRequest, ...):
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    script = req.context or {}
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Voce e um editor de video especialista em conteudo viral para TikTok/Reels.

Roteiro atual:
{json.dumps(script, ensure_ascii=False, indent=2)}

Pedido do criador: {req.message}

Responda em JSON com sugestoes especificas:
{{
  "suggestions": [
    {{
      "type": "rewrite_scene",
      "scene_index": 0,
      "new_text": "texto melhorado",
      "reason": "por que esta versao e melhor"
    }}
  ],
  "general_feedback": "feedback geral sobre o roteiro"
}}"""
        }],
    )
    return json.loads(message.content[0].text)
```

- [ ] **Step 2: Create AIAssistant component**

Chat-style UI in the "IA" tab:
- Quick prompts at top: "Melhorar gancho", "Mais engajante", "Reescrever cena N"
- Text input for custom requests
- Response shows structured suggestions with "Aplicar" buttons
- Clicking "Aplicar" on a scene rewrite calls `updateScene(index, { text: newText })`

```tsx
const AIAssistant: React.FC = () => {
  const { composition, updateScene } = useEditor()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  const quickPrompts = [
    { label: 'Melhorar gancho', prompt: 'Reescreva a cena 1 com um gancho mais forte e provocativo' },
    { label: 'Mais engajante', prompt: 'Torne o roteiro mais engajante e conversacional' },
    { label: 'Adicionar humor', prompt: 'Adicione toques de humor sem perder o conteudo informativo' },
    { label: 'CTA melhor', prompt: 'Melhore a conclusao com um call-to-action mais efetivo' },
  ]
  // ...
}
```

- [ ] **Step 3: Commit**

---

## Task 7: Export with Social Sharing

**Files:**
- Create: `frontend/src/components/editor/ExportPanel.tsx`
- Modify: `app/api/routes.py`

- [ ] **Step 1: Add /render endpoint**

```python
@router.post("/jobs/{job_id}/render")
async def render_video(job_id: str, user: User = Depends(get_current_user), db: ...):
    # 1. Read editor_state from DB
    # 2. Rebuild script from editor state
    # 3. Dispatch Celery task: re-run TTS + compose_short with updated params
    # 4. Return render job ID for polling
```

- [ ] **Step 2: Create ExportPanel**

Replaces the "Exportar" button with a panel/modal:
- Quality selector: Alta (1080p) / Media (720p)
- Progress bar during rendering
- After render:
  - Download button
  - Social sharing section with platform cards:
    - YouTube Shorts: title (100 chars max) + description + hashtags
    - TikTok: caption (150 chars) + hashtags
    - Instagram Reels: caption (2200 chars) + hashtags
  - "Copy caption" button per platform
  - Claude auto-generates platform-specific captions from the script

- [ ] **Step 3: Commit**

---

## Task 8: Scene Transitions

**Files:**
- Create: `frontend/src/remotion/compositions/TransitionComposition.tsx`
- Modify: `frontend/src/remotion/compositions/ShortVideoComposition.tsx`
- Modify: `frontend/src/remotion/types.ts`

- [ ] **Step 1: Add transition types**

```typescript
export type TransitionType = 'none' | 'fade' | 'slide' | 'wipe'

export interface Scene {
  // ...existing...
  transition: TransitionType  // transition INTO this scene
}
```

- [ ] **Step 2: Update ShortVideoComposition to use @remotion/transitions**

Replace `<Sequence>` with `<TransitionSeries>`:

```tsx
import { TransitionSeries, linearTiming } from '@remotion/transitions'
import { fade } from '@remotion/transitions/fade'
import { slide } from '@remotion/transitions/slide'
import { wipe } from '@remotion/transitions/wipe'

// In the composition:
<TransitionSeries>
  {sceneFrames.map((sf, i) => (
    <React.Fragment key={i}>
      {i > 0 && scenes[i].transition !== 'none' && (
        <TransitionSeries.Transition
          presentation={getTransition(scenes[i].transition)}
          timing={linearTiming({ durationInFrames: 10 })}
        />
      )}
      <TransitionSeries.Sequence durationInFrames={sf.duration}>
        <SceneClip mediaUrl={mediaUrls[i]} />
      </TransitionSeries.Sequence>
    </React.Fragment>
  ))}
</TransitionSeries>
```

- [ ] **Step 3: Add transition picker to SceneGrid**

Each scene card gets a small dropdown to select transition type (none/fade/slide/wipe).

- [ ] **Step 4: Commit**

---

## Verification

After all tasks:

1. Open `/editor/{jobId}` — player fills ~80% viewport height
2. UI is lighter (not oppressive dark) — CapCut-inspired 3-level gray
3. Click timeline → player seeks
4. Click scene thumbnail → player seeks to scene start
5. Space/arrows/J/L work for navigation
6. Caption style picker shows 3+ presets — selecting one changes video preview instantly
7. Overlays (question box, CTA) render in the Remotion player
8. "Regerar narracao" with different voice → new audio plays in preview
9. AI chat returns suggestions → "Aplicar" updates scene text → preview updates
10. Export → renders video → shows download + social sharing captions
11. Scene transitions (fade/slide) visible in preview
