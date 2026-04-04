import type { CompositionData } from '@/remotion/types'
import { DEFAULT_SUBTITLE_STYLE, DEFAULT_VOICE_CONFIG } from '@/remotion/types'
import { getToken } from '@/lib/auth'

const API_BASE = '/api/v1'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const error = await res.text()
    throw new Error(`API error ${res.status}: ${error}`)
  }
  return res.json()
}

function getAuthHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchComposition(jobId: string): Promise<CompositionData> {
  const data = await fetchJSON<{
    job_id: string
    script: { title: string; scenes: Array<{ text: string; keywords_en: string[]; duration_hint: number }>; narration: string }
    words: Array<{ word: string; start: number; end: number }>
    audio_url: string
    media_urls: string[]
    subtitle_style: Record<string, unknown>
    editor_state: Record<string, unknown> | null
    fps: number
    width: number
    height: number
  }>(`${API_BASE}/jobs/${jobId}/composition`)

  return {
    title: data.script.title || '',
    scenes: data.script.scenes,
    words: data.words,
    audioUrl: data.audio_url,
    mediaUrls: data.media_urls,
    subtitleStyle: {
      ...DEFAULT_SUBTITLE_STYLE,
      ...(data.subtitle_style as Partial<typeof DEFAULT_SUBTITLE_STYLE>),
    },
    voiceConfig: DEFAULT_VOICE_CONFIG,
    fps: data.fps,
    width: data.width,
    height: data.height,
    overlays: [],
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
