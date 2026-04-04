'use client'

import { useMemo } from 'react'
import { Player } from '@remotion/player'
import { ShortVideoComposition } from '@/remotion/compositions/ShortVideoComposition'
import { useEditor } from '@/contexts/EditorContext'

export function VideoPlayer() {
  const { composition, playerRef, totalFrames } = useEditor()

  if (!composition) return null

  return (
    <div style={{ position: 'relative', height: '100%', aspectRatio: '9/16', maxWidth: '100%' }}>
      <div className="editor-player-glow" />
      <div className="editor-player-container">
        <Player
          ref={playerRef}
          component={ShortVideoComposition as unknown as React.FC<Record<string, unknown>>}
          inputProps={composition}
          durationInFrames={totalFrames}
          compositionWidth={composition.width}
          compositionHeight={composition.height}
          fps={composition.fps}
          style={{ width: '100%', height: '100%' }}
          controls={false}
          loop
          clickToPlay
          acknowledgeRemotionLicense
        />
      </div>
    </div>
  )
}
