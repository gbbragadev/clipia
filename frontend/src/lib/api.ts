import { getToken } from "./auth";
import { fetchAuthenticatedBlobUrl } from "./download";
import { fetchJson, readApiError } from "./http";

const API_BASE = "";

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

export interface GenerateRequest {
  topic: string;
  style: string;
  duration_target: number;
}

export interface JobStatus {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  current_step: string | null;
  error: string | null;
  created_at: string;
  download_url: string | null;
}

export async function generateVideo(req: GenerateRequest): Promise<{ job_id: string }> {
  return fetchJson(`${API_BASE}/api/v1/generate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(req),
  }, "Erro ao gerar video");
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await readApiError(res, `Status failed: ${res.status}`));
  return res.json();
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/v1/jobs/${jobId}/download`;
}

export async function getDownloadBlobUrl(jobId: string): Promise<string> {
  return fetchAuthenticatedBlobUrl(getDownloadUrl(jobId));
}
