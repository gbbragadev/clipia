export function notifySessionExpired(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem('clipia_token')
  window.dispatchEvent(new CustomEvent('clipia:session-expired'))
}

function friendlyStatusMessage(status: number, fallback: string): string {
  if (status === 429) return 'Muitas requisições em pouco tempo. Aguarde um instante e tente novamente.'
  if (status === 502 || status === 503 || status === 504)
    return 'Serviço temporariamente indisponível. Tente novamente em instantes.'
  if (status >= 500) return 'Ocorreu um erro no servidor. Tente novamente.'
  return fallback
}

export async function readApiError(response: Response, fallbackMessage: string): Promise<string> {
  const contentType = response.headers.get('content-type') || ''

  // Le o corpo UMA vez (o stream so pode ser consumido uma vez).
  let raw = ''
  try {
    raw = await response.text()
  } catch {
    return friendlyStatusMessage(response.status, fallbackMessage)
  }
  const trimmed = raw.trim()

  // Tenta JSON mesmo quando o content-type nao declara (proxies as vezes mentem).
  if (trimmed && (contentType.includes('application/json') || trimmed.startsWith('{') || trimmed.startsWith('['))) {
    try {
      const data = JSON.parse(trimmed)
      if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail
      if (typeof data?.message === 'string' && data.message.trim()) return data.message
      if (typeof data?.error === 'string' && data.error.trim()) return data.error
    } catch {
      // nao era JSON valido; cai pro tratamento abaixo
    }
  }

  // Corpo HTML (ex.: pagina de erro 502 do Cloudflare) ou muito longo: NUNCA mostrar cru ao usuario.
  const looksLikeHtml = /^\s*</.test(trimmed) || /<html|<!doctype/i.test(trimmed)
  if (!trimmed || looksLikeHtml || trimmed.length > 300) {
    return friendlyStatusMessage(response.status, fallbackMessage)
  }

  // Texto curto e legivel (mensagem de erro em texto puro) pode ser exibido.
  return trimmed
}

export function normalizeNetworkError(error: unknown): Error {
  if (error instanceof Error) {
    return error
  }
  return new Error('Sem conexao. Verifique sua internet e tente novamente.')
}

export function isNetworkError(error: unknown): boolean {
  if (!(error instanceof Error)) return false
  return /failed to fetch|network|conex|offline/i.test(error.message)
}

export async function fetchJson<T>(
  input: RequestInfo | URL,
  init: RequestInit = {},
  fallbackMessage = 'Erro na requisicao',
): Promise<T> {
  try {
    const response = await fetch(input, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...init.headers,
      },
    })

    if (!response.ok) {
      // NÃO deslogar aqui: um 401 de um recurso específico (job, download, composition…) não significa
      // sessão expirada. A expiração real é detectada por getMe() (load + polling 5min do AuthContext).
      // Deslogar em qualquer 401 derrubava a sessão válida por falhas pontuais (BUG-R003).
      throw new Error(await readApiError(response, fallbackMessage))
    }

    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Sem conexao. Verifique sua internet e tente novamente.')
    }
    throw normalizeNetworkError(error)
  }
}
