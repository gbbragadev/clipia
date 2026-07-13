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
    music_asset_id: import('@/remotion/music-assets').MusicAssetId | null
    music_volume: number
  }>(`${API_BASE}/jobs/${jobId}/composition`, {
    headers: getAuthHeaders(),
  })

  // Restore from saved editor_state if available
  const saved = data.editor_state?.composition as Partial<CompositionData> | undefined

  return {
    title: data.script.title || '',
    // Normaliza cenas: templates de IA (ai_video/novelinha) vem com visual_hint e
    // SEM keywords_en — o editor (SceneGrid) faz .map/.join em keywords_en
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
    musicAssetId: saved ? (saved.musicAssetId ?? null) : (data.music_asset_id ?? null),
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
  /** Poster JPEG do vídeo final (rota autenticada; null em jobs antigos). */
  thumbnail_url?: string | null
  /** Fração 0..1 do pipeline (tempo real via Redis). */
  progress?: number
  /** Etapa atual do pipeline (chave de STEP_LABELS). */
  current_step?: string | null
  /** Roteiro atendido pelo provedor LLM free (badge "qualidade reduzida"). */
  degraded?: boolean
  /** Quantos jobs estão na frente na fila do worker (só quando status === 'queued'). */
  queue_position?: number | null
}

/** Jobs nestes status ainda vão mudar sozinhos — a grid faz polling enquanto existirem. */
export const ACTIVE_JOB_STATUSES = ['queued', 'processing', 'rendering', 'cancelling']

/** Rótulos pt-BR das etapas do pipeline (compartilhado por GenerateForm e VideoCard). */
export const STEP_LABELS: Record<string, string> = {
  scripting: 'Escrevendo roteiro...',
  generating_images: 'Gerando imagens IA...',
  generating_videos: 'Gerando clipes IA...',
  tts: 'Gerando narração...',
  transcribing: 'Transcrevendo áudio...',
  media: 'Buscando vídeos...',
  compositing: 'Montando vídeo...',
  finalizing: 'Finalizando...',
  preparing: 'Preparando re-render...',
  encoding: 'Renderizando edições...',
  queued: 'Na fila...',
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
  voice_provider?: 'edge' | 'elevenlabs'
  voice_config?: Record<string, unknown>
  trend_context?: string
  sfx_enabled?: boolean
  music_enabled?: boolean
  /** 'dialogue' = roteiro em conversa + 2 vozes (só em templates dialogue_capable). */
  narration_mode?: 'single' | 'dialogue'
  /** Roteiro pronto do /script-preview (possivelmente editado) — pula a geração de roteiro. */
  custom_script?: Record<string, unknown>
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
  /** Aceita narração em diálogo (2 vozes)? dialogue_duo é diálogo nativo → false. */
  dialogue_capable?: boolean
}

export async function fetchTemplates(): Promise<VideoTemplateInfo[]> {
  const res = await fetch(`${API_BASE}/templates`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) return []
  return res.json()
}

export async function generateVideo(
  params: GenerateParams,
): Promise<{ job_id: string; status: string; credit_cost: number }> {
  // credit_cost é o débito REAL do servidor (base + refinos liquidados) — confirmação
  // do custo prometido na UI. Backend responde 202 (aceito p/ fila; fetchJSON usa res.ok).
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
  /** Tradução pt-BR do título (fontes EN); exibir title_pt || title. */
  title_pt?: string
}

export async function fetchTrends(nicho?: string): Promise<Trend[]> {
  const qs = nicho ? `?nicho=${encodeURIComponent(nicho)}` : ''
  const res = await fetch(`${API_BASE}/trends${qs}`, { headers: getAuthHeaders() })
  if (!res.ok) return []
  const data = await res.json().catch(() => ({ trends: [] }))
  return data.trends ?? []
}

// ── Rascunho de roteiro (preview grátis + refino 0,5) ──────────────────────

export interface ScriptScene {
  text: string
  duration_hint?: number
  keywords_en?: string[]
  visual_hint?: string
  speaker?: string
  [key: string]: unknown
}

export interface ScriptDraft {
  title?: string
  narration: string
  scenes: ScriptScene[]
  [key: string]: unknown
}

export interface ScriptPreviewResponse {
  script: ScriptDraft
  refine_cost: number
  /** Refinos acumulados (0,5 cada) que serão somados ao próximo vídeo. */
  refine_pending: number
}

/** 1º rascunho é grátis (incluso no custo da geração). Lança em falha. */
export async function fetchScriptPreview(params: GenerateParams): Promise<ScriptPreviewResponse> {
  const res = await fetch(`${API_BASE}/script-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Não foi possível gerar o rascunho')
  }
  return res.json()
}

/** Refino custa 0,5 crédito (acumulado; liquidado no próximo vídeo). Lança em falha. */
export async function refineScriptDraft(body: {
  script: ScriptDraft
  instruction: string
  duration_target: number
  template_id: string
}): Promise<ScriptPreviewResponse> {
  const res = await fetch(`${API_BASE}/script-preview/refine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Não foi possível refinar o rascunho')
  }
  return res.json()
}

/** Temas prontos do nicho gerados por IA (renovam a cada hora). [] em falha → use o fallback estático. */
export async function fetchExampleTopics(nicho: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/example-topics/${encodeURIComponent(nicho)}`, { headers: getAuthHeaders() })
  if (!res.ok) return []
  const data = await res.json().catch(() => ({ topics: [] }))
  return Array.isArray(data.topics) ? data.topics : []
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
