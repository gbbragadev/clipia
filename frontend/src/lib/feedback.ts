import { getToken } from './auth'
import { fetchJson } from './http'

export type FeedbackKind = 'widget' | 'post_video'

export interface FeedbackPayload {
  kind: FeedbackKind
  rating?: number
  comment?: string
  job_id?: string
  source_url?: string
}

export async function submitFeedback(payload: FeedbackPayload): Promise<void> {
  const token = getToken()
  if (!token) throw new Error('Não autenticado')
  await fetchJson(
    '/api/v1/feedback',
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    'Não foi possível enviar o feedback',
  )
}

/** Prompt pós-vídeo é 1x por job: marca/consulta no localStorage. */
export function postVideoFeedbackGiven(jobId: string): boolean {
  try {
    return localStorage.getItem(`clipia_fb_${jobId}`) === '1'
  } catch {
    return true // sem localStorage (SSR/privacidade): não insistir
  }
}

export function markPostVideoFeedbackGiven(jobId: string): void {
  try {
    localStorage.setItem(`clipia_fb_${jobId}`, '1')
  } catch {
    // best-effort
  }
}
