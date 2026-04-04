'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getToken } from '@/lib/auth'
import {
  fetchJobs,
  generateVideo,
  fetchJobStatus,
  type JobSummary,
  type GenerateParams,
  type JobStatusResponse,
} from '@/lib/editor-api'

const STYLES = [
  { value: 'educational' as const, label: 'Educacional', icon: '📚', desc: 'Explica conceitos de forma clara' },
  { value: 'curiosity' as const, label: 'Curiosidades', icon: '🤯', desc: 'Fatos surpreendentes e intrigantes' },
  { value: 'storytelling' as const, label: 'Storytelling', icon: '📖', desc: 'Narrativa envolvente' },
  { value: 'news' as const, label: 'Notícias', icon: '📰', desc: 'Tom jornalístico e informativo' },
]

const STEP_LABELS: Record<string, string> = {
  scripting: 'Escrevendo roteiro...',
  tts: 'Gerando narração...',
  transcribing: 'Transcrevendo áudio...',
  media: 'Buscando vídeos...',
  compositing: 'Montando vídeo...',
  finalizing: 'Finalizando...',
}

function statusColor(status: string) {
  switch (status) {
    case 'completed': case 'editable': return '#10b981'
    case 'failed': case 'error': return '#ef4444'
    case 'processing': return '#6C5CE7'
    default: return '#666'
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'completed': case 'editable': return 'Pronto'
    case 'failed': case 'error': return 'Erro'
    case 'processing': return 'Gerando...'
    case 'queued': return 'Na fila'
    default: return status
  }
}

function timeAgo(dateStr: string | null) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `${mins}min atrás`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h atrás`
  return `${Math.floor(hours / 24)}d atrás`
}

export default function DashboardPage() {
  const router = useRouter()
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [loading, setLoading] = useState(true)

  // Generate form
  const [topic, setTopic] = useState('')
  const [style, setStyle] = useState<GenerateParams['style']>('educational')
  const [duration, setDuration] = useState(30)
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState<string | null>(null)

  // Active job tracking
  const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Auth guard
  useEffect(() => {
    if (!getToken()) router.replace('/auth/login')
  }, [router])

  // Load jobs
  const loadJobs = useCallback(async () => {
    try {
      const data = await fetchJobs()
      setJobs(data)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadJobs() }, [loadJobs])

  // Poll active job
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchJobStatus(jobId)
        setActiveJob(status)
        if (status.status === 'completed' || status.status === 'editable') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          loadJobs()
        } else if (status.status === 'failed' || status.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          setGenError(status.error || 'Erro ao gerar vídeo')
          loadJobs()
        }
      } catch { /* silent */ }
    }, 2000)
  }, [loadJobs])

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const handleGenerate = async () => {
    if (!topic.trim() || generating) return
    setGenerating(true)
    setGenError(null)
    setActiveJob(null)
    try {
      const result = await generateVideo({ topic: topic.trim(), style, duration_target: duration })
      startPolling(result.job_id)
      setActiveJob({ job_id: result.job_id, status: 'queued', progress: 0, current_step: null, error: null, created_at: new Date().toISOString(), download_url: null })
    } catch (err) {
      setGenerating(false)
      setGenError(err instanceof Error ? err.message : 'Erro ao iniciar geração')
    }
  }

  const canEdit = (status: string) => ['completed', 'editable'].includes(status)

  return (
    <div style={{ minHeight: '100vh', background: '#111', color: '#E8E8E8', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)',
        background: '#1A1A1A',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 20, fontWeight: 700, color: '#6C5CE7' }}>ClipIA</span>
          <span style={{ fontSize: 12, color: '#666', padding: '2px 8px', background: '#222', borderRadius: 4 }}>Dashboard</span>
        </div>
        <button
          onClick={() => { localStorage.removeItem('clipia_token'); router.push('/auth/login') }}
          style={{ background: 'none', border: '1px solid #333', borderRadius: 6, color: '#888', padding: '6px 12px', fontSize: 12, cursor: 'pointer' }}
        >
          Sair
        </button>
      </header>

      <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 20px' }}>
        {/* Generate section */}
        <section style={{ marginBottom: 40 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 20 }}>Criar novo vídeo</h2>

          {/* Topic input */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#999', marginBottom: 6 }}>Tema do vídeo</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleGenerate() }}
              placeholder="Ex: 5 curiosidades sobre o oceano profundo"
              disabled={generating}
              style={{
                width: '100%', padding: '12px 16px', fontSize: 15, borderRadius: 10,
                border: '1px solid #333', background: '#1A1A1A', color: '#E8E8E8',
                outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Style selector */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#999', marginBottom: 6 }}>Estilo</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {STYLES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStyle(s.value)}
                  disabled={generating}
                  style={{
                    padding: '10px 8px', borderRadius: 10, border: 'none', cursor: 'pointer',
                    background: style === s.value ? 'rgba(108,92,231,0.15)' : '#1A1A1A',
                    outline: style === s.value ? '2px solid #6C5CE7' : '1px solid #333',
                    textAlign: 'center', transition: 'all 0.15s',
                  }}
                >
                  <div style={{ fontSize: 20, marginBottom: 4 }}>{s.icon}</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: style === s.value ? '#E8E8E8' : '#999' }}>{s.label}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Duration slider */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, color: '#999', marginBottom: 6 }}>
              Duração: {duration}s
            </label>
            <input
              type="range" min={20} max={60} value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              disabled={generating}
              style={{ width: '100%', accentColor: '#6C5CE7' }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#555' }}>
              <span>20s</span><span>60s</span>
            </div>
          </div>

          {/* Active job progress */}
          {activeJob && generating && (
            <div style={{
              padding: 16, borderRadius: 10, background: '#1A1A1A',
              border: '1px solid rgba(108,92,231,0.2)', marginBottom: 16,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: '#ccc' }}>
                  {activeJob.current_step ? STEP_LABELS[activeJob.current_step] || activeJob.current_step : 'Iniciando...'}
                </span>
                <span style={{ fontSize: 13, color: '#6C5CE7', fontWeight: 600 }}>
                  {Math.round(activeJob.progress * 100)}%
                </span>
              </div>
              <div style={{ height: 6, background: '#222', borderRadius: 3, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 3, background: '#6C5CE7',
                  width: `${Math.max(5, activeJob.progress * 100)}%`,
                  transition: 'width 0.5s ease',
                }} />
              </div>
            </div>
          )}

          {genError && (
            <div style={{ padding: 12, borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', fontSize: 13, marginBottom: 16 }}>
              {genError}
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={generating || !topic.trim()}
            style={{
              width: '100%', padding: '14px 0', borderRadius: 10, border: 'none',
              background: generating || !topic.trim() ? '#333' : '#6C5CE7',
              color: generating || !topic.trim() ? '#666' : '#fff',
              fontSize: 16, fontWeight: 600, cursor: generating || !topic.trim() ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {generating ? 'Gerando...' : 'Gerar Vídeo'}
          </button>
        </section>

        {/* Jobs list */}
        <section>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Seus vídeos</h2>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#555' }}>Carregando...</div>
          ) : jobs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40, color: '#555', fontSize: 14 }}>
              Nenhum vídeo ainda. Crie o primeiro acima!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {jobs.map((job) => (
                <div
                  key={job.job_id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12,
                    padding: '14px 16px', borderRadius: 10,
                    background: '#1A1A1A', border: '1px solid #222',
                    transition: 'border-color 0.15s',
                  }}
                >
                  {/* Status dot */}
                  <div style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: statusColor(job.status),
                  }} />

                  {/* Info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {job.topic}
                    </div>
                    <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
                      {statusLabel(job.status)} · {job.duration_target}s · {timeAgo(job.created_at)}
                    </div>
                  </div>

                  {/* Actions */}
                  {canEdit(job.status) && (
                    <button
                      onClick={() => router.push(`/editor/${job.job_id}`)}
                      style={{
                        padding: '6px 16px', borderRadius: 6, border: 'none',
                        background: '#6C5CE7', color: '#fff', fontSize: 12,
                        fontWeight: 600, cursor: 'pointer', flexShrink: 0,
                      }}
                    >
                      Editar
                    </button>
                  )}
                  {job.download_url && (
                    <a
                      href={job.download_url}
                      download
                      style={{
                        padding: '6px 12px', borderRadius: 6, border: '1px solid #333',
                        color: '#999', fontSize: 12, textDecoration: 'none', flexShrink: 0,
                      }}
                    >
                      Baixar
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
