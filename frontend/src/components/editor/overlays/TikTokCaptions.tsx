import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion'
import type { SubtitleStyle, Word } from '@/remotion/types'

interface WordWithIndex {
  word: string
  start: number
  end: number
  index: number
}

function groupWords(words: Word[], maxWords: number): WordWithIndex[][] {
  const indexed: WordWithIndex[] = words.map((w, i) => ({ ...w, index: i }))
  const chunks: WordWithIndex[][] = []
  for (let i = 0; i < indexed.length; i += maxWords) {
    chunks.push(indexed.slice(i, i + maxWords))
  }
  return chunks
}

export const TikTokCaptions: React.FC<{
  words: Word[]
  style: SubtitleStyle
}> = ({ words, style }) => {
  const frame = useCurrentFrame()
  const { fps } = useVideoConfig()
  const currentTime = frame / fps

  const chunks = groupWords(words, style.maxWordsPerChunk)

  const activeChunk = chunks.find((group) => {
    const start = group[0].start
    const end = group[group.length - 1].end
    return currentTime >= start && currentTime <= end
  })

  if (!activeChunk) return null

  const chunkStart = activeChunk[0].start
  const fadeIn = interpolate(
    currentTime,
    [chunkStart, chunkStart + 0.15],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  )

  return (
    <AbsoluteFill
      style={{
        display: 'flex',
        // AbsoluteFill é column: justifyContent = vertical, alignItems = horizontal.
        justifyContent: style.position === 'bottom' ? 'flex-end' : 'center',
        alignItems: 'center',
        paddingBottom: style.position === 'bottom' ? style.marginBottom : 0,
      }}
    >
      <div
        style={{
          opacity: fadeIn,
          backgroundColor: style.backgroundColor,
          borderRadius: 8,
          padding: '8px 16px',
          maxWidth: '85%',
          textAlign: 'center',
        }}
      >
        <span
          style={{
            fontFamily: style.fontFamily,
            fontSize: style.fontSize,
            fontWeight: 700,
            lineHeight: 1.3,
            letterSpacing: '0.01em',
          }}
        >
          {activeChunk.map((w) => {
            const isActive = currentTime >= w.start && currentTime <= w.end
            return (
              <span
                key={w.index}
                style={{
                  color: isActive ? style.accentColor : style.color,
                  transition: 'color 0.1s ease',
                }}
              >
                {w.word}{' '}
              </span>
            )
          })}
        </span>
      </div>
    </AbsoluteFill>
  )
}
