export function notifySessionExpired(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem('clipia_token')
  window.dispatchEvent(new CustomEvent('clipia:session-expired'))
}

export async function readApiError(response: Response, fallbackMessage: string): Promise<string> {
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail
      if (typeof data?.message === 'string' && data.message.trim()) return data.message
      if (typeof data?.error === 'string' && data.error.trim()) return data.error
    } catch {
      // Fall through to text parsing.
    }
  }

  try {
    const text = await response.text()
    if (text.trim()) return text.trim()
  } catch {
    // Ignore body parsing errors.
  }

  return fallbackMessage
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
