'use client'

import { useMemo, useRef } from 'react'
import { Player, type PlayerRef } from '@remotion/player'
import { ShortVideoComposition } from '@/remotion/compositions/ShortVideoComposition'
import { useEditor } from '@/contexts/EditorContext'

export function RemotionPreview() {
  const { composition } = useEditor()
  const playerRef = useRef<PlayerRef>(null)

  const durationInFrames = useMemo(() => {
    if (!composition || composition.words.length === 0) return 150
    const lastWord = composition.words[composition.words.length - 1]
    return Math.round((lastWord.end + 0.5) * composition.fps)
  }, [composition])

  if (!composition) return null

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      gap: 10, height: '100%', width: '100%',
    }}>
      {/* Player with glow effect */}
      <div style={{
        position: 'relative',
        height: '100%',
        maxHeight: 'calc(100vh - 170px)',
        aspectRatio: '9/16',
      }}>
        {/* Glow behind player */}
        <div style={{
          position: 'absolute', inset: -20,
          background: 'radial-gradient(ellipse at center, rgba(124, 58, 237, 0.12) 0%, transparent 70%)',
          borderRadius: 40,
          filter: 'blur(20px)',
          pointerEvents: 'none',
        }} />

        {/* Player frame */}
        <div style={{
          position: 'relative',
          height: '100%',
          borderRadius: 20,
          border: '2px solid rgba(255,255,255,0.08)',
          overflow: 'hidden',
          background: '#0a0a12',
          boxShadow: '0 8px 40px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)',
        }}>
          <Player
            ref={playerRef}
            component={ShortVideoComposition as unknown as React.FC<Record<string, unknown>>}
            inputProps={composition}
            durationInFrames={durationInFrames}
            compositionWidth={composition.width}
            compositionHeight={composition.height}
            fps={composition.fps}
            style={{ width: '100%', height: '100%' }}
            controls
            autoPlay={false}
            loop
            clickToPlay
            acknowledgeRemotionLicense
          />
        </div>
      </div>

      {/* Duration badge */}
      <div style={{
        fontSize: 11, color: 'rgba(255,255,255,0.35)',
        background: 'rgba(255,255,255,0.04)',
        padding: '3px 10px', borderRadius: 4,
        flexShrink: 0,
      }}>
        {(durationInFrames / composition.fps).toFixed(1)}s &middot; {composition.fps}fps &middot; {composition.width}&times;{composition.height}
      </div>
    </div>
  )
}
