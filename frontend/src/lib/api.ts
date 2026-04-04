const API_BASE = ''  // Uses Next.js rewrites to proxy to FastAPI

export interface GenerateRequest {
  topic: string
  style: string
  duration_target: number
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  progress: number
  current_step: string | null
  error: string | null
  created_at: string
  download_url: string | null
}

export async function generateVideo(req: GenerateRequest): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(`Generate failed: ${res.status}`)
  return res.json()
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`)
  if (!res.ok) throw new Error(`Status failed: ${res.status}`)
  return res.json()
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/download`
}
