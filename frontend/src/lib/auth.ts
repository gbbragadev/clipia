import { strings } from '@/lib/strings';
import { notifySessionExpired } from "./http";

const API_BASE = "";

export interface User {
  id: string;
  email: string;
  name: string;
  credits: number;
  plan: string;
  email_verified: boolean;
  referral_code: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface ExportedAccountData {
  user: User & { created_at: string | null };
  jobs: Array<Record<string, unknown>>;
  purchases: Array<Record<string, unknown>>;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("clipia_token");
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("clipia_token", token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("clipia_token");
}

export interface RegisterPayload {
  email: string;
  name: string;
  password: string;
  referral_code?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  turnstile_token?: string;
}

export async function register(email: string, name: string, password: string, extra?: Omit<RegisterPayload, "email" | "name" | "password">): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password, ...extra }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao registrar"));
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await readError(res, strings.auth.login.error));
  return res.json();
}

export async function getMe(): Promise<User> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    if (res.status === 401) notifySessionExpired();
    throw new Error("Sessão expirada");
  }
  return res.json();
}

export async function verifyEmail(email: string, code: string): Promise<{ status: string; credits?: number }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao verificar"));
  return res.json();
}

export async function resendCode(email: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/resend-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao reenviar"));
  return res.json();
}

export async function forgotPassword(email: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao enviar codigo"));
  return res.json();
}

export async function verifyResetCode(email: string, code: string): Promise<{ status: string; reset_token: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/verify-reset-code`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao verificar codigo"));
  return res.json();
}

export async function resetPassword(resetToken: string, password: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reset_token: resetToken, new_password: password }),
  });
  if (!res.ok) throw new Error(await readError(res, "Erro ao redefinir senha"));
  return res.json();
}

export async function updateProfile(name: string): Promise<User> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao atualizar perfil"));
  return res.json();
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<{ status: string }> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao alterar senha"));
  return res.json();
}

export async function deleteAccount(password: string): Promise<{ status: string }> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/delete-account`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ password }),
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao excluir conta"));
  return res.json();
}

export async function exportAccountData(): Promise<ExportedAccountData> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/export-data`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) notifySessionExpired();
  if (!res.ok) throw new Error(await readError(res, "Erro ao exportar dados"));
  return res.json();
}

async function readError(res: Response, fallback: string): Promise<string> {
  const err = await res.json().catch(() => ({}));
  return typeof err.detail === "string" && err.detail ? err.detail : fallback;
}
