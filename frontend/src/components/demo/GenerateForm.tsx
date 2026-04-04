'use client'

import { useState } from 'react'

interface Props {
  onGenerate: (topic: string, style: string, duration: number) => void
  isGenerating: boolean
}

export default function GenerateForm({ onGenerate, isGenerating }: Props) {
  const [topic, setTopic] = useState('')
  const [style, setStyle] = useState('educational')
  const [duration, setDuration] = useState(45)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (topic.length >= 5) onGenerate(topic, style, duration)
  }

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
        <select
          value={style}
          onChange={e => setStyle(e.target.value)}
          className="flex-1 px-4 py-3 rounded-lg bg-white/5 border border-gray-700 text-white focus:border-purple-500 focus:outline-none"
        >
          <option value="educational">Educativo</option>
          <option value="curiosity">Curiosidades</option>
          <option value="storytelling">Narrativa</option>
          <option value="news">Noticias</option>
        </select>
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
        ) : 'Gerar Video'}
      </button>
    </form>
  )
}
