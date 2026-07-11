import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import type { SubtitleStyle, Word } from '../types'
import { TikTokCaptions } from '@/components/editor/overlays/TikTokCaptions'
import { ImpactCaptions } from '@/components/editor/overlays/ImpactCaptions'

interface WordChunk {
  text: string
  startFrame: number
  endFrame: number
}

function groupWordsIntoChunks(words: Word[], maxWords: number, fps: number): WordChunk[] {
  const chunks: WordChunk[] = []
  for (let i = 0; i < words.length; i += maxWords) {
    const group = words.slice(i, i + maxWords)
    chunks.push({
      text: group.map((w) => w.word).join(' '),
      startFrame: Math.round(group[0].start * fps),
      endFrame: Math.round(group[group.length - 1].end * fps),
    })
  }
  return chunks
}

const MinimalCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const chunks = groupWordsIntoChunks(words, style.maxWordsPerChunk, fps)

  const activeChunk = chunks.find(
    (c) => frame >= c.startFrame && frame <= c.endFrame,
  )

  if (!activeChunk) return null

  const animStyle = style.animationStyle || 'pop'

  let opacity = 1
  let transform = 'none'

  if (animStyle === 'pop' || animStyle === 'fade') {
    opacity = interpolate(
      frame,
      [activeChunk.startFrame, activeChunk.startFrame + 3],
      [0, 1],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
  }

  if (animStyle === 'pop') {
    const s = interpolate(
      frame,
      [activeChunk.startFrame, activeChunk.startFrame + 4],
      [0.88, 1],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    transform = `scale(${s})`
  } else if (animStyle === 'slideUp') {
    const y = interpolate(
      frame,
      [activeChunk.startFrame, activeChunk.startFrame + 5],
      [30, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    opacity = interpolate(
      frame,
      [activeChunk.startFrame, activeChunk.startFrame + 3],
      [0, 1],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    )
    transform = `translateY(${y}px)`
  }

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        // AbsoluteFill é flexDirection: column — justifyContent controla o eixo
        // VERTICAL e alignItems o HORIZONTAL. Com os papéis invertidos, "bottom"
        // renderizava a legenda no meio-direita do export (bug pego pela matriz E2E).
        justifyContent: style.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: style.position === 'bottom' ? style.marginBottom : 0,
      }}
    >
      <div
        style={{
          opacity,
          transform,
          padding: '12px 28px',
          borderRadius: 8,
          backgroundColor: style.backgroundColor,
          maxWidth: '85%',
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: 800,
            color: style.color,
            textTransform: 'uppercase',
            letterSpacing: '0.02em',
            lineHeight: 1.2,
            textShadow: `0 2px 8px ${style.outlineColor}`,
            WebkitTextStroke: style.strokeWidth > 0 ? `${style.strokeWidth}px ${style.outlineColor}` : undefined,
            paintOrder: style.strokeWidth > 0 ? 'stroke fill' : undefined,
          }}
        >
          {activeChunk.text}
        </span>
      </div>
    </AbsoluteFill>
  )
}

const KaraokeCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const chunks = groupWordsIntoChunks(words, style.maxWordsPerChunk, fps)

  const activeChunk = chunks.find(
    (c) => frame >= c.startFrame && frame <= c.endFrame,
  )
  if (!activeChunk) return null

  const chunkIdx = chunks.indexOf(activeChunk)
  const chunkStartIdx = chunkIdx * style.maxWordsPerChunk
  const chunkWords = words.slice(chunkStartIdx, chunkStartIdx + style.maxWordsPerChunk)
  const currentTime = frame / fps

  const opacity = interpolate(
    frame,
    [activeChunk.startFrame, activeChunk.startFrame + 3],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  )

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        // AbsoluteFill é flexDirection: column — justifyContent controla o eixo
        // VERTICAL e alignItems o HORIZONTAL. Com os papéis invertidos, "bottom"
        // renderizava a legenda no meio-direita do export (bug pego pela matriz E2E).
        justifyContent: style.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: style.position === 'bottom' ? style.marginBottom : 0,
      }}
    >
      <div style={{ opacity, maxWidth: '85%', textAlign: 'center' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '0 12px' }}>
          {chunkWords.map((word, i) => {
            const isActive = currentTime >= word.start && currentTime <= word.end
            const isPast = currentTime > word.end
            const progress = isActive
              ? Math.min(1, (currentTime - word.start) / (word.end - word.start))
              : isPast ? 1 : 0

            // Cor sólida por palavra: background-clip:text NÃO é suportado pelo
            // compositor de vídeo do Remotion (renderMedia) — o gradiente virava
            // uma CAIXA atrás do texto no MP4 (só o still renderizava certo).
            void progress
            return (
              <span
                key={`${chunkIdx}-${i}`}
                style={{
                  fontFamily: style.fontFamily,
                  fontSize: style.fontSize,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.02em',
                  lineHeight: 1.3,
                  WebkitTextStroke: style.strokeWidth > 0 ? `${style.strokeWidth}px ${style.outlineColor}` : undefined,
                  paintOrder: style.strokeWidth > 0 ? 'stroke fill' : undefined,
                  color: isActive || isPast ? style.accentColor : style.color,
                  opacity: isActive || isPast ? 1 : 0.55,
                  textShadow: isActive ? `0 0 20px ${style.accentColor}66` : `0 2px 8px ${style.outlineColor}`,
                }}
              >
                {word.word}
              </span>
            )
          })}
        </div>
      </div>
    </AbsoluteFill>
  )
}

const BoxedCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const chunks = groupWordsIntoChunks(words, style.maxWordsPerChunk, fps)

  const activeChunk = chunks.find(
    (c) => frame >= c.startFrame && frame <= c.endFrame,
  )
  if (!activeChunk) return null

  const chunkText = activeChunk.text.toUpperCase()
  // Split into ~2 lines based on maxWordsPerChunk
  const chunkWords = chunkText.split(' ')
  const mid = Math.ceil(chunkWords.length / 2)
  const lines = chunkWords.length > 2
    ? [chunkWords.slice(0, mid).join(' '), chunkWords.slice(mid).join(' ')]
    : [chunkText]

  const opacity = interpolate(
    frame,
    [activeChunk.startFrame, activeChunk.startFrame + 3],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  )

  const bgColor = style.backgroundColor !== 'transparent'
    ? style.backgroundColor
    : (style.accentColor + '55')

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        // AbsoluteFill é flexDirection: column — justifyContent controla o eixo
        // VERTICAL e alignItems o HORIZONTAL. Com os papéis invertidos, "bottom"
        // renderizava a legenda no meio-direita do export (bug pego pela matriz E2E).
        justifyContent: style.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: style.position === 'bottom' ? style.marginBottom : 0,
      }}
    >
      <div style={{ opacity, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
        {lines.map((lineText, lineIdx) => {
          const lineDelay = lineIdx * 2 // 2 frames stagger
          const boxScale = interpolate(
            frame,
            [activeChunk.startFrame + lineDelay, activeChunk.startFrame + lineDelay + 4],
            [0.3, 1],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
          )
          const textOpacity = interpolate(
            frame,
            [activeChunk.startFrame + lineDelay + 1, activeChunk.startFrame + lineDelay + 4],
            [0, 1],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
          )
          return (
            <div
              key={lineIdx}
              style={{
                backgroundColor: bgColor,
                borderRadius: 8,
                padding: '8px 20px',
                transform: `scaleX(${boxScale})`,
                transformOrigin: 'center',
              }}
            >
              <span
                style={{
                  fontFamily: style.fontFamily,
                  fontSize: style.fontSize,
                  fontWeight: 800,
                  color: style.color,
                  textTransform: 'uppercase',
                  letterSpacing: '0.02em',
                  lineHeight: 1.2,
                  opacity: textOpacity,
                  WebkitTextStroke: style.strokeWidth > 0 ? `${style.strokeWidth}px ${style.outlineColor}` : undefined,
                  paintOrder: style.strokeWidth > 0 ? 'stroke fill' : undefined,
                  textShadow: `0 2px 8px ${style.outlineColor}`,
                }}
              >
                {lineText}
              </span>
            </div>
          )
        })}
      </div>
    </AbsoluteFill>
  )
}

// Pop e Neon compartilham o chunk + pop-in do Minimal, mudando so o estilo do texto.
const ChunkCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
  textStyle: (style: SubtitleStyle) => React.CSSProperties
}> = ({ words, style, textStyle }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const chunks = groupWordsIntoChunks(words, style.maxWordsPerChunk, fps)
  const activeChunk = chunks.find((c) => frame >= c.startFrame && frame <= c.endFrame)
  if (!activeChunk) return null

  const opacity = interpolate(frame, [activeChunk.startFrame, activeChunk.startFrame + 3], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })
  const s = interpolate(frame, [activeChunk.startFrame, activeChunk.startFrame + 5], [0.8, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  })

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        // AbsoluteFill é flexDirection: column — justifyContent controla o eixo
        // VERTICAL e alignItems o HORIZONTAL. Com os papéis invertidos, "bottom"
        // renderizava a legenda no meio-direita do export (bug pego pela matriz E2E).
        justifyContent: style.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: style.position === 'bottom' ? style.marginBottom : 0,
      }}
    >
      <div style={{ opacity, transform: `scale(${s})`, maxWidth: '85%', textAlign: 'center' }}>
        <span style={textStyle(style)}>{activeChunk.text}</span>
      </div>
    </AbsoluteFill>
  )
}

const popTextStyle = (style: SubtitleStyle): React.CSSProperties => ({
  fontFamily: style.fontFamily,
  fontSize: style.fontSize,
  fontWeight: 900,
  color: style.accentColor,
  textTransform: 'uppercase',
  letterSpacing: '0.02em',
  lineHeight: 1.2,
  WebkitTextStroke: `${Math.max(style.strokeWidth, 2)}px ${style.outlineColor}`,
  paintOrder: 'stroke fill',
  textShadow: `0 3px 10px ${style.outlineColor}`,
})

const neonTextStyle = (style: SubtitleStyle): React.CSSProperties => ({
  fontFamily: style.fontFamily,
  fontSize: style.fontSize,
  fontWeight: 800,
  color: style.color,
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
  lineHeight: 1.2,
  textShadow: `0 0 6px ${style.accentColor}, 0 0 16px ${style.accentColor}, 0 0 34px ${style.accentColor}`,
})

export const SubtitleOverlay: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  switch (style.preset) {
    case 'tiktok':
      return <TikTokCaptions words={words} style={style} />
    case 'impact':
      return <ImpactCaptions words={words} style={style} />
    case 'karaoke':
      return <KaraokeCaptions words={words} style={style} />
    case 'boxed':
      return <BoxedCaptions words={words} style={style} />
    case 'pop':
      return <ChunkCaptions words={words} style={style} textStyle={popTextStyle} />
    case 'neon':
      return <ChunkCaptions words={words} style={style} textStyle={neonTextStyle} />
    case 'minimal':
    default:
      return <MinimalCaptions words={words} style={style} />
  }
}
