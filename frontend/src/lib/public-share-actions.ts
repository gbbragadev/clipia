export interface PublicShareActionRequest {
  path: string
  method: 'POST' | 'DELETE'
}

export type PublicShareActionTransport<T> = (request: PublicShareActionRequest) => Promise<T>

function publicShareJobPath(jobId: string): string {
  return `/videos/${encodeURIComponent(jobId)}/public-share`
}

export function publishPublicShare<T>(
  jobId: string,
  transport: PublicShareActionTransport<T>,
): Promise<T> {
  return transport({ path: publicShareJobPath(jobId), method: 'POST' })
}

export async function revokePublicShare(
  jobId: string,
  transport: PublicShareActionTransport<unknown>,
): Promise<void> {
  await transport({ path: publicShareJobPath(jobId), method: 'DELETE' })
}

export function canManagePublicShare(job: { status: string; download_url: string | null }): boolean {
  return job.status === 'completed' && Boolean(job.download_url)
}
