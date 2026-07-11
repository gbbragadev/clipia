'use client'

import { useEffect, useState } from 'react'
import { fetchTrends, fetchExampleTopics, type Trend } from '@/lib/editor-api'
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
  // O feed cru das fontes (Reddit/HN/Trends) vem traduzido quando possível — segue
  // colapsado por padrão; os "temas prontos" pt-BR por nicho são o caminho principal.
  const [showFeed, setShowFeed] = useState(false)
  // Temas prontos por IA (renovam a cada hora no backend); [] → fallback estático.
  const [aiTopics, setAiTopics] = useState<string[]>([])

  useEffect(() => {
    if (!showFeed) return
    let active = true
    setLoading(true)
    fetchTrends(niche ?? undefined)
      .then((data) => { if (active) setTrends(data) })
      .catch(() => { if (active) setTrends([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [niche, showFeed])

  useEffect(() => {
    if (!niche) { setAiTopics([]); return }
    let active = true
    setAiTopics([])
    fetchExampleTopics(niche)
      .then((topics) => { if (active) setAiTopics(topics) })
      .catch(() => { if (active) setAiTopics([]) })
    return () => { active = false }
  }, [niche])

  return (
    <div className="relative rounded-3xl bg-[var(--bg-raised)] border border-white/5 p-6 md:p-8 shadow-2xl mb-10">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xl" aria-hidden>💡</span>
        <h2 className="text-lg font-bold text-white">Precisa de uma ideia?</h2>
      </div>
      <p className="text-sm text-[var(--text-secondary)] mb-5">
        Escolha um nicho e clique num tema pronto — ele preenche o formulário acima com o template certo.
      </p>

      {/* Filtro por nicho */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          type="button"
          onClick={() => setNiche(null)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition cursor-pointer ${
            niche === null
              ? 'border-coral/50 bg-coral/10 text-coral'
              : 'border-white/10 bg-white/5 text-[var(--text-secondary)] hover:border-coral/30'
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
                : 'border-white/10 bg-white/5 text-[var(--text-secondary)] hover:border-coral/30'
            }`}
          >
            {n.emoji} {n.label}
          </button>
        ))}
      </div>

      {/* Convite quando nenhum nicho está selecionado (o feed cru fica colapsado) */}
      {niche === null && !showFeed && (
        <p className="text-sm text-[var(--text-tertiary)] py-2">
          Selecione um nicho acima para ver temas prontos em português.
        </p>
      )}

      {/* Temas prontos — IA rotativa (renovam a cada hora) com fallback estático */}
      {niche !== null && (
        <div className="mb-5 pb-5 border-b border-white/5">
          <div className="flex items-start gap-2 mb-3">
            <span className="text-sm" aria-hidden>✨</span>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-white">Temas prontos</h3>
              <p className="text-[11px] text-[var(--text-secondary)] mt-1">
                {aiTopics.length > 0
                  ? 'Gerados por IA para este nicho — renovam a cada hora. Clique para usar.'
                  : 'Assuntos que funcionam sempre — clique para usar.'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {(aiTopics.length > 0 ? aiTopics : NICHES.find((n) => n.slug === niche)?.exampleTopics ?? []).map((topic, i) => (
              <button
                key={`${topic}-${i}`}
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
                className="px-3 py-1.5 rounded-full text-xs text-[var(--text-primary)] border border-white/10 bg-white/[0.03] hover:border-coral/50 hover:bg-coral/5 transition cursor-pointer"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Feed cru das fontes — colapsado por padrão (majoritariamente em inglês) */}
      <button
        type="button"
        onClick={() => setShowFeed((v) => !v)}
        aria-expanded={showFeed}
        className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition cursor-pointer"
      >
        <span className="transition-transform" style={{ transform: showFeed ? 'rotate(90deg)' : 'rotate(0deg)' }} aria-hidden>
          ▶
        </span>
        Tendências das fontes (Reddit, Hacker News, Google Trends — traduzidas para pt-BR)
      </button>

      {!showFeed ? null : loading ? (
        <div className="mt-4 grid sm:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="anim-shimmer relative h-16 overflow-hidden rounded-xl border border-white/5 bg-white/5 p-3">
              <div className="h-3 w-4/5 rounded bg-white/10" />
              <div className="mt-2 h-2.5 w-2/5 rounded bg-white/[0.07]" />
            </div>
          ))}
        </div>
      ) : trends.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)] py-6 text-center">
          Nenhuma tendência disponível agora. Tente outro nicho ou escreva um tema manualmente acima.
        </p>
      ) : (
        <div className="mt-4 grid sm:grid-cols-2 gap-3">
          {trends.map((t, i) => {
            const nicheDef = niche ? NICHES.find((n) => n.slug === niche) : undefined
            return (
              <div
                key={`${t.url}-${i}`}
                className="group flex items-start justify-between gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3 hover:border-coral/30 transition"
              >
                <div className="min-w-0">
                  {/* Exibe a tradução pt-BR quando houver; o grounding do roteiro usa o original */}
                  <p className="text-sm text-[var(--text-primary)] line-clamp-2">{t.title_pt || t.title}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">
                      {SOURCE_LABEL[t.source] ?? t.source}
                      {t.title_pt && t.title_pt !== t.title ? ' · traduzido' : ''}
                    </span>
                    {t.score >= 0.66 && <span className="text-[10px]">🔥</span>}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onSelect({
                    topic: t.title_pt || t.title,
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
