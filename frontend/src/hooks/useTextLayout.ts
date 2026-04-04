'use client'

import { useEffect, useRef, useCallback } from 'react'
import {
  prepareWithSegments,
  layout,
  layoutWithLines,
  walkLineRanges,
  layoutNextLine,
  type PreparedTextWithSegments,
  type LayoutResult,
  type LayoutLinesResult,
  type LayoutLineRange,
  type LayoutLine,
  type LayoutCursor,
} from '@chenglou/pretext'

export type { PreparedTextWithSegments, LayoutResult, LayoutLinesResult, LayoutLineRange, LayoutLine, LayoutCursor }

export function useTextLayout(text: string, font: string) {
  const preparedRef = useRef<PreparedTextWithSegments | null>(null)
  const prevTextRef = useRef('')
  const prevFontRef = useRef('')

  useEffect(() => {
    if (text === prevTextRef.current && font === prevFontRef.current) return

    const init = () => {
      prevTextRef.current = text
      prevFontRef.current = font
      preparedRef.current = prepareWithSegments(text, font)
    }

    if (document.fonts?.ready) {
      document.fonts.ready.then(init)
    } else {
      init()
    }
  }, [text, font])

  const getLayout = useCallback((maxWidth: number, lineHeight: number): LayoutLinesResult | null => {
    if (!preparedRef.current) return null
    return layoutWithLines(preparedRef.current, maxWidth, lineHeight)
  }, [])

  const getLineRanges = useCallback((maxWidth: number, onLine: (line: LayoutLineRange) => void): number => {
    if (!preparedRef.current) return 0
    return walkLineRanges(preparedRef.current, maxWidth, onLine)
  }, [])

  const getNextLine = useCallback((start: LayoutCursor, maxWidth: number): LayoutLine | null => {
    if (!preparedRef.current) return null
    return layoutNextLine(preparedRef.current, start, maxWidth)
  }, [])

  const getSimpleLayout = useCallback((maxWidth: number, lineHeight: number): LayoutResult | null => {
    if (!preparedRef.current) return null
    return layout(preparedRef.current, maxWidth, lineHeight)
  }, [])

  return {
    prepared: preparedRef,
    getLayout,
    getLineRanges,
    getNextLine,
    getSimpleLayout,
  }
}
