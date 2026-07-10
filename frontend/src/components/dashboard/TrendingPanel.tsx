'use client'

import { useEffect, useState } from 'react'
import { fetchTrends, type Trend } from '@/lib/editor-api'
import { NICHES } from '@/lib/niches'
import { type StyleValue } from './StyleSelector'

export interface TrendSelection {
  topic: string
  trendContext: string | null
  templateId?: string
  style?: StyleValue
}

interface TrendingPanelProps {
  onSelect: (sel: TrendSelection) => void
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
    <div className="relative rounded-3xl bg-[var(--bg-raised)] border border-white/5 p-6 md:p-8 shadow-2xl mb-10">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl">🔥</span>
        <h2 className="text-lg font-bold text-white">Em alta agora</h2>
      </div>
      <p className="text-sm text-slate-400 mb-5">
        Sugestões com tração real nos últimos 30 dias — use uma como ponto de partida ou escreva seu próprio tema logo abaixo.
      </p>

      {/* Filtro por nicho */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          type="button"
          onClick={() => setNiche(null)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition cursor-pointer ${
            niche === null
              ? 'border-coral/50 bg-coral/10 text-coral'
              : 'border-white/10 bg-white/5 text-slate-400 hover:border-coral/30'
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
                ? 'border-coral/50 bg-coral/10 text-coral'
                : 'border-white/10 bg-white/5 text-slate-400 hover:border-coral/30'
            }`}
          >
            {n.emoji} {n.label}
          </button>
        ))}
      </div>

      {/* Temas amplos — mostrados quando um nicho está selecionado */}
      {niche !== null && (
        <div className="mb-5 pb-5 border-b border-white/5">
          <div className="flex items-start gap-2 mb-3">
            <span className="text-sm">💡</span>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-white">Temas amplos</h3>
              <p className="text-[11px] text-slate-400 mt-1">Assuntos que funcionam sempre — clique para usar.</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {NICHES.find((n) => n.slug === niche)?.exampleTopics.map((topic, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  const nicheDef = NICHES.find((n) => n.slug === niche)
                  onSelect({
                    topic,
                    trendContext: null,
                    templateId: nicheDef?.recommendedTemplate,
                    style: nicheDef?.generateStyle,
                  })
                }}
                className="px-3 py-1.5 rounded-full text-xs text-slate-300 border border-white/10 bg-white/[0.03] hover:border-coral/50 hover:bg-coral/5 transition cursor-pointer"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid sm:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="anim-shimmer relative h-16 overflow-hidden rounded-xl border border-white/5 bg-white/5 p-3">
              <div className="h-3 w-4/5 rounded bg-white/10" />
              <div className="mt-2 h-2.5 w-2/5 rounded bg-white/[0.07]" />
            </div>
          ))}
        </div>
      ) : trends.length === 0 ? (
        <p className="text-sm text-slate-500 py-6 text-center">
          Nenhuma tendência disponível agora. Tente outro nicho ou escreva um tema manualmente abaixo.
        </p>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3">
          {trends.map((t, i) => {
            const nicheDef = niche ? NICHES.find((n) => n.slug === niche) : undefined
            return (
              <div
                key={`${t.url}-${i}`}
                className="group flex items-start justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3 hover:border-coral/30 transition"
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
                  onClick={() => onSelect({
                    topic: t.title,
                    trendContext: trendContextOf(t),
                    templateId: nicheDef?.recommendedTemplate,
                    style: nicheDef?.generateStyle,
                  })}
                  className="shrink-0 self-center rounded-lg bg-coral/90 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-coral transition cursor-pointer"
                >
                  Gerar
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
