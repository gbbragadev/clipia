'use client'

import dynamic from 'next/dynamic'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ShortVideoComposition } from '@/remotion/compositions/ShortVideoComposition'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Player = dynamic(
  () => import('@remotion/player').then((mod) => mod.Player as any),
  {
    ssr: false,
    loading: () => (
      <div className="w-full aspect-[9/16] bg-black/50 rounded-xl animate-pulse flex items-center justify-center">
        <span className="text-white/40 text-sm">Carregando player...</span>
      </div>
    ),
  }
) as any
import { useEditor } from '@/contexts/EditorContext'
import { useIsMobile } from '@/hooks/useIsMobile'
import { PretextSubtitlePreview } from './PretextSubtitlePreview'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const VideoComponent = ShortVideoComposition as any

export function VideoPlayer() {
  const { composition, playerRef, totalFrames, playerFrame } = useEditor()
  const isMobile = useIsMobile()
  const [version, setVersion] = useState(0)
  const lastCompositionRef = useRef<string>('')
  const seekAfterMountRef = useRef<number | null>(null)

  // Detect meaningful composition changes and force re-mount while preserving position
  useEffect(() => {
    if (!composition) return
    const sig = JSON.stringify({
      scenes: composition.scenes.map(s => ({ t: s.transition, d: s.duration_hint })),
      preset: composition.subtitleStyle.preset,
      font: composition.subtitleStyle.fontFamily,
      fontSize: composition.subtitleStyle.fontSize,
      color: composition.subtitleStyle.color,
      bg: composition.subtitleStyle.backgroundColor,
      pos: composition.subtitleStyle.position,
      margin: composition.subtitleStyle.marginBottom,
      stroke: composition.subtitleStyle.strokeWidth,
      outline: composition.subtitleStyle.outlineColor,
      accent: composition.subtitleStyle.accentColor,
      anim: composition.subtitleStyle.animationStyle,
      maxWords: composition.subtitleStyle.maxWordsPerChunk,
      music: composition.musicUrl,
      musicVol: composition.musicVolume,
    })
    if (lastCompositionRef.current && sig !== lastCompositionRef.current) {
      // Save current frame before re-mount
      seekAfterMountRef.current = playerFrame
      setVersion(v => v + 1)
    }
    lastCompositionRef.current = sig
  }, [composition, playerFrame])

  // Restore playback position after re-mount
  const handlePlayerReady = useCallback(() => {
    if (seekAfterMountRef.current !== null && playerRef.current) {
      const frame = seekAfterMountRef.current
      seekAfterMountRef.current = null
      // Small delay to let Player initialize
      requestAnimationFrame(() => {
        playerRef.current?.seekTo(frame)
      })
    }
  }, [playerRef])

  useEffect(() => {
    handlePlayerReady()
  }, [version, handlePlayerReady])

  if (!composition) return null

  return (
    <div style={{ position: 'relative', height: '100%', aspectRatio: '9/16', maxWidth: '100%' }}>
      <div className="editor-player-glow" />
      <div className="editor-player-container" style={{ position: 'relative' }}>
        <Player
          key={version}
          ref={playerRef}
          component={VideoComponent}
          inputProps={composition}
          durationInFrames={totalFrames}
          compositionWidth={composition.width}
          compositionHeight={composition.height}
          fps={composition.fps}
          style={{ width: '100%', height: '100%' }}
          controls={isMobile}
          loop
          acknowledgeRemotionLicense
        />
        <PretextSubtitlePreview />
      </div>
    </div>
  )
}
