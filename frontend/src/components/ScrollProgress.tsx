'use client'
import { useScrollProgress } from '@/hooks/useScrollProgress'

export default function ScrollProgress() {
  const progress = useScrollProgress()
  return (
    <div className="h-[2px] bg-gray-900">
      <div
        className="h-full bg-gradient-to-r from-coral via-coral-soft to-azure transition-[width] duration-100"
        style={{ width: `${progress * 100}%` }}
      />
    </div>
  )
}
