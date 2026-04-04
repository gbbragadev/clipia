import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'

interface QuestionBoxProps {
  config: { text?: string; label?: string; [key: string]: unknown }
}

export const QuestionBox: React.FC<QuestionBoxProps> = ({ config }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()

  const entranceDuration = Math.round(fps * 0.4)
  const opacity = interpolate(frame, [0, entranceDuration], [0, 1], {
    extrapolateRight: 'clamp',
  })
  const translateY = interpolate(frame, [0, entranceDuration], [-30, 0], {
    extrapolateRight: 'clamp',
  })

  const label = (config.label as string) || 'VOCE SABIA?'
  const text = (config.text as string) || 'Pergunta aqui'

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '20%',
      }}
    >
      <div
        style={{
          width: '88%',
          background: 'rgba(0,0,0,0.75)',
          borderRadius: 18,
          border: '2px solid rgba(255,255,255,0.15)',
          padding: '28px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          opacity,
          transform: `translateY(${translateY}px)`,
        }}
      >
        <span
          style={{
            fontSize: 24,
            fontWeight: 600,
            color: '#FFCC00',
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            fontFamily: 'Montserrat, sans-serif',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: '#FFFFFF',
            fontFamily: 'Montserrat, sans-serif',
            lineHeight: 1.2,
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  )
}
