const TOKEN_STORAGE_KEY = "clipia_token";
const CSRF_STORAGE_KEY = "clipia_csrf";
const CSRF_COOKIE_NAME = "clipia_csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function getCsrfToken(): string | null {
  if (typeof window === "undefined") return null;
  const stored = window.sessionStorage.getItem(CSRF_STORAGE_KEY);
  if (stored) return stored;

  const prefix = `${CSRF_COOKIE_NAME}=`;
  const cookie = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  if (!cookie) return null;
  let token: string;
  try {
    token = decodeURIComponent(cookie.slice(prefix.length));
  } catch {
    return null;
  }
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) return null;
  window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  return token;
}

export function setCsrfToken(token: string): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
  document.cookie = `${CSRF_COOKIE_NAME}=; Max-Age=0; Path=/; SameSite=Lax`;
}

export function hasSessionCandidate(): boolean {
  return Boolean(getToken() || getCsrfToken());
}

export function buildAuthHeaders(method: string, initial?: HeadersInit): Headers {
  const headers = new Headers(initial);
  const bearer = getToken();
  if (bearer) headers.set("Authorization", `Bearer ${bearer}`);

  if (!SAFE_METHODS.has(method.toUpperCase())) {
    const csrf = getCsrfToken();
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  return headers;
}
