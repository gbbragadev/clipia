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
