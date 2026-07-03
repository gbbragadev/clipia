import type { CompositionData, TransitionType } from '@/remotion/types'
import { DEFAULT_SUBTITLE_STYLE, DEFAULT_VOICE_CONFIG } from '@/remotion/types'
import { getToken } from '@/lib/auth'
import { fetchAuthenticatedBlobUrl } from '@/lib/download'
import { fetchJson, readApiError } from '@/lib/http'

const API_BASE = '/api/v1'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  return fetchJson<T>(url, options, 'Erro na requisicao')
}

function getAuthHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchComposition(jobId: string): Promise<CompositionData> {
  const data = await fetchJSON<{
    job_id: string
    script: { title: string; scenes: Array<{ text: string; keywords_en?: string[]; visual_hint?: string; duration_hint: number; transition?: string }>; narration: string }
    words: Array<{ word: string; start: number; end: number }>
    audio_url: string
    media_urls: string[]
    subtitle_style: Record<string, unknown>
    editor_state: Record<string, unknown> | null
    template_id: string
    layout_type: string
    fps: number
    width: number
    height: number
    pending_credits: number
    music_url: string | null
    music_volume: number
  }>(`${API_BASE}/jobs/${jobId}/composition`, {
    headers: getAuthHeaders(),
  })

  // Restore from saved editor_state if available
  const saved = data.editor_state?.composition as Partial<CompositionData> | undefined

  return {
    title: data.script.title || '',
    // Normaliza cenas: templates de IA (ai_video/novelinha) vem com visual_hint e
    // SEM keywords_en — o editor (SceneGrid/ScriptEditor) faz .map/.join em keywords_en
    // e crashava ("Cannot read properties of undefined (reading 'map')"). Garante array.
    scenes: (data.script.scenes ?? []).map((s) => ({
      ...s,
      keywords_en: s.keywords_en ?? [],
      transition: s.transition as TransitionType | undefined,
    })),
    words: data.words ?? [],
    audioUrl: data.audio_url,
    mediaUrls: data.media_urls,
    subtitleStyle: {
      ...DEFAULT_SUBTITLE_STYLE,
      ...(data.subtitle_style as Partial<typeof DEFAULT_SUBTITLE_STYLE>),
      ...(saved?.subtitleStyle ?? {}),
    },
    voiceConfig: saved?.voiceConfig ?? DEFAULT_VOICE_CONFIG,
    fps: data.fps,
    width: data.width,
    height: data.height,
    overlays: saved?.overlays ?? [],
    musicUrl: saved ? (saved.musicUrl ?? null) : (data.music_url ?? null),
    musicVolume: saved?.musicVolume ?? data.music_volume ?? 0.12, // alinha com AUTO_MUSIC_VOLUME do backend
    isRendering: false,
    templateId: data.template_id || 'stock_narration',
    layoutType: (data.layout_type as import('@/remotion/types').LayoutType) || 'fullscreen',
    pendingCredits: data.pending_credits || 0,
  }
}

export async function saveEditorState(jobId: string, editorState: Record<string, unknown>): Promise<void> {
  await fetchJSON(`${API_BASE}/jobs/${jobId}/edit`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ editor_state: editorState }),
  })
}

export interface JobSummary {
  job_id: string
  topic: string
  style: string
  status: string
  duration_target: number
  created_at: string | null
  download_url: string | null
}

export async function fetchJobs(): Promise<JobSummary[]> {
  return fetchJSON<JobSummary[]>(`${API_BASE}/jobs`, {
    headers: getAuthHeaders(),
  })
}

export interface GenerateParams {
  topic: string
  style: string
  duration_target: number
  template_id: string
  voice_provider?: 'edge' | 'elevenlabs' | 'custom'
  voice_config?: Record<string, unknown>
  trend_context?: string
  sfx_enabled?: boolean
  music_enabled?: boolean
}

export interface VoiceInfo {
  id: string
  name: string
  provider: 'edge' | 'elevenlabs' | 'custom'
  language: string
  gender?: string | null
  preview_url?: string | null
  is_clone?: boolean
  clone_id?: string
}

export async function fetchVoices(): Promise<VoiceInfo[]> {
  const res = await fetch(`${API_BASE}/voices`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) return []
  return res.json()
}

/**
 * Clona uma voz enviando 1+ amostras de audio.
 * Backend espera multipart/form-data com campos `files`, `name` e `description`.
 * Custa CREDIT_COST_VOICE_CLONE creditos (5). Max 5 clones por usuario.
 */
export async function cloneVoice(
  name: string,
  files: File[],
  description = '',
): Promise<{ clone_id: string; voice_id: string; name: string }> {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  form.append('name', name)
  if (description) form.append('description', description)

  const token = getToken()
  const res = await fetch(`${API_BASE}/voices/clone`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    throw new Error(await readApiError(res, 'Não foi possível clonar a voz'))
  }
  return res.json()
}

/** Deleta uma voz clonada pelo seu clone_id. */
export async function deleteVoice(cloneId: string): Promise<{ status: string }> {
  return fetchJSON<{ status: string }>(`${API_BASE}/voices/${cloneId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
}

export async function uploadJobAudio(
  jobId: string,
  file: File,
): Promise<{ audio_url: string; words: Array<Record<string, unknown>>; duration: number }> {
  const form = new FormData()
  form.append('file', file)
  const token = getToken()
  const res = await fetch(`${API_BASE}/jobs/${jobId}/upload-audio`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Erro ao enviar áudio')
  }
  return res.json()
}

export interface VideoTemplateInfo {
  id: string
  name: string
  description: string
  icon: string
  layout_type: string
  media_source?: string
  default_voice_provider?: 'edge' | 'elevenlabs' | 'custom'
  default_voice_id?: string
  credit_costs?: Partial<Record<'edge' | 'elevenlabs' | 'custom', number>>
}

export async function fetchTemplates(): Promise<VideoTemplateInfo[]> {
  const res = await fetch(`${API_BASE}/templates`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) return []
  return res.json()
}

export async function generateVideo(params: GenerateParams): Promise<{ job_id: string; status: string }> {
  return fetchJSON(`${API_BASE}/generate`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(params),
  })
}

export interface Trend {
  title: string
  source: string
  score: number
  url: string
  context: string
}

export async function fetchTrends(nicho?: string): Promise<Trend[]> {
  const qs = nicho ? `?nicho=${encodeURIComponent(nicho)}` : ''
  const res = await fetch(`${API_BASE}/trends${qs}`, { headers: getAuthHeaders() })
  if (!res.ok) return []
  const data = await res.json().catch(() => ({ trends: [] }))
  return data.trends ?? []
}

export async function regenerateTTS(
  jobId: string,
  narrationText: string,
  voiceId?: string,
  rate?: number,
  pitch?: number,
): Promise<{ audio_url: string; words: Array<{ word: string; start: number; end: number }> }> {
  return fetchJSON(`${API_BASE}/jobs/${jobId}/regenerate-tts`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      text: narrationText,
      voice_id: voiceId,
      rate,
      pitch,
    }),
  })
}

export interface JobStatusResponse {
  job_id: string
  status: string
  progress: number
  current_step: string | null
  error: string | null
  created_at: string
  download_url: string | null
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  return fetchJSON<JobStatusResponse>(`${API_BASE}/jobs/${jobId}`, {
    headers: getAuthHeaders(),
  })
}

/**
 * Cancela um job em andamento (processing/queued).
 * O backend marca como "cancelling" e o worker reembolsa o credito da geracao.
 * Retorna { status: "cancelling" }.
 */
export async function cancelJob(jobId: string): Promise<{ status: string }> {
  return fetchJSON<{ status: string }>(`${API_BASE}/jobs/${jobId}/cancel`, {
    method: 'POST',
    headers: getAuthHeaders(),
  })
}

/**
 * Reseta o editor_state do job aos defaults.
 * Custa 1 credito, zera pending_credits e limpa editor_state.
 * Retorna { status: "reset", credits_remaining: number }.
 */
export async function resetJob(jobId: string): Promise<{ status: string; credits_remaining: number }> {
  return fetchJSON<{ status: string; credits_remaining: number }>(`${API_BASE}/jobs/${jobId}/reset`, {
    method: 'POST',
    headers: getAuthHeaders(),
  })
}

export async function fetchJobDownloadBlobUrl(jobId: string): Promise<string> {
  return fetchAuthenticatedBlobUrl(`${API_BASE}/jobs/${jobId}/download`)
}
