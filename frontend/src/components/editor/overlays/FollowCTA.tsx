import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'

interface FollowCTAProps {
  config: { text?: string; [key: string]: unknown }
}

export const FollowCTA: React.FC<FollowCTAProps> = ({ config }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const entranceDuration = Math.round(fps * 0.3)
  const opacity = interpolate(frame, [0, entranceDuration], [0, 1], {
    extrapolateRight: 'clamp',
  })
  const entranceY = interpolate(frame, [0, entranceDuration], [20, 0], {
    extrapolateRight: 'clamp',
  })

  // Floating bob after entrance: 2s cycle, +/- 4px
  const bobCycleFrames = fps * 2
  const bobPhase = ((frame - entranceDuration) % bobCycleFrames) / bobCycleFrames
  const bobY = frame > entranceDuration
    ? Math.sin(bobPhase * Math.PI * 2) * -4
    : 0

  const text = (config.text as string) || 'SIGA PARA MAIS'

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingBottom: '20%',
      }}
    >
      <div
        style={{
          borderRadius: 999,
          background: '#FE2C55',
          padding: '14px 36px',
          boxShadow: '0 4px 20px rgba(254,44,85,0.4)',
          opacity,
          transform: `translateY(${entranceY + bobY}px)`,
        }}
      >
        <span
          style={{
            fontSize: 24,
            fontWeight: 700,
            color: '#FFFFFF',
            textTransform: 'uppercase',
            fontFamily: 'Montserrat, sans-serif',
            letterSpacing: '0.05em',
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  )
}
