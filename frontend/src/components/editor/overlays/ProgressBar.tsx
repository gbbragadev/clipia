import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion'

export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame()
  const { durationInFrames } = useVideoConfig()
  const progress = (frame / durationInFrames) * 100

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '3%',
      }}
    >
      <div
        style={{
          width: '100%',
          height: 5,
          background: 'rgba(255,255,255,0.2)',
          borderRadius: 999,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress}%`,
            background: 'linear-gradient(90deg, #FF2D55, #FFCC00)',
            borderRadius: 999,
          }}
        />
      </div>
    </AbsoluteFill>
  )
}
