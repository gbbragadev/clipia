'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { getToken } from '@/lib/auth'

interface Props {
  onGenerate: (topic: string, style: string, duration: number) => void
  isGenerating: boolean
}

const STYLES = [
  { value: 'educational', label: 'Educativo' },
  { value: 'curiosity', label: 'Curiosidades' },
  { value: 'storytelling', label: 'Narrativa' },
  { value: 'news', label: 'Notícias' },
  { value: 'humor', label: 'Humor' },
  { value: 'motivational', label: 'Motivacional' },
  { value: 'conspiracy', label: 'Mistério' },
  { value: 'top5', label: 'Top 5' },
  { value: 'tutorial', label: 'Tutorial' },
  { value: 'debate', label: 'Debate' },
  { value: 'horror', label: 'Terror' },
  { value: 'scifi', label: 'Sci-Fi' },
]

function CustomSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = STYLES.find((s) => s.value === value)

  useEffect(() => {
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) {
      document.addEventListener('mousedown', close)
      return () => document.removeEventListener('mousedown', close)
    }
  }, [open])

  return (
    <div className="relative flex-1" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 rounded-lg bg-white/5 border border-gray-700 text-white text-left text-sm focus:border-purple-500 focus:outline-none transition flex items-center justify-between cursor-pointer"
      >
        <span>{selected?.label || 'Estilo'}</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className={`transition ${open ? 'rotate-180' : ''}`}>
          <path d="M3 4.5L6 7.5L9 4.5" stroke="#888" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 right-0 mt-1 rounded-lg bg-[#14141e] border border-gray-700 shadow-xl z-50 max-h-48 overflow-y-auto">
          {STYLES.map((s) => (
            <button
              key={s.value}
              type="button"
              onClick={() => { onChange(s.value); setOpen(false) }}
              className={`w-full px-4 py-2 text-left text-sm transition cursor-pointer ${
                s.value === value
                  ? 'bg-purple-500/20 text-purple-300'
                  : 'text-gray-300 hover:bg-white/5'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function GenerateForm({ onGenerate, isGenerating }: Props) {
  const [topic, setTopic] = useState('')
  const [style, setStyle] = useState('educational')
  const [duration, setDuration] = useState(45)
  const router = useRouter()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!getToken()) {
      router.push('/auth/login')
      return
    }
    if (topic.length >= 5) onGenerate(topic, style, duration)
  }

  const [isLoggedIn, setIsLoggedIn] = useState(false)
  useEffect(() => { setIsLoggedIn(!!getToken()) }, [])

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="text"
        value={topic}
        onChange={e => setTopic(e.target.value)}
        placeholder="Ex: 5 curiosidades sobre o oceano profundo"
        minLength={5}
        required
        className="w-full px-4 py-3 rounded-lg bg-white/5 border border-gray-700 text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none transition"
      />
      <div className="flex gap-4">
        <CustomSelect value={style} onChange={setStyle} />
        <div className="flex-1 flex items-center gap-3">
          <input
            type="range"
            min={20} max={60} value={duration}
            onChange={e => setDuration(Number(e.target.value))}
            className="flex-1 accent-purple-500"
          />
          <span className="text-gray-400 text-sm w-8">{duration}s</span>
        </div>
      </div>
      <button
        type="submit"
        disabled={isGenerating || topic.length < 5}
        className="w-full py-3 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium disabled:opacity-50 hover:opacity-90 transition flex items-center justify-center gap-2"
      >
        {isGenerating ? (
          <>
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            Gerando...
          </>
        ) : isLoggedIn ? 'Gerar Vídeo' : 'Entrar e Gerar Vídeo'}
      </button>
    </form>
  )
}
