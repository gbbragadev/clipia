import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'
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
        alignItems: style.position === 'bottom' ? 'flex-end' : 'center',
        justifyContent: 'center',
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

export const SubtitleOverlay: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  switch (style.preset) {
    case 'tiktok':
      return <TikTokCaptions words={words} style={style} />
    case 'impact':
      return <ImpactCaptions words={words} style={style} />
    case 'minimal':
    default:
      return <MinimalCaptions words={words} style={style} />
  }
}
