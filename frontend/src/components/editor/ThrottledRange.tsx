'use client'

import { useEffect, useRef, useState } from 'react'

/** Range com thumb/feedback imediatos (estado local) e commit THROTTLED no contexto.
 * onChange direto disparava por pixel de drag e cada update recriava a composition —
 * remontando o Remotion Player (key=version) dezenas de vezes por segundo. */
export function ThrottledRange({
  min,
  max,
  value,
  onCommit,
  onLive,
  delay = 200,
}: {
  min: number
  max: number
  value: number
  /** Recebe o valor consolidado (~5x/s durante o drag + valor final). */
  onCommit: (v: number) => void
  /** Efeito colateral imediato por movimento (ex.: volume do preview de áudio). */
  onLive?: (v: number) => void
  delay?: number
}) {
  const [local, setLocal] = useState<number | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latest = useRef(value)

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  return (
    <input
      type="range"
      className="editor-slider"
      min={min}
      max={max}
      value={local ?? value}
      onChange={(e) => {
        const v = Number(e.target.value)
        setLocal(v)
        latest.current = v
        onLive?.(v)
        if (timer.current) return
        timer.current = setTimeout(() => {
          onCommit(latest.current)
          timer.current = null
          setLocal(null)
        }, delay)
      }}
    />
  )
}
