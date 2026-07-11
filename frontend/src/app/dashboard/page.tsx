'use client'

import { Mail } from 'lucide-react'
import { strings } from '@/lib/strings';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJobs, cancelJob, ACTIVE_JOB_STATUSES, type JobSummary } from '@/lib/editor-api'
import { useAuth } from '@/contexts/AuthContext'
import GenerateForm from '@/components/dashboard/GenerateForm'
import TrendingPanel, { type TrendSelection } from '@/components/dashboard/TrendingPanel'
import VideoGrid from '@/components/dashboard/VideoGrid'
import ReferralCard from '@/components/dashboard/ReferralCard'
import { InlineError, useToast } from '@/components/ui/feedback'
import { PretextHeading } from '@/components/ui/PretextHeading'
import { fetchPublicConfig } from '@/lib/config'

export default function DashboardPage() {
  const router = useRouter()
  const { user, refreshUser } = useAuth()
  const { success: toastSuccess, error: toastError } = useToast()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [prefill, setPrefill] = useState<TrendSelection | null>(null)
  const formRef = useRef<HTMLDivElement>(null)
  // Número prometido no banner vem do backend (guardrail: nunca hardcodar oferta).
  const [welcomeBonus, setWelcomeBonus] = useState<number | null>(null)
  useEffect(() => {
    fetchPublicConfig().then((c) => setWelcomeBonus(c.welcome_credit_bonus))
  }, [])

  const loadJobs = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      setJobs(await fetchJobs())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível carregar os vídeos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadJobs() }, [loadJobs])

  // ── Grid reativa: enquanto houver job ativo, re-busca a lista com backoff.
  // O efeito só liga/desliga quando a "atividade" muda (não a cada poll), então o
  // backoff sobrevive entre ticks. Toast + refresh de créditos nas transições.
  const hasActiveJobs = useMemo(() => jobs.some((j) => ACTIVE_JOB_STATUSES.includes(j.status)), [jobs])
  const jobsRef = useRef(jobs)
  useEffect(() => { jobsRef.current = jobs }, [jobs])

  useEffect(() => {
    if (!hasActiveJobs) return
    let cancelled = false
    let delay = 4000
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      try {
        const fresh = await fetchJobs()
        if (cancelled) return
        delay = 4000
        const before = new Map(jobsRef.current.map((j) => [j.job_id, j.status]))
        for (const j of fresh) {
          const prev = before.get(j.job_id)
          if (!prev || !ACTIVE_JOB_STATUSES.includes(prev) || ACTIVE_JOB_STATUSES.includes(j.status)) continue
          if (['completed', 'editable'].includes(j.status)) {
            toastSuccess('Vídeo pronto', j.topic)
          } else if (['failed', 'error'].includes(j.status)) {
            toastError('A geração falhou', j.topic)
          }
          refreshUser() // créditos podem ter mudado (conclusão ou reembolso)
        }
        setJobs(fresh)
      } catch {
        // Blip de rede: não zera a grid; só espaça o próximo poll.
        if (!cancelled) delay = Math.min(delay * 2, 20000)
      }
      if (!cancelled) timer = setTimeout(tick, delay)
    }

    timer = setTimeout(tick, delay)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [hasActiveJobs, refreshUser, toastSuccess, toastError])

  const handleCancel = useCallback(async (jobId: string) => {
    try {
      await cancelJob(jobId)
      toastSuccess('Vídeo cancelado', 'O crédito da geração será devolvido.')
      // Atualiza estado local imediatamente e recarrega a lista.
      setJobs((prev) => prev.filter((j) => j.job_id !== jobId))
      await Promise.all([loadJobs(), refreshUser()])
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Não foi possível cancelar o vídeo'
      toastError('Não foi possível cancelar', message)
      await loadJobs()
    }
  }, [loadJobs, refreshUser, toastSuccess, toastError])

  const greeting = user?.name ? `Olá, ${user.name.split(' ')[0]}.` : 'Olá.'
  const hour = new Date().getHours()
  const timeGreeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'

  // Cockpit da 1ª dobra: números REAIS do criador (nada decorativo — cada chip é um atalho)
  const readyCount = jobs.filter((j) => ['completed', 'editable'].includes(j.status)).length
  const activeCount = jobs.filter((j) => ACTIVE_JOB_STATUSES.includes(j.status)).length

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="mb-10">
        <h1 className="font-display text-3xl sm:text-4xl md:text-[2.9rem] font-extrabold text-white mb-2.5 tracking-tight leading-[1.05]">
          <span className="text-coral">{timeGreeting}.</span> {greeting}
          <br className="hidden sm:block" /> Pronto para criar?
        </h1>
        <p className="text-[var(--text-secondary)] text-lg">
          Do tema ao vídeo pronto — narração, legendas e edição inclusas.
        </p>

        {!loading && user && (
          <div className="mt-5 flex flex-wrap gap-2.5">
            <button
              type="button"
              onClick={() => router.push('/dashboard/credits')}
              className="flex items-center gap-2 rounded-full border border-coral/25 bg-coral/10 px-3.5 py-1.5 text-[13px] text-coral transition hover:bg-coral/15"
            >
              <span className="font-bold tabular-nums">{user.credits}</span> créditos
            </button>
            <button
              type="button"
              onClick={() => document.getElementById('videos')?.scrollIntoView({ behavior: 'smooth' })}
              className="flex items-center gap-2 rounded-full border border-mint/25 bg-mint/10 px-3.5 py-1.5 text-[13px] text-mint transition hover:bg-mint/15"
            >
              <span className="font-bold tabular-nums">{readyCount}</span> vídeo{readyCount === 1 ? '' : 's'} pronto{readyCount === 1 ? '' : 's'}
            </button>
            {activeCount > 0 && (
              <button
                type="button"
                onClick={() => document.getElementById('videos')?.scrollIntoView({ behavior: 'smooth' })}
                className="flex items-center gap-2 rounded-full border border-azure/25 bg-azure/10 px-3.5 py-1.5 text-[13px] text-azure transition hover:bg-azure/15 animate-pulse"
              >
                <span className="font-bold tabular-nums">{activeCount}</span> gerando agora
              </button>
            )}
          </div>
        )}
      </div>

      {user && !user.email_verified && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-5 mb-8 flex flex-col md:flex-row items-center justify-between gap-4 backdrop-blur-md">
          <div className="flex items-start gap-3">
            <Mail className="w-5 h-5 text-yellow-300 mt-0.5 shrink-0" />
            <div>
              <p className="text-yellow-200 font-semibold mb-1">{strings.auth.verify.title}</p>
              <p className="text-yellow-200/70 text-sm">
                Confirme seu e-mail para receber {welcomeBonus ?? 'seus'} créditos grátis e começar a gerar vídeos.
              </p>
            </div>
          </div>
          <button
            onClick={() => router.push(`/auth/verify?email=${encodeURIComponent(user.email)}`)}
            className="shrink-0 px-6 py-2.5 rounded-lg bg-yellow-500/20 text-yellow-200 hover:bg-yellow-500/30 transition border border-yellow-500/30 font-medium text-sm"
          >
            {strings.dashboard.verifyBanner.cta}
          </button>
        </div>
      )}

      {/* Ação nº 1 do produto vem PRIMEIRO: o formulário de geração (auditoria F0 —
          o feed de ideias abaixo é apoio, não protagonista). */}
      <div ref={formRef} id="studio" className="relative rounded-3xl bg-[var(--bg-raised)] border border-white/5 overflow-hidden p-6 md:p-10 shadow-2xl mb-10">
        <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 pointer-events-none mix-blend-overlay"></div>
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-coral/20 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="relative z-10">
          <GenerateForm
            onJobCreated={loadJobs}
            prefillTopic={prefill?.topic}
            prefillTrendContext={prefill?.trendContext}
            prefillTemplateId={prefill?.templateId}
            prefillStyle={prefill?.style}
          />
        </div>
      </div>

      {/* Ideias e tendências — apoio à geração (clique preenche o formulário acima) */}
      <TrendingPanel
        onSelect={(sel) => {
          setPrefill(sel)
          formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
      />

      <div className="mb-10">
        <ReferralCard />
      </div>

      <section id="videos" className="mt-8 scroll-mt-20">
        <div className="flex items-center justify-between mb-8 border-b border-white/5 pb-4">
          <h2 className="font-display text-2xl font-extrabold text-white">Seus vídeos</h2>
          <div className="text-sm text-slate-500 font-medium bg-white/5 px-3 py-1 rounded-full border border-white/5">
            {jobs.length} vídeos
          </div>
        </div>
        
        {error ? (
          <InlineError
            title="Não foi possível carregar seus vídeos"
            description={error}
            onRetry={loadJobs}
          />
        ) : (
          <VideoGrid
            jobs={jobs}
            loading={loading}
            onEdit={(id) => router.push(`/editor/${id}`)}
            onCancel={handleCancel}
          />
        )}
      </section>
    </div>
  )
}
