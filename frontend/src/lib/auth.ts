import { strings } from '@/lib/strings';
import { notifySessionExpired } from "./http";
import type { SelectedPackage } from "./package-intent";
import {
  buildAuthHeaders,
  clearAuthSession,
  getToken,
  hasSessionCandidate,
} from "./session";

export {
  clearAuthSession,
  getCsrfToken,
  getToken,
  hasSessionCandidate,
  setCsrfToken,
  setToken,
} from "./session";

const API_BASE = "";

/**
 * Erro transitório (rede offline, DNS, timeout, 5xx do gateway, etc.).
 * Diferente de sessão expirada (401): NÃO deve derrubar o usuário logado.
 * O AuthContext usa instanceof para distinguir e preservar o token/sessão.
 */
export class NetworkError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "NetworkError";
    this.status = status;
  }
}

/** Timeout das chamadas autenticadas: backend pendurado não pode prender o dashboard no skeleton. */
const AUTH_REQUEST_TIMEOUT_MS = 15000;

/**
 * fetch com timeout via AbortController. Um backend lento/pendurado nunca deve prender um
 * spinner até o Cloudflare estourar (~100s) — falha rápido com mensagem clara. Converte
 * abort/erro de rede em NetworkError (mensagem amigável) e sempre limpa o timer.
 */
async function fetchWithTimeout(
  input: string,
  init: RequestInit = {},
  timeoutMs = AUTH_REQUEST_TIMEOUT_MS,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { credentials: "include", ...init, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new NetworkError("Tempo limite excedido. Tente novamente em instantes.");
    }
    throw new NetworkError("Falha de rede. Verifique sua conexão e tente novamente.");
  } finally {
    clearTimeout(timer);
  }
}

export interface User {
  id: string;
  email: string;
  name: string;
  credits: number;
  plan: string;
  email_verified: boolean;
  referral_code: string;
  selected_package?: SelectedPackage | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  csrf_token: string;
}

export interface ExportedAccountData {
  user: User & { created_at: string | null };
  jobs: Array<Record<string, unknown>>;
  purchases: Array<Record<string, unknown>>;
}

export function clearToken(): void {
  clearAuthSession();
}

export interface RegisterPayload {
  email: string;
  name: string;
  password: string;
  referral_code?: string;
  offer_code?: string;
  marketing_measurement_consent?: boolean;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  turnstile_token?: string;
  consent?: boolean;
  selected_package?: SelectedPackage;
}

export async function register(email: string, name: string, password: string, extra?: Omit<RegisterPayload, "email" | "name" | "password">): Promise<AuthResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password, ...extra }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao registrar"));
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await readError(res, strings.auth.login.error));
  return res.json();
}

export async function getMe(): Promise<User> {
  const token = getToken();
  if (!hasSessionCandidate()) throw new Error("Não autenticado");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), AUTH_REQUEST_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    // Erro de rede (offline/DNS) ou abort por timeout: transitório, NÃO ejetar.
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new NetworkError("Tempo limite ao validar sessão");
    }
    throw new NetworkError("Falha de rede ao validar sessão");
  } finally {
    window.clearTimeout(timer);
  }
  if (!res.ok) {
    // 401 = JWT inválido/expirado de verdade => sessão expirada, ejetar.
    if (res.status === 401) {
      notifySessionExpired();
      throw new Error("Sessão expirada");
    }
    // Qualquer outra coisa (5xx do gateway, 4xx estranho) é transitória:
    // manter o token e deixar o usuário entrar; o polling retenta em breve.
    throw new NetworkError("Serviço indisponível", res.status);
  }
  return res.json();
}

export async function verifyEmail(email: string, code: string): Promise<{ status: string; credits?: number }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao verificar"));
  return res.json();
}

export async function resendCode(email: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/resend-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao reenviar"));
  return res.json();
}

export async function forgotPassword(email: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao enviar codigo"));
  return res.json();
}

export async function verifyResetCode(email: string, code: string): Promise<{ status: string; reset_token: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/verify-reset-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao verificar codigo"));
  return res.json();
}

export async function resetPassword(resetToken: string, password: string): Promise<{ status: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reset_token: resetToken, new_password: password }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao redefinir senha"));
  return res.json();
}

export async function updateProfile(name: string): Promise<User> {
  if (!hasSessionCandidate()) throw new Error("Não autenticado");
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/me`, {
    method: "PATCH",
    headers: buildAuthHeaders("PATCH", { "Content-Type": "application/json" }),
    body: JSON.stringify({ name }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao atualizar perfil"));
  return res.json();
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ status: string }> {
  if (!hasSessionCandidate()) throw new Error("Não autenticado");
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/change-password`, {
    method: "POST",
    headers: buildAuthHeaders("POST", { "Content-Type": "application/json" }),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao alterar senha"));
  return res.json();
}

export async function deleteAccount(password: string): Promise<{ status: string }> {
  if (!hasSessionCandidate()) throw new Error("Não autenticado");
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/delete-account`, {
    method: "POST",
    headers: buildAuthHeaders("POST", { "Content-Type": "application/json" }),
    body: JSON.stringify({ password }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao excluir conta"));
  return res.json();
}

export async function exportAccountData(): Promise<ExportedAccountData> {
  if (!hasSessionCandidate()) throw new Error("Não autenticado");
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/export-data`, {
    headers: buildAuthHeaders("GET"),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao exportar dados"));
  return res.json();
}

export async function logout(): Promise<void> {
  if (!hasSessionCandidate()) return;
  const res = await fetchWithTimeout(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    headers: buildAuthHeaders("POST"),
  });
  if (!res.ok && res.status !== 401) {
    throw new Error(await readError(res, "Erro ao encerrar sessão"));
  }
}

async function readError(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({}));
  return typeof err.detail === "string" && err.detail ? err.detail : fallback;
}
