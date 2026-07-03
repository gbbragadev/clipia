'use client'

import { Mail } from 'lucide-react'
import { strings } from '@/lib/strings';
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJobs, cancelJob, type JobSummary } from '@/lib/editor-api'
import { useAuth } from '@/contexts/AuthContext'
import GenerateForm from '@/components/dashboard/GenerateForm'
import TrendingPanel from '@/components/dashboard/TrendingPanel'
import VideoGrid from '@/components/dashboard/VideoGrid'
import ReferralCard from '@/components/dashboard/ReferralCard'
import { InlineError, useToast } from '@/components/ui/feedback'
import { PretextHeading } from '@/components/ui/PretextHeading'

export default function DashboardPage() {
  const router = useRouter()
  const { user, refreshUser } = useAuth()
  const { success: toastSuccess, error: toastError } = useToast()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [prefill, setPrefill] = useState<{ topic: string; trendContext: string } | null>(null)
  const formRef = useRef<HTMLDivElement>(null)

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

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <div className="mb-10">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-display font-bold text-white mb-2 tracking-tight">
          <span className="text-coral">{timeGreeting}.</span> {greeting} Pronto para criar?
        </h1>
        <p className="text-slate-400 text-lg">Transforme suas ideias em vídeos com apenas um clique.</p>
      </div>

      {user && !user.email_verified && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-5 mb-8 flex flex-col md:flex-row items-center justify-between gap-4 backdrop-blur-md">
          <div className="flex items-start gap-3">
            <Mail className="w-5 h-5 text-yellow-300 mt-0.5 shrink-0" />
            <div>
              <p className="text-yellow-200 font-semibold mb-1">{strings.auth.verify.title}</p>
              <p className="text-yellow-200/70 text-sm">Confirme seu e-mail para receber 2 créditos grátis e começar a gerar vídeos.</p>
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

      {/* Painel "Em alta" — descoberta de temas em tendência */}
      <TrendingPanel
        onSelect={(topic, trendContext) => {
          setPrefill({ topic, trendContext })
          formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }}
      />

      {/* Studio-like Generate Form Wrapper */}
      <div ref={formRef} className="relative rounded-3xl bg-[#110d1a] border border-white/5 overflow-hidden p-6 md:p-10 shadow-2xl mb-16">
        <div className="absolute inset-0 bg-[url(/noise.svg)] opacity-20 pointer-events-none mix-blend-overlay"></div>
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-coral/20 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="relative z-10">
          <GenerateForm
            onJobComplete={loadJobs}
            prefillTopic={prefill?.topic}
            prefillTrendContext={prefill?.trendContext}
          />
        </div>
      </div>

      <div className="mb-10">
        <ReferralCard />
      </div>

      <section className="mt-8">
        <div className="flex items-center justify-between mb-8 border-b border-white/5 pb-4">
          <h2 className="text-2xl font-display font-bold text-white">Seus vídeos</h2>
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
