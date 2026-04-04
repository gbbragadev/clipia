import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion'
import type { SubtitleStyle, Word } from '@/remotion/types'

function groupWords(words: Word[], maxWords: number): { text: string; start: number; end: number; wordTexts: string[] }[] {
  const chunks: { text: string; start: number; end: number; wordTexts: string[] }[] = []
  for (let i = 0; i < words.length; i += maxWords) {
    const group = words.slice(i, i + maxWords)
    chunks.push({
      text: group.map((w) => w.word).join(' ').toUpperCase(),
      start: group[0].start,
      end: group[group.length - 1].end,
      wordTexts: group.map((w) => w.word.toUpperCase()),
    })
  }
  return chunks
}

export const ImpactCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const currentTime = frame / fps

  const chunks = groupWords(words, style.maxWordsPerChunk)

  const activeChunk = chunks.find(
    (c) => currentTime >= c.start && currentTime <= c.end,
  )

  if (!activeChunk) return null

  const chunkStartFrame = Math.round(activeChunk.start * fps)

  const popIn = spring({
    frame: frame - chunkStartFrame,
    fps,
    config: {
      damping: 12,
      stiffness: 200,
      mass: 0.5,
    },
  })

  const scale = interpolate(popIn, [0, 1], [1.3, 1])
  const opacity = interpolate(popIn, [0, 1], [0, 1])

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
          transform: `scale(${scale})`,
          maxWidth: '90%',
          textAlign: 'center',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: '0 12px',
        }}
      >
        {activeChunk.wordTexts.map((word, i) => (
          <span
            key={`${chunkStartFrame}-${i}`}
            style={{
              fontFamily: style.fontFamily,
              fontSize: style.fontSize,
              fontWeight: 900,
              lineHeight: 1.1,
              color: i % 2 === 0 ? style.color : style.accentColor,
              WebkitTextStroke: `${style.strokeWidth || 3}px ${style.outlineColor}`,
              paintOrder: 'stroke fill',
              textShadow: '4px 4px 0px rgba(0, 0, 0, 0.8)',
              textTransform: 'uppercase',
            }}
          >
            {word}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  )
}
