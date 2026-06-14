import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'

function buildHeaders(): HeadersInit {
  const token = getToken()
  if (!token) throw new Error('Não autenticado')
  return { Authorization: `Bearer ${token}` }
}

async function fetchProtectedBlob(url: string): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(url, { headers: buildHeaders() })
  // 401 aqui = este arquivo específico negou; não desloga a sessão (BUG-R003). Apenas falha local.
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Erro ao baixar arquivo'))
  }

  const disposition = response.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? null,
  }
}

export async function downloadAuthenticatedFile(url: string, fallbackFilename: string): Promise<void> {
  const { blob, filename } = await fetchProtectedBlob(url)
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename || fallbackFilename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}

export async function fetchAuthenticatedBlobUrl(url: string): Promise<string> {
  const { blob } = await fetchProtectedBlob(url)
  return URL.createObjectURL(blob)
}
