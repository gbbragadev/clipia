import React from 'react'
import { AbsoluteFill, Html5Audio, Sequence, useCurrentFrame, useVideoConfig } from 'remotion'
import { TransitionSeries, linearTiming, type TransitionPresentation } from '@remotion/transitions'
import { fade } from '@remotion/transitions/fade'
import { slide } from '@remotion/transitions/slide'
import { wipe } from '@remotion/transitions/wipe'
import type { CompositionData } from '../types'
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

export const ShortVideoComposition: React.FC<CompositionData> = ({
  scenes,
  words,
  audioUrl,
  mediaUrls,
  subtitleStyle,
  overlays,
  musicUrl,
  musicVolume,
}) => {
  const { fps, durationInFrames } = useVideoConfig()

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
        {sceneFrames.map((sf, i) => {
          const scene = scenes[i]
          const transitionType = scene?.transition || 'none'
          const presentation = getTransitionPresentation(transitionType)
          return (
            <React.Fragment key={`scene-${i}-${transitionType}`}>
              {i > 0 && transitionType !== 'none' && presentation && (
                <TransitionSeries.Transition
                  key={`tr-${i}-${transitionType}`}
                  presentation={presentation}
                  timing={linearTiming({ durationInFrames: 10 })}
                />
              )}
              <TransitionSeries.Sequence durationInFrames={sf.duration}>
                {i < mediaUrls.length && <SceneClip mediaUrl={mediaUrls[i]} />}
              </TransitionSeries.Sequence>
            </React.Fragment>
          )
        })}
      </TransitionSeries>

      {/* Narration audio */}
      {audioUrl && <Html5Audio src={audioUrl} />}

      {/* Background music */}
      {musicUrl && <Html5Audio src={musicUrl} volume={musicVolume ?? 0.15} />}

      {/* Subtitles rendered by Pretext canvas overlay in editor */}
      {/* SubtitleOverlay only used during server-side render/export */}

      {/* User-added overlays */}
      {overlays?.map((overlay, i) => (
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
      ))}

      {/* Progress bar at bottom */}
      <ProgressBar />
    </AbsoluteFill>
  )
}

const ProgressBar: React.FC = () => {
  const { durationInFrames } = useVideoConfig()
  const frame = useCurrentFrame()
  const progress = frame / durationInFrames

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingBottom: 80,
      }}
    >
      <div
        style={{
          width: '80%',
          height: 3,
          background: 'rgba(255,255,255,0.15)',
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress * 100}%`,
            background: 'rgba(255,255,255,0.7)',
            borderRadius: 2,
          }}
        />
      </div>
    </AbsoluteFill>
  )
}
