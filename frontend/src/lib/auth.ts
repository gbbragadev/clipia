const API_BASE = "";

export interface User {
  id: string;
  email: string;
  name: string;
  credits: number;
  plan: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("clipia_token");
}

export function setToken(token: string): void {
  localStorage.setItem("clipia_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("clipia_token");
}

export async function register(email: string, name: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao registrar" }));
    throw new Error(err.detail || "Erro ao registrar");
  }
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Email ou senha incorretos" }));
    throw new Error(err.detail || "Email ou senha incorretos");
  }
  return res.json();
}

export async function getMe(): Promise<User> {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    clearToken();
    throw new Error("Sessão expirada");
  }
  return res.json();
}
