'use client'

import { Player } from '@remotion/player'
import { ShortVideoComposition } from '@/remotion/compositions/ShortVideoComposition'
import { useEditor } from '@/contexts/EditorContext'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const VideoComponent = ShortVideoComposition as any

export function VideoPlayer() {
  const { composition, playerRef, totalFrames, compositionVersion } = useEditor()

  if (!composition) return null

  return (
    <div style={{ position: 'relative', height: '100%', aspectRatio: '9/16', maxWidth: '100%' }}>
      <div className="editor-player-glow" />
      <div className="editor-player-container">
        <Player
          key={compositionVersion}
          ref={playerRef}
          component={VideoComponent}
          inputProps={composition}
          durationInFrames={totalFrames}
          compositionWidth={composition.width}
          compositionHeight={composition.height}
          fps={composition.fps}
          style={{ width: '100%', height: '100%' }}
          controls={false}
          loop
          acknowledgeRemotionLicense
        />
      </div>
    </div>
  )
}
