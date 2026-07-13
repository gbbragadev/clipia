'use client'
import { useScrollProgress } from '@/hooks/useScrollProgress'

export default function ScrollProgress() {
  const progress = useScrollProgress()
  return (
    <div className="h-[2px] bg-gray-900">
      <div
        className="h-full w-full origin-left bg-gradient-to-r from-coral via-coral-soft to-azure transition-transform duration-100 ease-linear"
        style={{ transform: `scaleX(${progress})` }}
      />
    </div>
  )
}
