import { getToken } from '@/lib/auth'
import { readApiError } from '@/lib/http'

/** Callback de progresso: fração 0..1. Só é chamado quando o Content-Length é conhecido. */
export type DownloadProgress = (fraction: number) => void

function buildHeaders(): HeadersInit {
  const token = getToken()
  if (!token) throw new Error('Não autenticado')
  return { Authorization: `Bearer ${token}` }
}

/**
 * Busca um arquivo protegido por Bearer e devolve o Blob + filename do servidor.
 * Com `onProgress`, lê o corpo em streaming e reporta a fração baixada — é o que
 * alimenta spinner/porcentagem nos botões de download (antes o botão parecia
 * morto em conexões lentas: blob inteiro em memória sem nenhum feedback).
 */
export async function fetchAuthenticatedBlob(
  url: string,
  onProgress?: DownloadProgress,
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetch(url, { headers: buildHeaders() })
  // 401 aqui = este arquivo específico negou; não desloga a sessão (BUG-R003). Apenas falha local.
  if (!response.ok) {
    throw new Error(await readApiError(response, 'Erro ao baixar arquivo'))
  }

  const disposition = response.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match?.[1] ?? null

  const total = Number(response.headers.get('content-length') || 0)
  if (!onProgress || !response.body || !total) {
    return { blob: await response.blob(), filename }
  }

  const reader = response.body.getReader()
  const chunks: BlobPart[] = []
  let received = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    chunks.push(value)
    received += value.byteLength
    onProgress(Math.min(received / total, 1))
  }
  const type = response.headers.get('content-type') || 'application/octet-stream'
  return { blob: new Blob(chunks, { type }), filename }
}

export async function downloadAuthenticatedFile(
  url: string,
  fallbackFilename: string,
  onProgress?: DownloadProgress,
): Promise<void> {
  const { blob, filename } = await fetchAuthenticatedBlob(url, onProgress)
  saveBlob(blob, filename || fallbackFilename)
}

/** Dispara o "salvar como" do browser para um Blob já em memória (sem novo fetch). */
export function saveBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}

export async function fetchAuthenticatedBlobUrl(url: string, onProgress?: DownloadProgress): Promise<string> {
  const { blob } = await fetchAuthenticatedBlob(url, onProgress)
  return URL.createObjectURL(blob)
}
