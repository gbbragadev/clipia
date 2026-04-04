import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'

interface EndScreenProps {
  config: { username?: string; text?: string; [key: string]: unknown }
}

export const EndScreen: React.FC<EndScreenProps> = ({ config }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const fadeDuration = Math.round(fps * 0.5)
  const bgOpacity = interpolate(frame, [0, fadeDuration], [0, 1], {
    extrapolateRight: 'clamp',
  })

  // Stagger elements from center outward
  const stagger = (delay: number) => {
    const start = Math.round(fadeDuration * delay)
    return {
      opacity: interpolate(frame, [start, start + fadeDuration], [0, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      }),
      scale: interpolate(frame, [start, start + fadeDuration], [0.8, 1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      }),
    }
  }

  const circle = stagger(0.2)
  const username = stagger(0.5)
  const textAnim = stagger(0.7)
  const button = stagger(1.0)

  const usernameText = (config.username as string) || '@clipia'
  const ctaText = (config.text as string) || 'Gostou? Siga para mais!'

  return (
    <AbsoluteFill
      style={{
        background: `rgba(0,0,0,${0.85 * bgOpacity})`,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 20,
      }}
    >
      {/* Profile circle */}
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          border: '3px solid white',
          background: '#6C5CE7',
          opacity: circle.opacity,
          transform: `scale(${circle.scale})`,
        }}
      />

      {/* Username */}
      <span
        style={{
          fontSize: 28,
          fontWeight: 600,
          color: '#FFFFFF',
          fontFamily: 'Montserrat, sans-serif',
          opacity: username.opacity,
          transform: `scale(${username.scale})`,
        }}
      >
        {usernameText}
      </span>

      {/* CTA text */}
      <span
        style={{
          fontSize: 36,
          fontWeight: 700,
          color: '#FFFFFF',
          fontFamily: 'Montserrat, sans-serif',
          textAlign: 'center',
          opacity: textAnim.opacity,
          transform: `scale(${textAnim.scale})`,
        }}
      >
        {ctaText}
      </span>

      {/* Follow button */}
      <div
        style={{
          borderRadius: 999,
          background: '#FE2C55',
          padding: '12px 40px',
          opacity: button.opacity,
          transform: `scale(${button.scale})`,
        }}
      >
        <span
          style={{
            fontSize: 22,
            fontWeight: 700,
            color: '#FFFFFF',
            fontFamily: 'Montserrat, sans-serif',
            textTransform: 'uppercase',
          }}
        >
          SEGUIR
        </span>
      </div>
    </AbsoluteFill>
  )
}
