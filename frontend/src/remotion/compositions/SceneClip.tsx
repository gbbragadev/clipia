import { AbsoluteFill, OffthreadVideo, useVideoConfig } from 'remotion'

export const SceneClip: React.FC<{
  mediaUrl: string
}> = ({ mediaUrl }) => {
  const { width, height } = useVideoConfig()

  return (
    <AbsoluteFill>
      <OffthreadVideo
        src={mediaUrl}
        style={{
          width,
          height,
          objectFit: 'cover',
        }}
      />
    </AbsoluteFill>
  )
}
