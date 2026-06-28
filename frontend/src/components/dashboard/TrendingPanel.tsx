'use client'

import { useEffect, useState } from 'react'
import { fetchTrends, type Trend } from '@/lib/editor-api'
import { NICHES } from '@/lib/niches'

interface TrendingPanelProps {
  onSelect: (topic: string, trendContext: string) => void
}

const SOURCE_LABEL: Record<string, string> = {
  reddit: 'Reddit',
  hackernews: 'Hacker News',
  google_trends: 'Google Trends',
}

function trendContextOf(t: Trend): string {
  return t.context ? `${t.title}. ${t.context}` : t.title
}

export default function TrendingPanel({ onSelect }: TrendingPanelProps) {
  const [niche, setNiche] = useState<string | null>(null) // null = feed geral
  const [trends, setTrends] = useState<Trend[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    fetchTrends(niche ?? undefined)
      .then((data) => { if (active) setTrends(data) })
      .catch(() => { if (active) setTrends([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [niche])

  return (
    <div className="relative rounded-3xl bg-[#110d1a] border border-white/5 p-6 md:p-8 shadow-2xl mb-10">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">🔥</span>
        <h2 className="text-lg font-bold text-white">Em alta agora</h2>
      </div>
      <p className="text-sm text-slate-400 mb-5">
        Temas com tração real nos últimos 30 dias. Clique para gerar um vídeo já fundamentado nos dados.
      </p>

      {/* Filtro por nicho */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          type="button"
          onClick={() => setNiche(null)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition cursor-pointer ${
            niche === null
              ? 'border-purple-500/50 bg-purple-500/10 text-purple-300'
              : 'border-white/10 bg-white/5 text-slate-400 hover:border-purple-500/30'
          }`}
        >
          🌎 Geral
        </button>
        {NICHES.map((n) => (
          <button
            key={n.slug}
            type="button"
            onClick={() => setNiche(n.slug)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition cursor-pointer ${
              niche === n.slug
                ? 'border-purple-500/50 bg-purple-500/10 text-purple-300'
                : 'border-white/10 bg-white/5 text-slate-400 hover:border-purple-500/30'
            }`}
          >
            {n.emoji} {n.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid sm:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : trends.length === 0 ? (
        <p className="text-sm text-slate-500 py-6 text-center">
          Nenhuma tendência disponível agora. Tente outro nicho ou escreva um tema manualmente abaixo.
        </p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {trends.map((t, i) => (
            <div
              key={`${t.url}-${i}`}
              className="group flex items-start justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3 hover:border-purple-500/30 transition"
            >
              <div className="min-w-0">
                <p className="text-sm text-slate-200 line-clamp-2">{t.title}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] uppercase tracking-wide text-slate-500">
                    {SOURCE_LABEL[t.source] ?? t.source}
                  </span>
                  {t.score >= 0.66 && <span className="text-[10px]">🔥</span>}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onSelect(t.title, trendContextOf(t))}
                className="shrink-0 self-center rounded-lg bg-purple-600/90 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-purple-500 transition cursor-pointer"
              >
                Gerar
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
