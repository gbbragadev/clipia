'use client'

import { strings } from '@/lib/strings';
import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJobs, type JobSummary } from '@/lib/editor-api'
import { useAuth } from '@/contexts/AuthContext'
import GenerateForm from '@/components/dashboard/GenerateForm'
import VideoGrid from '@/components/dashboard/VideoGrid'
import { InlineError } from '@/components/ui/feedback'

export default function DashboardPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {user && !user.email_verified && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-4 mb-6 flex items-center justify-between">
          <div>
            <p className="text-yellow-200 font-medium">{strings.auth.verify.title}</p>
            <p className="text-yellow-200/70 text-sm">Confirme seu e-mail para receber 2 créditos grátis e começar a gerar vídeos.</p>
          </div>
          <button
            onClick={() => router.push(`/auth/verify?email=${encodeURIComponent(user.email)}`)}
            className="btn-primary px-4 py-2 rounded-lg text-sm whitespace-nowrap ml-4"
          >
            {strings.dashboard.verifyBanner.cta}
          </button>
        </div>
      )}
      <GenerateForm onJobComplete={loadJobs} />

      <section className="mt-12">
        <h2 className="text-lg font-semibold mb-6">Seus vídeos</h2>
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
          />
        )}
      </section>
    </div>
  )
}
