'use client'

import { useEffect, useRef } from 'react'
import { prepareWithSegments, layoutWithLines } from '@chenglou/pretext'

export function useTextLayout(text: string, font: string) {
  const preparedRef = useRef<ReturnType<typeof prepareWithSegments> | null>(null)

  useEffect(() => {
    const init = () => {
      preparedRef.current = prepareWithSegments(text, font)
    }
    if (document.fonts?.ready) {
      document.fonts.ready.then(init)
    } else {
      init()
    }
  }, [text, font])

  return {
    getLayout: (maxWidth: number, lineHeight: number) => {
      if (!preparedRef.current) return null
      return layoutWithLines(preparedRef.current, maxWidth, lineHeight)
    },
    prepared: preparedRef,
  }
}
