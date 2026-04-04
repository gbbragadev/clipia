import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Sequence } from 'remotion'

export const ExampleShort: React.FC<{
  title: string
  subtitle: string
  bgGradient: [string, string]
}> = ({ title, subtitle, bgGradient }) => {
  const frame = useCurrentFrame()
  const { fps, durationInFrames } = useVideoConfig()

  // Title animation
  const titleProgress = spring({ frame, fps, config: { damping: 15, stiffness: 80 } })
  const titleScale = interpolate(titleProgress, [0, 1], [0.6, 1])
  const titleY = interpolate(titleProgress, [0, 1], [40, 0])

  // Background subtle zoom
  const bgScale = interpolate(frame, [0, durationInFrames], [1, 1.08], { extrapolateRight: 'clamp' })

  // Words animation
  const words = subtitle.split(' ')

  return (
    <AbsoluteFill>
      {/* Animated gradient background */}
      <AbsoluteFill style={{
        background: `linear-gradient(135deg, ${bgGradient[0]}, ${bgGradient[1]})`,
        transform: `scale(${bgScale})`,
      }} />

      {/* Subtle vignette overlay */}
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.5) 100%)',
      }} />

      {/* Title with spring animation */}
      <Sequence from={0}>
        <AbsoluteFill style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          paddingBottom: 200,
        }}>
          <div style={{
            fontSize: 80,
            fontWeight: 900,
            color: 'white',
            opacity: titleProgress,
            transform: `scale(${titleScale}) translateY(${titleY}px)`,
            textAlign: 'center',
            padding: '0 60px',
            textShadow: '0 4px 30px rgba(0,0,0,0.4)',
            letterSpacing: '-0.02em',
            lineHeight: 1.1,
          }}>
            {title}
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* Animated subtitle — word by word reveal */}
      <Sequence from={20}>
        <AbsoluteFill style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'center',
          paddingBottom: 280,
        }}>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: '6px 10px',
            padding: '0 80px',
            maxWidth: 900,
          }}>
            {words.map((word, i) => {
              const wordStart = 20 + i * 4
              const wordOpacity = interpolate(frame, [wordStart, wordStart + 6], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              })
              const wordY = interpolate(frame, [wordStart, wordStart + 6], [12, 0], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              })

              return (
                <span key={i} style={{
                  fontSize: 38,
                  fontWeight: 700,
                  color: 'white',
                  opacity: wordOpacity,
                  transform: `translateY(${wordY}px)`,
                  textShadow: '0 2px 12px rgba(0,0,0,0.6)',
                  display: 'inline-block',
                }}>
                  {word}
                </span>
              )
            })}
          </div>
        </AbsoluteFill>
      </Sequence>

      {/* Bottom progress bar */}
      <AbsoluteFill style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        paddingBottom: 120,
      }}>
        <div style={{
          width: '75%',
          height: 3,
          background: 'rgba(255,255,255,0.15)',
          borderRadius: 2,
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${(frame / durationInFrames) * 100}%`,
            background: 'rgba(255,255,255,0.8)',
            borderRadius: 2,
          }} />
        </div>
      </AbsoluteFill>

      {/* Fake social icons on right */}
      <AbsoluteFill style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        justifyContent: 'flex-end',
        paddingRight: 30,
        paddingBottom: 180,
        gap: 24,
      }}>
        {['heart', 'comment', 'share'].map((icon, i) => {
          const iconDelay = 40 + i * 8
          const iconOpacity = interpolate(frame, [iconDelay, iconDelay + 10], [0, 0.7], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
          return (
            <div key={icon} style={{
              width: 44,
              height: 44,
              borderRadius: 22,
              background: 'rgba(255,255,255,0.15)',
              opacity: iconOpacity,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <div style={{
                width: 18,
                height: 18,
                borderRadius: icon === 'heart' ? '50% 50% 0 0' : icon === 'share' ? 2 : 9,
                border: '2px solid rgba(255,255,255,0.8)',
                transform: icon === 'heart' ? 'rotate(45deg) scale(0.8)' : 'none',
              }} />
            </div>
          )
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  )
}
