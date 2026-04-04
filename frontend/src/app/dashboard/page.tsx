'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchJobs, type JobSummary } from '@/lib/editor-api'
import GenerateForm from '@/components/dashboard/GenerateForm'
import VideoGrid from '@/components/dashboard/VideoGrid'

export default function DashboardPage() {
  const router = useRouter()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loading, setLoading] = useState(true)

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await fetchJobs())
    } catch { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadJobs() }, [loadJobs])

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <GenerateForm onJobComplete={loadJobs} />

      <section className="mt-12">
        <h2 className="text-lg font-semibold mb-6">Seus vídeos</h2>
        <VideoGrid
          jobs={jobs}
          loading={loading}
          onEdit={(id) => router.push(`/editor/${id}`)}
        />
      </section>
    </div>
  )
}
