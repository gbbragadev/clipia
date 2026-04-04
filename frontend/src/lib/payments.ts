import { getToken } from "@/lib/auth";

const API_BASE = "";

export interface CreditPackage {
  id: string;
  name: string;
  credits: number;
  price_brl: number;
  price_display: string;
}

export interface PurchaseHistoryItem {
  id: string;
  package_name: string;
  credits_amount: number;
  price_brl: number;
  status: string;
  created_at: string;
  paid_at: string | null;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function fetchPackages(): Promise<CreditPackage[]> {
  const res = await fetch(`${API_BASE}/api/v1/credits/packages`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao carregar pacotes");
  return res.json();
}

export async function createCheckout(packageId: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1/credits/checkout`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ package: packageId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Erro ao criar checkout" }));
    throw new Error(err.detail || "Erro ao criar checkout");
  }
  const data = await res.json();
  return data.checkout_url;
}

export async function fetchHistory(): Promise<PurchaseHistoryItem[]> {
  const res = await fetch(`${API_BASE}/api/v1/credits/history`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Erro ao carregar histórico");
  const data = await res.json();
  return data.purchases;
}
