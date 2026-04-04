'use client'

import { useEffect, useRef, useState } from 'react'
import { useTextLayout } from '@/hooks/useTextLayout'

interface OpticalBalancePreviewProps {
  text: string
  font?: string
}

const DEFAULT_FONT = '700 18px Inter, system-ui, sans-serif'
const SEARCH_ITERATIONS = 20
const DEBOUNCE_MS = 300

export default function OpticalBalancePreview({ text, font = DEFAULT_FONT }: OpticalBalancePreviewProps) {
  const { getLineRanges } = useTextLayout(text, font)
  const [balancedWidth, setBalancedWidth] = useState<number | null>(null)
  const [lineCount, setLineCount] = useState(0)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)

    if (!text.trim()) {
      setBalancedWidth(null)
      setLineCount(0)
      return
    }

    debounceRef.current = setTimeout(() => {
      let lo = 40
      let hi = 700

      let naturalLines = 0
      getLineRanges(hi, () => { naturalLines++ })
      if (naturalLines <= 1) {
        const widths: number[] = []
        getLineRanges(hi, (line) => widths.push(line.width))
        setBalancedWidth(Math.ceil((widths[0] || 200) + 2))
        setLineCount(1)
        return
      }

      const targetLines = naturalLines

      for (let i = 0; i < SEARCH_ITERATIONS; i++) {
        const mid = (lo + hi) / 2
        const widths: number[] = []
        getLineRanges(mid, (line) => widths.push(line.width))

        if (widths.length <= targetLines) {
          const lastWidth = widths[widths.length - 1] || 0
          const firstWidth = widths[0] || 1
          if (lastWidth >= firstWidth * 0.65) {
            hi = mid
          } else {
            lo = mid
          }
        } else {
          lo = mid
        }
      }

      setBalancedWidth(Math.ceil(hi + 2))
      setLineCount(targetLines)
    }, DEBOUNCE_MS)

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [text, font, getLineRanges])

  if (!text.trim() || !balancedWidth) return null

  return (
    <div className="mt-2 mb-1">
      <div
        className="mx-auto px-3 py-2 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)]"
        style={{
          width: `${Math.min(balancedWidth, 100)}%`,
          maxWidth: `${balancedWidth}px`,
          transition: 'max-width 600ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <p
          className="text-center text-[var(--text-primary)] leading-snug break-words"
          style={{ font }}
        >
          {text}
        </p>
      </div>
      <p className="text-center text-[10px] text-[var(--text-tertiary)] mt-1.5">
        {balancedWidth}px &middot; {lineCount} {lineCount === 1 ? 'linha' : 'linhas'} &middot; balanceado
      </p>
    </div>
  )
}
