import React from 'react'
import { AbsoluteFill, Html5Audio, Sequence, useVideoConfig } from 'remotion'
import { TransitionSeries, linearTiming, type TransitionPresentation } from '@remotion/transitions'
import { fade } from '@remotion/transitions/fade'
import { slide } from '@remotion/transitions/slide'
import { wipe } from '@remotion/transitions/wipe'
import type { CompositionData, LayoutType } from '../types'
import type { TransitionType } from '../types'
import { SceneClip } from './SceneClip'
import { SubtitleOverlay } from './SubtitleOverlay'
import { QuestionBox } from '@/components/editor/overlays/QuestionBox'
import { FollowCTA } from '@/components/editor/overlays/FollowCTA'
import { EndScreen } from '@/components/editor/overlays/EndScreen'
import { ProgressBar as OverlayProgressBar } from '@/components/editor/overlays/ProgressBar'

function getTransitionPresentation(type: TransitionType) {
  switch (type) {
    case 'fade': return fade() as TransitionPresentation<Record<string, unknown>>
    case 'slide': return slide() as TransitionPresentation<Record<string, unknown>>
    case 'wipe': return wipe() as TransitionPresentation<Record<string, unknown>>
    default: return null
  }
}

const Watermark: React.FC<{ text: string }> = ({ text }) => (
  <div
    style={{
      position: 'absolute',
      bottom: 40,
      right: 30,
      fontSize: 22,
      fontFamily: 'Montserrat, sans-serif',
      fontWeight: 600,
      color: 'rgba(255, 255, 255, 0.55)',
      textShadow: '0 1px 3px rgba(0, 0, 0, 0.6)',
      pointerEvents: 'none',
    }}
  >
    {text}
  </div>
)

export const ShortVideoComposition: React.FC<CompositionData> = ({
  scenes,
  words,
  audioUrl,
  mediaUrls,
  subtitleStyle,
  overlays,
  musicUrl,
  musicVolume,
  isRendering,
  layoutType,
  watermark,
}) => {
  const { fps, width, height, durationInFrames } = useVideoConfig()
  const layout = (layoutType || 'fullscreen') as LayoutType

  // Overlays do usuário: um único bloco usado nos 3 layouts — antes, os early
  // returns de split_horizontal/character_overlay descartavam overlays no export.
  const overlayElements = overlays?.map((overlay, i) => (
    <Sequence
      key={`overlay-${i}`}
      from={overlay.startFrame}
      durationInFrames={overlay.endFrame - overlay.startFrame}
    >
      {overlay.type === 'questionBox' && <QuestionBox config={overlay.config as { text?: string; label?: string }} />}
      {overlay.type === 'followCTA' && <FollowCTA config={overlay.config as { text?: string }} />}
      {overlay.type === 'endScreen' && <EndScreen config={overlay.config as { username?: string; text?: string }} />}
      {overlay.type === 'progressBar' && <OverlayProgressBar />}
    </Sequence>
  ))

  // Split-screen layout: dark top + gameplay bottom
  if (layout === 'split_horizontal' && mediaUrls.length === 1) {
    const splitRatio = 0.55
    const topHeight = Math.round(height * splitRatio)
    const botHeight = height - topHeight

    return (
      <AbsoluteFill style={{ backgroundColor: '#000' }}>
        {/* Top region: dark background for subtitles */}
        <div style={{ position: 'absolute', top: 0, left: 0, width, height: topHeight, background: '#0D0D0D', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isRendering && <SubtitleOverlay words={words} style={{ ...subtitleStyle, position: 'center' as const }} />}
        </div>
        {/* Bottom region: gameplay */}
        <div style={{ position: 'absolute', top: topHeight, left: 0, width, height: botHeight, overflow: 'hidden' }}>
          <SceneClip mediaUrl={mediaUrls[0]} />
        </div>
        {audioUrl && <Html5Audio src={audioUrl} />}
        {musicUrl && <Html5Audio src={musicUrl} volume={musicVolume ?? 0.15} />}
        {overlayElements}
        {watermark && <Watermark text={watermark} />}
      </AbsoluteFill>
    )
  }

  // Character overlay layout: full-screen gameplay + character image (approximate preview)
  if (layout === 'character_overlay' && mediaUrls.length === 1) {
    return (
      <AbsoluteFill style={{ backgroundColor: '#000' }}>
        <SceneClip mediaUrl={mediaUrls[0]} />
        {/* Placeholder SÓ no preview: o personagem real é composto pelo FFmpeg na
            geração inicial e o re-export Remotion não tem o asset — sem este gate,
            o círculo "Personagem" ia parar no MP4 final. */}
        {!isRendering && (
          <div style={{
            position: 'absolute', bottom: 250, left: 40,
            width: 350, height: 350, borderRadius: '50%',
            background: 'rgba(108, 92, 231, 0.3)', border: '3px solid rgba(108, 92, 231, 0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, color: '#aaa', textAlign: 'center',
          }}>
            Personagem
          </div>
        )}
        {audioUrl && <Html5Audio src={audioUrl} />}
        {musicUrl && <Html5Audio src={musicUrl} volume={musicVolume ?? 0.15} />}
        {isRendering && <SubtitleOverlay words={words} style={subtitleStyle} />}
        {overlayElements}
        {watermark && <Watermark text={watermark} />}
      </AbsoluteFill>
    )
  }

  // Calculate scene frame ranges proportional to duration_hint
  // Account for transition overlap (each transition consumes 10 frames shared between scenes)
  const transitionDuration = 10
  const totalHints = scenes.reduce((sum, s) => sum + s.duration_hint, 0)
  const transitionCount = scenes.filter((s, i) => i > 0 && s.transition && s.transition !== 'none').length
  const availableFrames = durationInFrames + transitionCount * transitionDuration
  const sceneFrames: { from: number; duration: number }[] = []
  let currentFrame = 0

  for (const scene of scenes) {
    const ratio = scene.duration_hint / totalHints
    const duration = Math.max(transitionDuration + 1, Math.round(ratio * availableFrames))
    sceneFrames.push({ from: currentFrame, duration })
    currentFrame += duration
  }

  return (
    <AbsoluteFill style={{ backgroundColor: '#000' }}>
      {/* Background video scenes with transitions */}
      <TransitionSeries>
        {sceneFrames.flatMap((sf, i) => {
          const scene = scenes[i]
          const transitionType = scene?.transition || 'none'
          const presentation = getTransitionPresentation(transitionType)
          const elements: React.ReactNode[] = []

          if (i > 0 && presentation) {
            elements.push(
              <TransitionSeries.Transition
                key={`tr-${i}`}
                presentation={presentation}
                timing={linearTiming({ durationInFrames: transitionDuration })}
              />
            )
          }

          elements.push(
            <TransitionSeries.Sequence key={`seq-${i}`} durationInFrames={sf.duration}>
              {i < mediaUrls.length ? (
                <SceneClip mediaUrl={mediaUrls[i]} sceneIndex={i} durationInFrames={sf.duration} />
              ) : (
                // Sem mídia (ex.: template ai_video sem media_urls): placeholder grafite.
                // A Sequence PRECISA de um filho, senão o Remotion lanca
                // "Sequence detected to not have any children".
                <AbsoluteFill style={{ background: 'linear-gradient(135deg, #11141d, #08090f)' }} />
              )}
            </TransitionSeries.Sequence>
          )

          return elements
        })}
      </TransitionSeries>

      {/* Narration audio */}
      {audioUrl && <Html5Audio src={audioUrl} />}

      {/* Background music */}
      {musicUrl && <Html5Audio src={musicUrl} volume={musicVolume ?? 0.15} />}

      {/* Subtitles: Pretext canvas in editor, SubtitleOverlay in SSR export */}
      {isRendering && <SubtitleOverlay words={words} style={subtitleStyle} />}

      {/* User-added overlays */}
      {overlayElements}

      {watermark && <Watermark text={watermark} />}
    </AbsoluteFill>
  )
}
